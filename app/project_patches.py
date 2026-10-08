"""Exact source edits authored by the selected model, never evaluator repairs."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from html.parser import HTMLParser
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
REMOVAL_SCHEMA = {
    'type':'object','additionalProperties':False,'required':['edits'],
    'properties':{'edits':{'type':'array','minItems':1,'maxItems':4,'items':{
        'type':'object','additionalProperties':False,'required':['line','remove'],
        'properties':{'line':{'type':'integer','minimum':1},'remove':{'type':'string','minLength':1,'maxLength':9000}}}}}
}


def digest(source):
    return hashlib.sha256(source.encode()).hexdigest()


def prompt_errors(errors):
    """Keep real examples concise; validators/journals still retain all failures."""
    helper=0;selected=[]
    for error in errors:
        if error.startswith('Helper behavior failed: '):
            helper+=1
            if helper>3:continue
        selected.append(error)
    return selected


def forbidden_attribute_choices(source, errors):
    """Offer only unique spans already present on the IDs named by real checks."""
    forbidden={}
    for error in errors:
        found=re.fullmatch(r'([\w-]+) must not have HTML attribute ([\w-]+)\.',error)
        if found:forbidden.setdefault(found[1],set()).add(found[2].lower())
    choices=[]
    class AttributeSpans(HTMLParser):
        def handle_starttag(self,tag,attrs):
            ident=dict(attrs).get('id')
            if ident not in forbidden:return
            opening=self.get_starttag_text()
            tag_end=re.match(r'<\s*[^\s/>]+',opening).end()
            for match in re.finditer(r'''\s+([^\s/>=]+)(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?''',opening[tag_end:]):
                span=match[0]
                if match[1].lower() in forbidden[ident] and source.count(span)==1:choices.append(span)
        def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
    AttributeSpans().feed(source)
    return list(dict.fromkeys(choices))


def duplicate_id_choices(source, errors):
    """Locate existing duplicate ID attributes; the model chooses which to remove."""
    if 'Remove duplicate IDs.' not in errors:return []
    occurrences={};lines=source.splitlines()
    class IdSpans(HTMLParser):
        def handle_starttag(self,tag,attrs):
            ident=dict(attrs).get('id')
            if not ident:return
            opening=self.get_starttag_text();base=self.getpos()[0]
            # Multiline attribute spans are left to the general source editor.
            for match in re.finditer(r'''[ \t]+id\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''',opening,re.I):
                span=match[0];line=base+opening[:match.start()].count('\n')
                if '\n' not in span and lines[line-1].count(span)==1:
                    occurrences.setdefault(ident,[]).append({'line':line,'remove':span})
        def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
    IdSpans().feed(source)
    return [choice for choices in occurrences.values() if len(choices)>1 for choice in choices]


PROPERTY_LOCATIONS = r'''
const fs=require('node:fs'),acorn=require(process.argv[1]);
const input=JSON.parse(fs.readFileSync(0,'utf8'));
try{
 const ast=acorn.parse(input.source,{ecmaVersion:'latest',locations:true});
 const properties=new Set(input.properties),definitions=new Map(),roots=[],lines=new Set(),constants=new Set(),writes=[];
 function visit(node,callback){
  if(!node||typeof node!=='object')return;
  if(node.type)callback(node);
  for(const value of Object.values(node))if(Array.isArray(value))value.forEach(v=>visit(v,callback));else if(value&&typeof value==='object')visit(value,callback);
 }
 function references(node){
  const names=new Set();
  function read(n,parent,key){
   if(!n||typeof n!=='object')return;
   if(n.type==='Identifier'&&!(parent?.type==='MemberExpression'&&key==='property'&&!parent.computed)&&!(parent?.type==='Property'&&key==='key'&&!parent.computed))names.add(n.name);
   for(const [k,value] of Object.entries(n))if(Array.isArray(value))value.forEach(v=>read(v,n,k));else if(value&&typeof value==='object')read(value,n,k);
  }
  read(node);return names;
 }
 visit(ast,node=>{
  if(node.type==='VariableDeclaration'&&node.kind==='const')for(const declaration of node.declarations)if(declaration.id.type==='Identifier')constants.add(declaration.id.name);
  if(node.type==='VariableDeclarator'&&node.id.type==='Identifier'){
   const entries=definitions.get(node.id.name)||[];entries.push(node);definitions.set(node.id.name,entries);
  }
  if(node.type==='AssignmentExpression'&&node.left.type==='Identifier'){
   const entries=definitions.get(node.left.name)||[];entries.push(node);definitions.set(node.left.name,entries);
   writes.push([node.left.name,node]);
  }
  if(node.type==='UpdateExpression'&&node.argument.type==='Identifier')writes.push([node.argument.name,node]);
  if(node.type==='AssignmentExpression'&&node.left.type==='MemberExpression'){
   const member=node.left,property=member.computed?member.property.value:member.property.name;
   if(properties.has(property))roots.push(node);
  }
  if(node.type==='CallExpression'&&node.callee.type==='MemberExpression'){
   const member=node.callee,property=member.computed?member.property.value:member.property.name;
   if(properties.has(property))roots.push(node);
  }
 });
 if(input.constant_assignments)for(const [name,node] of writes)if(constants.has(name))roots.push(node,...(definitions.get(name)||[]));
 const visited=new Set();
 function include(node){
  if(visited.has(node))return;visited.add(node);
  for(let line=node.loc.start.line;line<=node.loc.end.line;line++)lines.add(line);
  for(const name of references(node.type==='CallExpression'?node:node.right??node.init))for(const definition of definitions.get(name)||[])include(definition);
 }
 roots.forEach(include);console.log(JSON.stringify([...lines].sort((a,b)=>a-b)));
}catch(error){console.log('[]');}
'''


def property_dependency_lines(source, properties, *, constant_assignments=False):
    """Locate existing assignments and their local inputs; never suggest code.

    Conservative union across scopes includes ambiguous definitions rather
    than guessing one. Parsing never evaluates model source. Failure returns
    no restriction so the ordinary whole-part repair remains available.
    """
    if not (properties or constant_assignments) or len(source.encode()) > 65536:return []
    try:
        result=subprocess.run(['node','--max-old-space-size=96','-e',PROPERTY_LOCATIONS,str(Path(__file__).parent/'vendor/acorn.cjs')],
            input=json.dumps({'source':source,'properties':sorted(properties),'constant_assignments':constant_assignments}),text=True,encoding='utf-8',
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=3,
            **({'creationflags':0x08000000} if __import__('os').name=='nt' else {}))
        value=json.loads(result.stdout) if not result.returncode else []
        if isinstance(value,list) and all(type(line) is int and 1 <= line <= len(source.splitlines()) for line in value):return value
    except (OSError,subprocess.TimeoutExpired,ValueError):pass
    return []


def failing_lines(source, errors):
    """Locate identifiers named by real checks, without deciding replacements."""
    lines=source.splitlines()
    if any('SyntaxError: await is only valid in async functions' in error for error in errors):
        headers=[i for i,line in enumerate(lines,1) if re.match(r'\s*function\s+[A-Za-z_$][\w$]*\s*\(',line)]
        if len(headers)==1:return headers
    missing=set(re.findall(r'^Define complete named function ([A-Za-z_$][\w$]*)\.$', '\n'.join(errors),re.M))
    if lines and any("SyntaxError: Unexpected token '{'" in error for error in errors) and len(missing)==1:
        name=next(iter(missing))
        if re.fullmatch(r'\s*(?:async\s+)?'+re.escape(name)+r'\s*\([^\n]*\)\s*\{\s*',lines[0]):return [1]
    identifiers=set()
    css_lines=set()
    for error in errors:
        if error.startswith(('Patch rejected:','The patch introduced')):continue
        undefined=re.search(r'Undefined shared field ([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*);',error)
        if undefined:
            path=r'\b'+re.escape(undefined[1])+r'\s*\.\s*'+re.escape(undefined[2])+r'\b'
            targets={i for i,line in enumerate(lines,1) if re.search(path,line)}
            if targets:css_lines.update(targets);continue
        if 'Assignment to constant variable' in error:
            targets=property_dependency_lines(source,set(),constant_assignments=True)
            if targets:css_lines.update(targets);continue
        properties=set(re.findall(r'\b(?:[A-Za-z_$][\w$]*\.)+([A-Za-z_$][\w$]*)\s+expected',error))
        properties.update(re.findall(r'\b(?:[A-Za-z_$][\w$]*\.)+([A-Za-z_$][\w$]*)\s+[A-Za-z_$][\w$]*\s+expected',error))
        # A computed property can be wrong because of its local inputs. Offer
        # the original assignment plus those definitions, not unrelated style
        # or visibility lines. Text-content diagnostics retain their existing
        # targeted route below, including omitted-property fallback.
        if properties-{'textContent','innerText','value','disabled','hidden','busy','loaded'}:
            targets=property_dependency_lines(source,properties)
            if targets:css_lines.update(targets);continue
        # Text/value diagnostics identify a property, not a replacement.
        # Match both dot and bracket access, including local aliases, so an
        # incorrect text assignment does not invite edits to visibility.
        text_properties=set(re.findall(r'\b(?:[A-Za-z_$][\w$]*\.)+(textContent|innerText|value)\s+expected',error))
        if text_properties:
            targets={i for i,line in enumerate(lines,1) if any(re.search(r'(?:\.\s*'+re.escape(prop)+r'\b|\[\s*[\'\"]'+re.escape(prop)+r'[\'\"]\s*\])',line) for prop in text_properties)}
            if targets:css_lines.update(targets);continue
        if error.startswith('Missing CSS selector '):
            import tinycss2
            def collect(rules):
                for rule in rules:
                    if rule.type=='qualified-rule':css_lines.add(rule.source_line)
                    elif rule.type=='at-rule' and rule.content is not None:
                        collect(tinycss2.parse_rule_list(rule.content,skip_comments=True,skip_whitespace=True))
            collect(tinycss2.parse_stylesheet(source,skip_comments=True,skip_whitespace=True))
            if css_lines:continue
        named=set(re.findall(r'\b([A-Za-z_]\w*)\.(?:disabled|hidden|busy|loaded)\s+expected',error))
        named.update(re.findall(r"SyntaxError: Identifier '([A-Za-z_$][\w$]*)' has already been declared",error))
        named.update(re.findall(r'(?:ReferenceError:|Helper behavior failed:|Helper execution failed:)\s*([A-Za-z_$][\w$]*) is not defined\b',error))
        named.update(re.findall(r'Call standalone helper ([A-Za-z_$][\w$]*) directly',error))
        named.update(re.findall(r'\b([A-Za-z_][\w-]*) must (?:have|not have) HTML attribute',error))
        named.update(re.findall(r'\b([A-Za-z_][\w-]*) must not use a self-closing HTML tag',error))
        # A generic structural error can concern another line. Do not prevent
        # that repair merely because a separate error happens to name an ID.
        if not named:return list(range(1,len(lines)+1))
        identifiers.update(named)
    matched=[i for i,line in enumerate(lines,1) if any(re.search(r'(?<![\w-])'+re.escape(name)+r'(?![\w-])',line) for name in identifiers)]
    return sorted(set(matched)|css_lines) or list(range(1,len(lines)+1))


def apply(source, raw):
    """Apply a complete unambiguous patch in memory, or reject all its edits."""
    import jsonschema
    patch=json.loads(projects.unwrap_file(raw,'patch.json'))
    removal=isinstance(patch,dict) and isinstance(patch.get('edits'),list) and any(isinstance(edit,dict) and 'remove' in edit for edit in patch['edits'])
    indexed=isinstance(patch,dict) and isinstance(patch.get('edits'),list) and any(isinstance(edit,dict) and 'line' in edit for edit in patch['edits'])
    try:jsonschema.validate(patch,REMOVAL_SCHEMA if removal else INDEXED_SCHEMA if indexed else SCHEMA)
    except jsonschema.ValidationError as exc:raise ValueError('Invalid source patch schema.') from exc
    result=source
    if removal:
        lines=source.splitlines(keepends=True);seen=set()
        for edit in patch['edits']:
            line,span=edit['line'],edit['remove'];identity=(line,span)
            if line>len(lines) or identity in seen or lines[line-1].count(span)!=1:
                raise ValueError('Removal must match once on an existing original line.')
            seen.add(identity)
        for edit in patch['edits']:lines[edit['line']-1]=lines[edit['line']-1].replace(edit['remove'],'',1)
        result=''.join(lines)
    elif indexed:
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


async def request(source, *, task, errors, contracts, max_tokens=900, diagnose=False, indexed=False, single_line=True):
    # Choices only describe existing text, never the correct replacement. A
    # bounded model can select a line or the whole part without inventing find
    # strings. Exact-match application still validates online/plain JSON output.
    attribute_choices=forbidden_attribute_choices(source,errors)
    examples=prompt_errors(errors)
    check_context={'test_context':'Each input example is a separate invocation of the same function. Fix general behavior; do not combine examples into one invocation or hard-code their values.'} if any(e.startswith('Helper behavior failed: ') for e in errors) else {}
    removal_choices=duplicate_id_choices(source,errors) if not attribute_choices else []
    if attribute_choices:indexed=False
    schema=json.loads(json.dumps(REMOVAL_SCHEMA if removal_choices else INDEXED_SCHEMA if indexed else SCHEMA))
    choices=[source]+[line.strip() for line in source.splitlines() if line.strip() and source.count(line.strip())==1]
    targets=failing_lines(source,errors) if indexed else []
    header_only=targets==[1] and any("SyntaxError: Unexpected token '{'" in e for e in errors) and any(e.startswith('Define complete named function ') for e in errors)
    argument_scope=bool(indexed and targets and len(targets)<len(source.splitlines()) and any(re.search(r'\b(?:[A-Za-z_$][\w$]*\.)+[A-Za-z_$][\w$]*\s+[A-Za-z_$][\w$]*\s+expected',e) for e in errors))
    prompt_source=source.splitlines()[0] if header_only else '\n'.join(source.splitlines()[number-1] for number in targets) if argument_scope else source
    if removal_choices:
        schema['properties']['edits']['items']['enum']=removal_choices
    elif indexed:
        schema['properties']['edits']['items']['properties']['line']['enum']=targets
        schema['properties']['edits']['maxItems']=min(8,len(targets))
        if single_line:schema['properties']['edits']['items']['properties']['replace']['pattern']='^[^\r\n]*$'
    else:
        if attribute_choices:
            choices=attribute_choices
            schema['properties']['edits']['items']['properties']['replace']['const']=''
        schema['properties']['edits']['items']['properties']['find']['enum']=list(dict.fromkeys(choices))
    wire_schema=json.loads(json.dumps(schema))
    # Use the backend's escaped JSON string grammar. A broad replace pattern
    # may swallow JSON quotes; enforce line boundaries after decoding instead.
    wire_schema['properties']['edits']['items'].get('properties',{}).get('replace',{}).pop('pattern',None)
    fmt={'type':'json_schema','json_schema':{'name':'source_patch','strict':True,'schema':wire_schema}} if llm.active_backend()=='local' else 'json'
    reasoning_allowance=512 if llm.active_backend()=='local' and llm.coding_reasoning.get() else 0
    diagnosis=None
    if diagnose and not attribute_choices and not removal_choices:
        diagnosis=await llm.chat([
            {'role':'system','content':'Explain the smallest correction required by the actual validation errors. Read the task and current source. Describe what must change and why, in at most four short sentences. Do not repeat the source or claim it passes. Do not write a patch or code.'},
            {'role':'user','content':json.dumps({'errors':examples,'total_error_count':len(errors),'task':task,'source':source,**check_context},ensure_ascii=False)}
        ],max_tokens=220+reasoning_allowance,temperature=.2)
    # A cut-off diagnosis is evidence of a failed reasoning attempt, not a
    # trustworthy plan to inject into the next request. Preserve it in logs.
    plan=(diagnosis or {}).get('content','')[:1800]
    complete_plan=plan if (diagnosis or {}).get('stats',{}).get('finish_reason') not in ('length','max_tokens') else ''
    if removal_choices:
        system='Remove only the duplicate ID attribute from the wrong element. Select edits from removal_choices verbatim: line is the original line and remove is existing text to delete. Read required controls in contracts to decide which element keeps its ID. Keep every element and all other source unchanged. Return JSON with edits only. Do not remove the ID from the required control.'
    else:
        system=None
    if header_only:
        system='Correct only the JavaScript function declaration header. Return JSON with edits containing exactly one original line number and its corrected single-line replacement. Keep the existing function name, parameters and opening brace. Do not output the function body, closing brace, comments or literal backslash-n sequences.'
        schema['properties']['edits']['minItems']=1
        schema['properties']['edits']['maxItems']=1
    result=await llm.chat([
        {'role':'system','content':system or ('Remove ALL listed forbidden attribute spans from the current source. Return one JSON object with edits, an array of find/replace strings. Copy each find exactly from find_choices and set replace to the empty string. Keep the element, its ID, every other attribute and surrounding source. No replacement markup or other changes. Other errors will be checked again afterwards.' if attribute_choices else 'You repair existing source using numbered lines. The task describes the desired final part, not the patch output format. Return one JSON object with edits, an array of objects containing line (original integer line number) and replace (one corrected line, no newline). Edit only listed failing lines. If a line opens a block, keep it open; do not include its body or closing brace in that replacement. Do not just copy old text or include line numbers in code. Leave correct lines untouched. Write replacements yourself. No markdown or commentary.' if indexed else 'You repair an existing source part using exact text edits. Return one JSON object with edits, an array of objects containing find and replace strings. Copy find text exactly from the supplied source, matching once. Write the corrected replacement yourself. Change only failing lines; preserve correct code. No markdown or commentary.')},
        {'role':'user','content':json.dumps({'source':prompt_source,'errors':['The declaration is missing its JavaScript function keyword.'] if header_only else examples,'total_error_count':len(errors),'contracts':{'scope':'declaration header only; the rest of the source is retained'} if header_only else contracts,'task':'Correct declaration syntax on the supplied header only.' if header_only else task,**check_context,
            **({'source_scope':'Only affected statements and their local inputs are shown; original line numbers remain authoritative. All omitted source is retained unchanged.'} if argument_scope else {}),
            **({'removal_choices':removal_choices} if removal_choices else {'numbered_lines':[{'line':number,'text':line} for number,line in enumerate(source.splitlines(),1) if number in targets]} if indexed else {'find_choices':list(dict.fromkeys(choices))}),**({'repair_plan':complete_plan} if complete_plan else {})},ensure_ascii=False)}
    ],fmt=fmt,max_tokens=max_tokens+reasoning_allowance,temperature=.2)
    if attribute_choices or removal_choices or indexed:
        import jsonschema
        try:
            decoded=json.loads(projects.unwrap_file(result.get('content',''),'patch.json'))
            jsonschema.validate(decoded,schema)
            if indexed and not removal_choices and single_line and any('\n' in edit['replace'] or '\r' in edit['replace'] for edit in decoded['edits']):
                raise ValueError('A single-line replacement cannot contain CR or LF.')
        except (ValueError,jsonschema.ValidationError):result['patch_validation_error']='Indexed edit must use listed lines and respect replacement boundaries.' if indexed and not removal_choices else 'Attribute edit must select listed existing spans and only delete them.'
    if diagnosis:
        result['repair_plan']={'text':plan,'sha256':digest(plan),'model':diagnosis.get('stats',{}).get('served_model',''),
                               'finish_reason':diagnosis.get('stats',{}).get('finish_reason')}
    return result
