"""Exact source edits authored by the selected model, never evaluator repairs."""
import hashlib
import json
from . import llm, projects

SCHEMA = {
    'type':'object','additionalProperties':False,'required':['edits'],
    'properties':{'edits':{'type':'array','minItems':1,'maxItems':4,'items':{
        'type':'object','additionalProperties':False,'required':['find','replace'],
        'properties':{'find':{'type':'string','minLength':1,'maxLength':9000},
                      'replace':{'type':'string','maxLength':9000}}}}}
}


def digest(source):
    return hashlib.sha256(source.encode()).hexdigest()


def apply(source, raw):
    """Apply a complete unambiguous patch in memory, or reject all its edits."""
    import jsonschema
    patch=json.loads(projects.unwrap_file(raw,'patch.json'))
    try:jsonschema.validate(patch,SCHEMA)
    except jsonschema.ValidationError as exc:raise ValueError('Invalid source patch schema.') from exc
    result=source
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


async def request(source, *, task, errors, contracts, max_tokens=900, diagnose=False):
    # Choices only describe existing text, never the correct replacement. A
    # bounded model can select a line or the whole part without inventing find
    # strings. Exact-match application still validates online/plain JSON output.
    schema=json.loads(json.dumps(SCHEMA))
    choices=[source]+[line.strip() for line in source.splitlines() if line.strip() and source.count(line.strip())==1]
    schema['properties']['edits']['items']['properties']['find']['enum']=list(dict.fromkeys(choices))
    fmt={'type':'json_schema','json_schema':{'name':'source_patch','strict':True,'schema':schema}} if llm.active_backend()=='local' else 'json'
    diagnosis=None
    if diagnose:
        diagnosis=await llm.chat([
            {'role':'system','content':'Explain the smallest correction required by the actual validation errors. Read the task and current source. Describe what must change and why, in at most four short sentences. Do not repeat the source or claim it passes. Do not write a patch or code.'},
            {'role':'user','content':json.dumps({'errors':errors,'task':task,'source':source},ensure_ascii=False)}
        ],max_tokens=220,temperature=.2)
    plan=(diagnosis or {}).get('content','')[:1800]
    result=await llm.chat([
        {'role':'system','content':'You repair an existing source part using exact text edits. Return one JSON object with edits, an array of objects containing find and replace strings. Copy find text exactly from the supplied source, matching once. Write the corrected replacement yourself. Change only failing lines; preserve correct code. No markdown or commentary.'},
        {'role':'user','content':json.dumps({'source':source,'errors':errors,'contracts':contracts,'task':task,
            'find_choices':list(dict.fromkeys(choices)),**({'repair_plan':plan} if plan else {})},ensure_ascii=False)}
    ],fmt=fmt,max_tokens=max_tokens,temperature=.2)
    if diagnosis:
        result['repair_plan']={'text':plan,'sha256':digest(plan),'model':diagnosis.get('stats',{}).get('served_model',''),
                               'finish_reason':diagnosis.get('stats',{}).get('finish_reason')}
    return result
