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


def replay(origin_raw, chain, path):
    """Verify retained model text and every exact transformation before reuse."""
    if not isinstance(origin_raw,str) or not isinstance(chain,list) or not 1<=len(chain)<=2:
        raise ValueError('Incomplete model patch provenance.')
    source=projects.unwrap_file(origin_raw,path)
    for entry in chain:
        if entry['base_sha256']!=digest(source):raise ValueError('Patch base changed.')
        if entry['raw_sha256']!=digest(entry['raw_patch']):raise ValueError('Patch response changed.')
        source=apply(source,entry['raw_patch'])
        if entry['source_sha256']!=digest(source):raise ValueError('Patch result changed.')
    return source


async def request(source, *, task, errors, contracts, max_tokens=900):
    # Choices only describe existing text, never the correct replacement. A
    # bounded model can select a line or the whole part without inventing find
    # strings. Exact-match application still validates online/plain JSON output.
    schema=json.loads(json.dumps(SCHEMA))
    choices=[source]+[line.strip() for line in source.splitlines() if line.strip() and source.count(line.strip())==1]
    schema['properties']['edits']['items']['properties']['find']['enum']=list(dict.fromkeys(choices))
    fmt={'type':'json_schema','json_schema':{'name':'source_patch','strict':True,'schema':schema}} if llm.active_backend()=='local' else 'json'
    return await llm.chat([
        {'role':'system','content':'You repair an existing source part using exact text edits. Return one JSON object with edits, an array of objects containing find and replace strings. Copy find text exactly from the supplied source, matching once. Write the corrected replacement yourself. Change only failing lines; preserve correct code. No markdown or commentary.'},
        {'role':'user','content':json.dumps({'source':source,'errors':errors,'contracts':contracts,'task':task,
            'find_choices':list(dict.fromkeys(choices))},ensure_ascii=False)}
    ],fmt=fmt,max_tokens=max_tokens,temperature=.2)
