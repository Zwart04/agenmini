"""Exact source edits authored by the selected model, never evaluator repairs."""
import hashlib
import json
import re
from . import llm, projects

SCHEMA = {
    'type':'object','additionalProperties':False,'required':['edits'],
    'properties':{'edits':{'type':'array','minItems':1,'maxItems':4,'items':{
        'type':'object','additionalProperties':False,'required':['find','replace'],
        'properties':{'find':{'type':'string','minLength':1,'maxLength':9000},
                      'replace':{'type':'string','maxLength':9000}}}}}
}
INDEXED_SCHEMA = {
    'type':'object','additionalProperties':False,'required':['edits'],
    'properties':{'edits':{'type':'array','minItems':1,'maxItems':8,'items':{
        'type':'object','additionalProperties':False,'required':['line','replace'],
        'properties':{'line':{'type':'integer','minimum':1},
                      'replace':{'type':'string','maxLength':9000}}}}}
}


def digest(source):
    return hashlib.sha256(source.encode()).hexdigest()


def failing_lines(source, errors):
    """Locate identifiers named by real checks, without deciding replacements."""
    lines=source.splitlines()
    identifiers=set()
    for error in errors:
        if error.startswith(('Patch rejected:','The patch introduced')):continue
        named=set(re.findall(r'\b([A-Za-z_]\w*)\.(?:disabled|hidden)\s+expected',error))
        named.update(re.findall(r'\b([A-Za-z_][\w-]*) must (?:have|not have) HTML attribute',error))
        # A generic structural error can concern another line. Do not prevent
        # that repair merely because a separate error happens to name an ID.
        if not named:return list(range(1,len(lines)+1))
        identifiers.update(named)
    matched=[i for i,line in enumerate(lines,1) if any(re.search(r'(?<![\w-])'+re.escape(name)+r'(?![\w-])',line) for name in identifiers)]
    return matched or list(range(1,len(lines)+1))


def apply(source, raw):
    """Apply a complete unambiguous patch in memory, or reject all its edits."""
    import jsonschema
    patch=json.loads(projects.unwrap_file(raw,'patch.json'))
    indexed=isinstance(patch,dict) and isinstance(patch.get('edits'),list) and any(isinstance(edit,dict) and 'line' in edit for edit in patch['edits'])
    try:jsonschema.validate(patch,INDEXED_SCHEMA if indexed else SCHEMA)
    except jsonschema.ValidationError as exc:raise ValueError('Invalid source patch schema.') from exc
    result=source
    if indexed:
        lines=source.splitlines(keepends=True);seen=set()
        for edit in patch['edits']:
            line=edit['line']
            if line>len(lines) or line in seen:raise ValueError('Patch line must exist exactly once in original source.')
            seen.add(line)
        # All addresses refer to the original source. No offset drift when a
        # replacement spans several lines, and no partial application on error.
        for edit in sorted(patch['edits'],key=lambda item:item['line'],reverse=True):
            index=edit['line']-1;new=edit['replace']
            ending='\r\n' if lines[index].endswith('\r\n') else '\n' if lines[index].endswith('\n') else ''
            lines[index]=new+(ending if new and not new.endswith(('\n','\r')) else '')
        result=''.join(lines)
    else:
        for edit in patch['edits']:
            old,new=edit['find'],edit['replace']
            if result.count(old)!=1:raise ValueError('Patch find text must match exactly once in current source.')
            result=result.replace(old,new,1)
    if not result.strip() or result==source:raise ValueError('Patch cannot empty the part or leave it unchanged.')
    return result


def replay(origin_raw, chain, path, select_source=None):
    """Verify retained model text and every exact transformation before reuse."""
    if not isinstance(origin_raw,str) or not isinstance(chain,list) or not 1<=len(chain)<=2:
        raise ValueError('Incomplete model patch provenance.')
    source=projects.unwrap_file(origin_raw,path)
    if select_source:source=select_source(source)
    for entry in chain:
        if entry['base_sha256']!=digest(source):raise ValueError('Patch base changed.')
        if entry['raw_sha256']!=digest(entry['raw_patch']):raise ValueError('Patch response changed.')
        plan=entry.get('repair_plan')
        if plan is not None and (not isinstance(plan,dict) or not isinstance(plan.get('text'),str) or plan.get('sha256')!=digest(plan['text'])):
            raise ValueError('Repair diagnosis changed.')
        source=apply(source,entry['raw_patch'])
        if entry['source_sha256']!=digest(source):raise ValueError('Patch result changed.')
    return source


async def request(source, *, task, errors, contracts, max_tokens=900, diagnose=False, indexed=False):
    # Choices only describe existing text, never the correct replacement. A
    # bounded model can select a line or the whole part without inventing find
    # strings. Exact-match application still validates online/plain JSON output.
    schema=json.loads(json.dumps(INDEXED_SCHEMA if indexed else SCHEMA))
    choices=[source]+[line.strip() for line in source.splitlines() if line.strip() and source.count(line.strip())==1]
    targets=failing_lines(source,errors) if indexed else []
    if indexed:
        schema['properties']['edits']['items']['properties']['line']['enum']=targets
        schema['properties']['edits']['maxItems']=min(8,len(targets))
    else:schema['properties']['edits']['items']['properties']['find']['enum']=list(dict.fromkeys(choices))
    fmt={'type':'json_schema','json_schema':{'name':'source_patch','strict':True,'schema':schema}} if llm.active_backend()=='local' else 'json'
    reasoning_allowance=512 if llm.active_backend()=='local' and llm.coding_reasoning.get() else 0
    diagnosis=None
    if diagnose:
        diagnosis=await llm.chat([
            {'role':'system','content':'Explain the smallest correction required by the actual validation errors. Read the task and current source. Describe what must change and why, in at most four short sentences. Do not repeat the source or claim it passes. Do not write a patch or code.'},
            {'role':'user','content':json.dumps({'errors':errors,'task':task,'source':source},ensure_ascii=False)}
        ],max_tokens=220+reasoning_allowance,temperature=.2)
    plan=(diagnosis or {}).get('content','')[:1800]
    result=await llm.chat([
        {'role':'system','content':('You repair existing source using numbered lines. Return one JSON object with edits, an array of objects containing line (original integer line number) and replace (complete corrected line text). Edit only the listed failing lines; change their logic to satisfy the check. Do not just copy their old text. Do not copy line numbers into replacement code. Leave every correct line untouched. Write replacements yourself. No markdown or commentary.' if indexed else 'You repair an existing source part using exact text edits. Return one JSON object with edits, an array of objects containing find and replace strings. Copy find text exactly from the supplied source, matching once. Write the corrected replacement yourself. Change only failing lines; preserve correct code. No markdown or commentary.')},
        {'role':'user','content':json.dumps({'source':source,'errors':errors,'contracts':contracts,'task':task,
            **({'numbered_lines':[{'line':number,'text':line} for number,line in enumerate(source.splitlines(),1) if number in targets]} if indexed else {'find_choices':list(dict.fromkeys(choices))}),**({'repair_plan':plan} if plan else {})},ensure_ascii=False)}
    ],fmt=fmt,max_tokens=max_tokens+reasoning_allowance,temperature=.2)
    if diagnosis:
        result['repair_plan']={'text':plan,'sha256':digest(plan),'model':diagnosis.get('stats',{}).get('served_model',''),
                               'finish_reason':diagnosis.get('stats',{}).get('finish_reason')}
    return result
