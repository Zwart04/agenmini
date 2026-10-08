"""Bounded source-part generation. Every runtime byte comes from the model.

Recipes contain engineering/design instructions, never HTML/CSS/JS templates.
The harness selects model-written nodes/containers and joins them with whitespace.
It can discard unsolicited implementation, but never supplies replacement code.
This is a task-specific coding skill, not evidence of general frontier capability.
"""
import hashlib
import contextvars
import json
import re
import subprocess
import time
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from . import llm, projects, tools, project_checks, project_patches

part_cache = contextvars.ContextVar('model_source_part_cache', default={})
ACORN_PATH=Path(__file__).parent/'vendor'/'acorn.cjs'
HELPER_SELECTOR=r'''
const fs=require('node:fs'),acorn=require(process.argv[1]);
const input=JSON.parse(fs.readFileSync(0,'utf8'));
try{
 const ast=acorn.parse(input.source,{ecmaVersion:'latest',sourceType:'script'});
 if(input.mode==='member_helpers'){
  const known=new Set(input.names),bad=new Set();
  function walk(node){
   if(!node||typeof node!=='object')return;
   if(node.type==='CallExpression'&&node.callee.type==='MemberExpression'){
    const callee=node.callee,name=callee.computed?callee.property.value:callee.property.name;
    if(known.has(name)&&!(callee.object.type==='Identifier'&&['window','globalThis'].includes(callee.object.name)))bad.add(name);
   }
   for(const value of Object.values(node))if(Array.isArray(value))value.forEach(walk);else if(value&&typeof value==='object')walk(value);
  }
  walk(ast);console.log(JSON.stringify({methods:[...bad]}));
 }else if(input.mode==='contracts'){
  const globals={},functions=[],shadowed=new Set();
  function bindingNames(node){
   if(!node)return [];
   if(node.type==='Identifier')return [node.name];
   if(node.type==='RestElement')return bindingNames(node.argument);
   if(node.type==='AssignmentPattern')return bindingNames(node.left);
   if(node.type==='ArrayPattern')return node.elements.flatMap(bindingNames);
   if(node.type==='ObjectPattern')return node.properties.flatMap(p=>bindingNames(p.type==='RestElement'?p.argument:p.value));
   return [];
  }
  function walk(node){
   if(!node||typeof node!=='object')return;
   let names=[];
   if(node.type==='VariableDeclarator')names=bindingNames(node.id);
   if(['FunctionDeclaration','FunctionExpression','ArrowFunctionExpression'].includes(node.type))names=[...bindingNames(node.id),...node.params.flatMap(bindingNames)];
   if(node.type==='CatchClause')names=bindingNames(node.param);
   for(const name of names)if(['app','ui'].includes(name))shadowed.add(name);
   for(const value of Object.values(node))if(Array.isArray(value))value.forEach(walk);else if(value&&typeof value==='object')walk(value);
  }
  walk(ast);
  for(const node of ast.body){
   if(node.type==='VariableDeclaration')for(const declaration of node.declarations){
    if(['app','ui'].includes(declaration.id.name)&&declaration.init?.type==='ObjectExpression')
     globals[declaration.id.name]=declaration.init.properties.filter(p=>p.type==='Property'&&!p.computed).map(p=>p.key.name??p.key.value).filter(k=>typeof k==='string');
    if(declaration.id.type==='Identifier'&&['ArrowFunctionExpression','FunctionExpression'].includes(declaration.init?.type))
     functions.push((declaration.init.async?'async ':'')+'function '+declaration.id.name+'('+declaration.init.params.map(p=>input.source.slice(p.start,p.end)).join(',')+')');
   }
   if(node.type==='FunctionDeclaration')functions.push(input.source.slice(node.start,node.body.start).trim());
  }
  console.log(JSON.stringify({globals,existing_functions:functions,shadowed_state:[...shadowed]}));
 }else{
 const choices=ast.body.filter(n=>n.type==='FunctionDeclaration'&&n.id.name===input.name||n.type==='VariableDeclaration'&&n.declarations.length===1&&n.declarations[0].id.name===input.name&&['ArrowFunctionExpression','FunctionExpression'].includes(n.declarations[0].init?.type));
 const spans=choices.map(n=>input.source.slice(n.start,n.end));
 if(new Set(spans).size>1){console.log(JSON.stringify({ambiguous:true}));}
 else console.log(JSON.stringify({source:spans[0]??input.source}));
 }
}catch(error){console.log(JSON.stringify({source:input.source}));}
'''


def css_source_schema(item):
    """Constrain one rule's syntax/selector, never supply declaration code."""
    selectors=item.get('css_selectors',[])
    if item.get('kind')!='css' or len(selectors)!=1:return None
    whitespace=r'[ \t\r\n]*'
    pattern='^'+whitespace+re.escape(selectors[0])+whitespace+r'\{[^{}]+\}'+whitespace+'$'
    if item.get('media_query'):
        pattern='^'+whitespace+r'@media[ \t\r\n]+'+re.escape(item['media_query'])+whitespace+r'\{'+whitespace+re.escape(selectors[0])+whitespace+r'\{[^{}]+\}'+whitespace+r'\}'+whitespace+'$'
    return {'type':'object','properties':{'source':{'type':'string','pattern':pattern}},
            'required':['source'],'additionalProperties':False}


def html_source_schema(item):
    """Constrain a fragment's root only; its implementation remains model text."""
    root=item.get('root_class')
    if item.get('kind') not in ('node','panel') or not root:return None
    classname=re.escape(root)
    attribute='(?:"'+classname+'(?: [^"<>]*)?"|\''+classname+'(?: [^\'<>]*)?\')'
    allowed_tags=('section','div','aside','header','footer','main')
    tags=(item['root_tag'],) if item.get('root_tag') in (*allowed_tags,'h2') else allowed_tags
    extra='' if item.get('root_only_class') else r'[^>]*'
    body=r'[ \t\r\n]*' if item.get('empty_container') else r'[\x00-\U0010FFFF]*'
    alternatives=[r'<'+tag+r' class='+attribute+extra+r'>'+body+r'</'+tag+r'>' for tag in tags]
    schema={'type':'object','properties':{'source':{'type':'string','pattern':'^(?:'+'|'.join(alternatives)+')$'}},
            'required':['source'],'additionalProperties':False}
    return schema


def js_source_schema(item):
    """Constrain a requested function boundary, never provide its implementation."""
    names=item.get('functions',[])
    if item.get('kind')!='js' or len(names)!=1:return None
    pattern=r'^[ \t\r\n]*(?:async[ \t\r\n]+)?function[ \t\r\n]+'+re.escape(names[0])+r'[ \t\r\n]*\([^)]*\)[ \t\r\n]*\{[\x00-\U0010FFFF]+\}[ \t\r\n]*$'
    return {'type':'object','properties':{'source':{'type':'string','pattern':pattern}},'required':['source'],'additionalProperties':False}


def source_response_schema():
    """Keep encoded JSON valid; code contracts are checked after decoding.

    llama.cpp's pattern converter operates on grammar string bytes. A broad
    multiline source pattern can consume JSON quotes/keys; unsupported regex
    escapes also silently weaken it. Use the builtin escaped string grammar.
    """
    return {'type':'object','properties':{'source':{'type':'string'}},'required':['source'],'additionalProperties':False}


def decode_source(raw,path,source_format='raw'):
    """Decode a model's source string verbatim; never fill in missing code."""
    if source_format=='json_source':
        def unique_pairs(pairs):
            value={}
            for key,item in pairs:
                if key in value:raise ValueError('Duplicate source response key.')
                value[key]=item
            return value
        value=json.loads(raw,object_pairs_hook=unique_pairs)
        if not isinstance(value,dict) or set(value)!={'source'} or not isinstance(value['source'],str):
            raise ValueError('Expected exactly one model-written source string.')
        return value['source']
    if source_format!='raw':raise ValueError('Unknown model source format.')
    return projects.unwrap_file(raw,path)


def select_repeated_function(source,item):
    """Select one exact span only when the entire response repeats that span.

    Different implementations, extra helpers or trailing statements stay
    unchanged and fail normal guards. Syntax and behavior are checked later.
    No braces are guessed and no function body bytes are rewritten.
    """
    names=item.get('functions',[])
    if item.get('kind')!='js' or len(names)!=1:return source
    text=source.strip()
    starts=list(re.finditer(r'(?m)^[ \t]*(?:async\s+)?function\s+'+re.escape(names[0])+r'\s*\(',text))
    if len(starts)<2 or starts[0].start()!=0:return source
    for match in starts[1:]:
        unit=text[:match.start()].rstrip()
        if len(re.findall(r'\bfunction\s+\w+\s*\(',unit))!=1:continue
        if re.fullmatch(re.escape(unit)+r'(?:\s*'+re.escape(unit)+r')+',text):return unit
    return source


def select_model_helper(source,item):
    """Parse without executing model code; select an exact tested helper span."""
    names=item.get('functions',[])
    if item.get('kind')!='js' or len(names)!=1 or not item.get('behavior_checks'):
        return select_repeated_function(source,item)
    if len(source.encode())>65536:return source
    try:
        result=subprocess.run(['node','--max-old-space-size=96','-e',HELPER_SELECTOR,str(ACORN_PATH)],
            input=json.dumps({'source':source,'name':names[0]}),text=True,encoding='utf-8',
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=3,
            **({'creationflags':0x08000000} if __import__('os').name=='nt' else {}))
        if result.returncode:return source
        selected=json.loads(result.stdout)
    except (OSError,subprocess.TimeoutExpired,ValueError):return source
    if selected.get('ambiguous'):raise ValueError('Multiple different requested helper implementations; write a single '+names[0]+'.')
    span=selected.get('source')
    if not isinstance(span,str) or span not in source:return source
    return span


def parsed_js_contracts(source):
    """Read top-level property names through syntax, never execute declarations."""
    if not source.strip():return {'globals':{},'existing_functions':[],'shadowed_state':[]}
    if len(source.encode())>65536:return None
    try:
        result=subprocess.run(['node','--max-old-space-size=96','-e',HELPER_SELECTOR,str(ACORN_PATH)],
            input=json.dumps({'source':source,'mode':'contracts'}),text=True,encoding='utf-8',
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=3,
            **({'creationflags':0x08000000} if __import__('os').name=='nt' else {}))
        if result.returncode:return None
        value=json.loads(result.stdout)
        if set(value)=={'globals','existing_functions','shadowed_state'}:return value
    except (OSError,subprocess.TimeoutExpired,ValueError):pass
    return None


def callable_names(source):
    """Recognize complete top-level callable bindings without rewriting code."""
    parsed=parsed_js_contracts(source)
    if parsed is None:return re.findall(r'\bfunction\s+(\w+)\s*\(',source)
    return [re.search(r'\bfunction\s+(\w+)',signature)[1] for signature in parsed['existing_functions']]


def standalone_helper_errors(source,names):
    """Catch a declared standalone helper incorrectly called as an object method."""
    if not names or len(source.encode())>65536:return []
    try:
        result=subprocess.run(['node','--max-old-space-size=96','-e',HELPER_SELECTOR,str(ACORN_PATH)],
            input=json.dumps({'source':source,'mode':'member_helpers','names':sorted(names)}),text=True,encoding='utf-8',
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=3,
            **({'creationflags':0x08000000} if __import__('os').name=='nt' else {}))
        if result.returncode:return []
        methods=json.loads(result.stdout).get('methods',[])
        return ['Call standalone helper '+name+' directly; it is not an object method.' for name in methods if isinstance(name,str) and name in names]
    except (OSError,subprocess.TimeoutExpired,ValueError):return []


def duplicate_declaration_repairable(source,item,errors):
    """Only a known parser error in complete named JS functions is patchable."""
    if item.get('kind')!='js' or not item.get('functions'):return False
    if not all(re.search(r'\bfunction\s+'+re.escape(fn)+r'\s*\(',source) for fn in item['functions']):return False
    return any(re.search(r"SyntaxError: Identifier '[A-Za-z_$][\w$]*' has already been declared",error) for error in errors)



def missing_async_repairable(source,item,errors):
    """Let the model patch a function header after Node identifies missing async.

    This selects a repair route only; every edit must still pass the complete
    syntax, contract and behavioral checks before it can be accepted.
    """
    if item.get('kind')!='js' or len(item.get('functions',[]))!=1:return False
    name=item['functions'][0]
    if not re.match(r'\s*function\s+'+re.escape(name)+r'\s*\(',source):return False
    if not source.rstrip().endswith('}'):return False
    return any('SyntaxError: await is only valid in async functions' in error for error in errors)


def helper_failure_identity(error):
    """Changing a wrong value is not a new failing case; case coverage is stable."""
    return error.split(' [observed ',1)[0].split('; actual=',1)[0]


def repair_contracts(item):
    """Expose source requirements, not evaluator bookkeeping, to the model."""
    allowed={'functions','parameters','state_writes','system_contract','controls',
             'present_attributes','absent_attributes','direct_parent_classes',
             'required_text','required_tags','required_patterns','root_class',
             'root_only_class','root_tag','empty_container','dom_refs','slots','slot',
             'css_selectors','css_declarations','css_generic_font','media_query'}
    return {key:value for key,value in item.items() if key in allowed}


def part_system(kind):
    instruction={
        'document':'HTML document only. Empty body. No CSS or JavaScript implementation.',
        'node':'One HTML fragment only. No document, styles or scripts.',
        'shell':'Complete HTML document with empty comment slots. No panel implementations or styles.',
        'shellchunk':'One HTML fragment only for this task. No styles or other panels.',
        'panel':'One balanced HTML panel fragment. No document, styles or scripts.',
        'css':'Complete CSS rules only: exact selector, opening brace, property/value declarations with colons and semicolons, then closing brace. A selector alone is not a rule. Match the actual HTML. No markup or JavaScript.',
        'js':'Complete plain browser JavaScript functions exactly as requested, for a classic script. Reuse previous state and call existing helpers. No TypeScript annotations, imports, exports, global redeclarations or copied previous functions.',
        'md':'Short honest Markdown instructions.'
    }[kind]
    return 'You write one source part. Output raw source only, without explanations or fences. '+instruction


def part_contract_errors(source, item):
    """Check declared contracts, without filling in missing model implementations."""
    errors=[]
    if item.get('kind') in ('document','node','panel','shell','shellchunk'):
        doc=projects.Document();doc.feed(source)
        if item.get('empty_container') and not re.fullmatch(r'\s*<(?P<tag>[a-z][\w-]*)\b[^>]*>\s*</(?P=tag)\s*>\s*',source,re.I):
            errors.append('Fragment must be an empty container; write its opening and matching closing tag only.')
        if item.get('kind')=='node' and doc.duplicate_ids:errors.append('Remove duplicate IDs.')
        strict_fragment=item.get('kind') in ('node','panel') and bool(item.get('root_class'))
        if strict_fragment or item.get('direct_parent_classes') or re.search(r'/\s*>',source):
            parents=item.get('direct_parent_classes',{})
            class ParentCheck(HTMLParser):
                stack=[]
                roots=0
                def handle_starttag(self,tag,attrs):
                    attributes=dict(attrs);classes=(attributes.get('class') or '').split()
                    if strict_fragment and item['root_class'] in classes:self.roots+=1
                    if strict_fragment and item['root_class'] in classes and item.get('root_tag') and tag!=item['root_tag']:
                        errors.append('Root class '+item['root_class']+' must use tag '+item['root_tag']+'.')
                    if strict_fragment and item['root_class'] in classes and item.get('root_only_class') and set(attributes)!={'class'}:
                        errors.append('Root class '+item['root_class']+' must have only the class attribute; remove extra attributes from the container.')
                    if strict_fragment and len(attrs)!=len(attributes):errors.append('Duplicate HTML attributes are not allowed in the fragment.')
                    parent_classes=self.stack[-1][1] if self.stack else []
                    for selector,required in parents.items():
                        matches=selector.startswith('#') and attributes.get('id')==selector[1:] or selector.startswith('.') and selector[1:] in classes
                        if matches and required not in parent_classes:errors.append(selector+' must be a direct child of class '+required+'; current parent classes: '+str(parent_classes))
                    if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:self.stack.append((tag,classes))
                def handle_startendtag(self,tag,attrs):
                    if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
                        errors.append((dict(attrs).get('id') or tag)+' must not use a self-closing HTML tag '+tag+'; include explicit </'+tag+'>.')
                    before=len(self.stack);self.handle_starttag(tag,attrs);del self.stack[before:]
                def handle_endtag(self,tag):
                    if strict_fragment and (not self.stack or self.stack[-1][0]!=tag):
                        errors.append('Fragment closing tag '+tag+' does not match the current open element; use explicitly balanced tags.')
                    for index in range(len(self.stack)-1,-1,-1):
                        if self.stack[index][0]==tag:del self.stack[index:];break
            parsed=ParentCheck();parsed.feed(source)
            if strict_fragment:
                if parsed.stack:errors.append('Fragment has unclosed HTML tags: '+', '.join(tag for tag,_ in parsed.stack)+'.')
                if parsed.roots!=1:errors.append('Root class '+item['root_class']+' must occur on exactly one container, not on nested elements.')
        if doc.inline_styles:errors.append('No inline style attributes. Use semantic hidden/disabled attributes; styling belongs in style.css.')
        if doc.inline_handlers:errors.append('No inline event handlers. Event listeners belong in app.js; do not call undeclared helpers from HTML.')
        for ident,attrs in item.get('present_attributes',{}).items():
            for attr in attrs:
                if attr not in doc.attributes.get(ident,{}):errors.append(ident+' must have HTML attribute '+attr+'.')
        for ident,attrs in item.get('absent_attributes',{}).items():
            for attr in attrs:
                if attr in doc.attributes.get(ident,{}):errors.append(ident+' must not have HTML attribute '+attr+'.')
        for tag in item.get('required_tags',[]):
            if not doc.tags.get(tag):errors.append('Required HTML tag '+tag+' is missing; it is used by the stylesheet.')
        if item.get('required_text'):
            texts={};stack=[]
            class ElementText(HTMLParser):
                def handle_starttag(self,tag,attrs):
                    ident=dict(attrs).get('id')
                    if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:stack.append((tag,ident))
                def handle_endtag(self,tag):
                    for index in range(len(stack)-1,-1,-1):
                        if stack[index][0]==tag:del stack[index:];break
                def handle_data(self,data):
                    for _,ident in stack:
                        if ident:texts[ident]=texts.get(ident,'')+data
            ElementText().feed(source)
            for ident,expected in item['required_text'].items():
                actual=' '.join(texts.get(ident,'').split())
                if ' '.join(expected.split()).casefold() not in actual.casefold():errors.append(ident+' must contain actual text '+json.dumps(expected)+', not text in attributes; observed '+json.dumps(actual)+'.')
    if item.get('media_query'):
        import tinycss2
        rules=[r for r in tinycss2.parse_stylesheet(source,skip_comments=True,skip_whitespace=True)]
        expected=item['media_query'].replace(' ','')
        if not rules or any(r.type!='at-rule' or r.lower_at_keyword!='media' or
            tinycss2.serialize(r.prelude).replace(' ','').strip()!=expected for r in rules):
            errors.append('Every mobile rule must be inside @media '+item['media_query']+'; no global rules.')
    for ident in item.get('dom_refs',[]):
        if not re.search(r'[\"\']?\b'+re.escape(ident)+r'[\"\']?\s*:\s*document\.getElementById\(\s*[\"\']'+re.escape(ident)+r'[\"\']\s*\)',source):
            errors.append('Missing ui reference '+ident+' mapped to document.getElementById of the same ID.')
    if item.get('functions'):
        declarations=callable_names(source)
        unexpected=set(declarations)-set(item['functions'])
        if unexpected:errors.append('Do not redefine other helpers: '+', '.join(sorted(unexpected)))
        for fn in item['functions']:
            if declarations.count(fn)>1:errors.append('Duplicate requested function declaration: '+fn)
        comments='\n'.join(re.findall(r'/\*.*?\*/|//[^\n]*',source,re.S))
        if re.search(r'\b(?:simulate|simulation|placeholder|TODO)\b',comments,re.I):
            errors.append('A working implementation is required, not simulated handlers or placeholder code.')
    for pattern in item.get('required_patterns',[]):
        if not re.search(pattern,source):errors.append('Required implementation contract is missing: '+pattern)
    if 'state_writes' in item:
        for field in set(re.findall(r'\bapp\.(\w+)\s*=(?!=)',source))-set(item['state_writes']):
            errors.append('This function must not change app.'+field+'; only permitted state writes: '+', '.join(item['state_writes']))
    if item.get('css_selectors'):
        import tinycss2
        selectors=set()
        def split_selector(value):
            groups=[[]]
            for token in tinycss2.parse_component_value_list(value):
                if token.type=='literal' and token.value==',':groups.append([])
                else:groups[-1].append(token)
            return {' '.join(tinycss2.serialize(tokens).split()) for tokens in groups}
        def collect(rules):
            for rule in rules:
                if rule.type=='qualified-rule':selectors.update(split_selector(tinycss2.serialize(rule.prelude)))
                elif rule.type=='at-rule' and rule.content is not None:
                    collect(tinycss2.parse_rule_list(rule.content,skip_comments=True,skip_whitespace=True))
        collect(tinycss2.parse_stylesheet(source,skip_comments=True,skip_whitespace=True))
        for required in item['css_selectors']:
            if not split_selector(required)<=selectors:
                errors.append('Missing CSS selector '+required+'; preserve its exact punctuation, including IDs (#), classes (.), attribute brackets and descendant spaces.')
        if item.get('css_declarations'):
            expected=item['css_declarations']
            def normalized(value):
                return re.sub(r'\s*([(),])\s*',r'\1',' '.join(value.strip().lower().split()))
            def declarations(rules):
                for rule in rules:
                    if rule.type=='qualified-rule':
                        props={};priorities={}
                        for declaration in tinycss2.parse_declaration_list(rule.content,skip_comments=True,skip_whitespace=True):
                            if declaration.type!='declaration':continue
                            name=declaration.lower_name
                            if priorities.get(name) and not declaration.important:continue
                            priorities[name]=declaration.important
                            props[name]=tinycss2.serialize([token for token in declaration.value if token.type!='comment']).strip()+(' !important' if declaration.important else '')
                        for name,value in expected.items():
                            if normalized(props.get(name,''))!=normalized(value):errors.append('CSS property '+name+' must be '+value+'; observed '+repr(props.get(name,'missing'))+'.')
                        for name in props.keys()-expected.keys():errors.append('Unrequested CSS property '+name+' changes the specified layout; omit it from this part.')
                    elif rule.type=='at-rule' and rule.content is not None:declarations(tinycss2.parse_rule_list(rule.content,skip_comments=True,skip_whitespace=True))
            declarations(tinycss2.parse_stylesheet(source,skip_comments=True,skip_whitespace=True))
        if item.get('css_generic_font'):
            # A syntactically valid multiword custom family can silently fall
            # back to Times. This task explicitly requests a system font.
            families=[];shorthand=False
            expected=set().union(*(split_selector(s) for s in item['css_selectors']))
            for rule in tinycss2.parse_stylesheet(source,skip_comments=True,skip_whitespace=True):
                if rule.type!='qualified-rule' or not expected&split_selector(tinycss2.serialize(rule.prelude)):continue
                for declaration in tinycss2.parse_declaration_list(rule.content,skip_comments=True,skip_whitespace=True):
                    if declaration.type!='declaration':continue
                    if declaration.lower_name=='font':shorthand=True
                    if declaration.lower_name=='font-family':families.append(declaration.value)
            def generic_family(tokens):
                groups=[[]]
                for token in tokens:
                    if token.type=='literal' and token.value==',':groups.append([])
                    elif token.type not in ('whitespace','comment'):groups[-1].append(token)
                return any(len(group)==1 and group[0].type=='ident' and group[0].value.lower() in ('system-ui','sans-serif') for group in groups)
            if shorthand or not families or not all(generic_family(tokens) for tokens in families):
                errors.append('Use separate font-size and font-family declarations. font-family must include unquoted system-ui or sans-serif as a separate comma-delimited family, not a multiword custom font name.')
    return errors


def js_contract_context(prior, relevant=None, functions=None):
    """Supply actual declarations and function signatures, not implementations to copy."""
    parsed=parsed_js_contracts(prior)
    globals_=re.findall(r'\b(?:const|let|var)\s+(app|ui)\s*=\s*\{([^}]+)\}',prior,re.S) if parsed is None else []
    fields=parsed['globals'] if parsed is not None else {name:[quoted or plain for quoted,plain in re.findall(r'''(?:["'](\w+)["']|\b(\w+))\s*:''',body)] for name,body in globals_}
    if relevant:fields={name:[key for key in keys if key in relevant.get(name,keys)] for name,keys in fields.items()}
    signatures=parsed['existing_functions'] if parsed is not None else re.findall(r'\b(?:async\s+)?function\s+\w+\s*\([^)]*\)',prior)
    if functions is not None:
        signatures=[signature for signature in signatures if re.search(r'\bfunction\s+(\w+)',signature)[1] in functions]
    return json.dumps({'globals':fields,'existing_functions':signatures},ensure_ascii=False)


def js_shared_reference_errors(source, prior):
    fields=json.loads(js_contract_context(prior))['globals']
    errors=[]
    parsed=parsed_js_contracts(source)
    if parsed is not None:
        errors += ['Do not shadow existing shared state '+name+'; use the outer declaration.' for name in parsed['shadowed_state'] if name in fields]
    for obj,key in sorted(set(re.findall(r'\b(app|ui)\.(\w+)',source))):
        if obj in fields and key not in fields[obj]:
            errors.append('Undefined shared field '+obj+'.'+key+'; use the declared contracts.')
    for fake in ('createMediaSource','createMediaDestination'):
        if re.search(r'\.'+fake+r'\s*\(',source):
            errors.append('Unsupported Web Audio method '+fake+'; use documented browser APIs.')
    return errors


def js_prompt_context(prior, relevant=None, functions=None):
    """Describe real outer symbols without resembling declarations to copy."""
    contracts=json.loads(js_contract_context(prior,relevant,functions))
    fields=[name+'.'+key for name,keys in contracts['globals'].items() for key in keys]
    signatures=[re.sub(r'^(?:async\s+)?function\s+','',signature) for signature in contracts['existing_functions']]
    return ('Read and write these existing state properties as required by the task. Keep existing app/ui objects:\n'+
            ('\n'.join(fields) or '(none required)')+
            '\nAlready implemented helpers: call these names directly, not app/ui methods. Do not define them again:\n'+
            ('\n'.join(signatures) or '(none required)'))


def validated_helper_context(item, helper_sources, max_chars=2400):
    """Show selected complete model-authored dependencies, never test fixtures.

    Large helpers are omitted whole, rather than truncating their bodies into
    misleading examples. This is opt-in for callers needing implementation
    context; signatures remain available for omitted dependencies.
    """
    allowed=set(item.get('relevant_functions',[]))
    sources=[];used=0
    for name in item.get('include_helper_sources',[]):
        source=helper_sources.get(name) if name in allowed else None
        if not source or source in sources or used+len(source)>max_chars:continue
        sources.append(source);used+=len(source)
    if not sources:return ''
    return 'Already validated model-written helpers. Call them unchanged; do not redefine them:\n'+'\n\n'.join(sources)


def reusable_part(saved, item):
    """Reuse only unmodified model text for an identical task; validate it again."""
    if not saved:return None
    source=saved.get('source','');evidence=saved.get('evidence',{})
    task_hash=hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if evidence.get('task_sha256')!=task_hash or evidence.get('sha256')!=hashlib.sha256(source.encode()).hexdigest():return None
    raw=saved.get('raw_source',source)
    if evidence.get('raw_sha256') and evidence['raw_sha256']!=hashlib.sha256(raw.encode()).hexdigest():return None
    chain=saved.get('repair_chain',[])
    origin=saved.get('origin_raw_source')
    source_format=evidence.get('source_format','raw')
    if chain:
        try:
            def selector(value):
                selected=decode_source(value,item['file'],source_format)
                return document_container(selected) if item.get('kind')=='document' else extract_node(selected,item['root_class']) if item.get('root_class') else select_model_helper(selected,item)
            if project_patches.replay(origin,chain,item['file'],selector)!=source:return None
        except (ValueError,KeyError,TypeError):return None
        if raw!=chain[-1]['raw_patch']:return None
    elif origin is not None:return None
    elif source_format=='json_source' or item.get('kind')=='js':
        try:
            decoded=decode_source(raw,item['file'],source_format)
            if item.get('root_class'):decoded=extract_node(decoded,item['root_class'])
            else:decoded=select_model_helper(decoded,item)
            if decoded!=source:return None
        except (ValueError,TypeError):return None
    return {'content':raw,'stats':{'served_model':evidence.get('model',''),'reused':True},
            'source_format':source_format,
            'initial_selection':evidence.get('initial_selection',''),
            **({'patched_source':source,'repair_chain':chain,'origin_raw_source':origin} if chain else {})}


def extract_node(source,root_class):
    """Select an exact model-written element span, without rewriting its source."""
    offsets=[0]
    for line in source.splitlines(keepends=True):offsets.append(offsets[-1]+len(line))
    class Selector(HTMLParser):
        start=None;end=None;tag='';depth=0
        def source_offset(self):
            line,col=self.getpos();return offsets[line-1]+col
        def handle_starttag(self,tag,attrs):
            if self.end is not None:return
            if self.start is None:
                if tag not in ('div','main','section','aside','header','footer','h2'):return
                if root_class not in dict(attrs).get('class','').split():return
                self.start=self.source_offset();self.tag=tag;self.depth=1
            elif tag==self.tag:self.depth+=1
        def handle_endtag(self,tag):
            if self.start is None or self.end is not None or tag!=self.tag:return
            self.depth-=1
            if self.depth==0:self.end=source.index('>',self.source_offset())+1
    parser=Selector();parser.feed(source)
    if parser.start is None or parser.end is None:raise ValueError('Complete element with class '+root_class+' is required.')
    return source[parser.start:parser.end]


def document_container(source):
    """Keep model-written document tags/assets, discard unsolicited implementations."""
    source=re.sub(r'<style\b[^>]*>.*?</style\s*>','',source,flags=re.I|re.S)
    source=re.sub(r'<script\b([^>]*)>.*?</script\s*>',lambda m:m[0] if re.search(r'\bsrc\s*=',m[1],re.I) else '',source,flags=re.I|re.S)
    body=re.search(r'(<body\b[^>]*>).*?(</body\s*>)',source,re.I|re.S)
    if not body:raise ValueError('A complete body opening/closing pair is required; no tags can be invented by the assembler.')
    return source[:body.start()]+body[1]+'\n'+body[2]+source[body.end():]


def document_asset_errors(source):
    """Check each required asset independently, without generating markup."""
    class Assets(HTMLParser):
        def __init__(self):super().__init__();self.head=False;self.styles=0;self.scripts=0
        def handle_starttag(self,tag,attrs):
            if tag=='head':self.head=True
            values=dict(attrs)
            if self.head and tag=='link' and values.get('href')=='style.css' and 'stylesheet' in (values.get('rel') or '').lower().split():self.styles+=1
            if self.head and tag=='script' and values.get('src')=='app.js' and 'defer' in values and values.get('type','').lower() in ('','text/javascript','application/javascript'):self.scripts+=1
        def handle_endtag(self,tag):
            if tag=='head':self.head=False
    assets=Assets();assets.feed(source)
    return ([f'Expected one stylesheet link href="style.css" in the head; found {assets.styles}.'] if assets.styles!=1 else [])+([f'Expected one classic deferred script src="app.js" in the head; found {assets.scripts}.'] if assets.scripts!=1 else [])


def supports(brief):
    ids=projects.requested_controls(brief)|set(projects.typed_controls(brief))
    known={'fileInput','preview','playBtn','seekInput','startInput','endInput','titleInput','exportBtn','downloadLink','status','timeline'}
    return bool(re.search(r'video\s+editor|editor\s+video',brief,re.I) and re.search(r'export|ekspor',brief,re.I)
                and not re.search(r'backend|login|database|server-side',brief,re.I) and ids<=known)


def assemble(shell,panels):
    for name,source in panels.items():
        marker='<!--panel:'+name+'-->'
        if shell.count(marker)!=1:raise ValueError('Slot panel harus tepat satu: '+name)
        shell=shell.replace(marker,source)
    if '<!--panel:' in shell:raise ValueError('Panel belum lengkap.')
    return shell


def fill_model_container(source,children):
    """Keep the model's exact empty tags and insert only model-written children."""
    match=re.fullmatch(r'\s*(<(?P<tag>[a-z][\w-]*)\b[^>]*>)\s*(</(?P=tag)\s*>)\s*',source,re.I)
    if not match:raise ValueError('Model container must have empty content and matching closing tags.')
    return match[1]+'\n'+'\n'.join(children)+'\n'+match[3]


def compose_document(shell,nodes,panels):
    """Insert model-written nodes into model-written empty containers, no tags added."""
    body=re.search(r'(<body\b[^>]*>)\s*(</body\s*>)',shell,re.I)
    stage=re.fullmatch(r'\s*(<(?:div|main)\b[^>]*>)\s*(</(?:div|main)\s*>)\s*',nodes['stage'],re.I)
    if not body or not stage:raise ValueError('Model document/body and stage must be empty containers.')
    inner='\n'.join(panels[key] for key in ('library','viewer','inspector'))
    timeline=fill_model_container(nodes['timeline'],[nodes['timeline-heading'],nodes['timeline-content']]) if 'timeline' in nodes else panels['timeline']
    markup='\n'.join((nodes['header'],fill_model_container(nodes['stage'],[inner]),timeline,nodes['footer']))
    return shell[:body.start()]+body[1]+'\n'+markup+'\n'+body[2]+shell[body.end():]


async def generate(brief,ctx,on_event=None):
    recipe=json.loads((Path(__file__).parent/'project_recipes'/'video_editor.json').read_text(encoding='utf-8'))
    known_helpers={fn for part in recipe['parts'] for fn in part.get('functions',[])}
    root='project-'+str(time.time_ns());contents={};panels={};nodes={};evidence=[];stats={};shell='';helper_sources={}
    async def emit(kind,value):
        if on_event:await on_event(kind,value)
    for step,item in enumerate(recipe['parts']):
        if item['kind']=='js':item={**item,'generation_contract_revision':2}
        path=item['file'];kind=item['kind'];name=item['name']
        await emit('status',f'Menyusun {name} ({step+1}/{len(recipe["parts"])})â€¦')
        prior=contents.get(path,'')
        context={'owner_goal':brief.split('\n')[0][:250],'architecture':recipe['architecture'],
                 'current_html':contents.get('index.html',shell)[-6500:], 'previous_source':prior[-8500:], 'task':item['task']}
        if kind in ('shell','shellchunk','document','node','panel'):
            context.pop('architecture');context.pop('current_html');context.pop('previous_source')
            context.pop('owner_goal')
            context['required_controls']=item.get('controls',{})
            for key in ('present_attributes','absent_attributes','direct_parent_classes','required_text'):
                if item.get(key):context[key]=item[key]
        elif kind in ('css','md'):context.pop('architecture')
        if kind=='css':
            context.pop('current_html');context.pop('previous_source')
            context.pop('owner_goal')
            context['required_selectors']='\n'.join(item.get('css_selectors',[]))
            context['required_declarations']=item.get('css_declarations',{})
            # The part already names its exact selectors. Unrelated selectors
            # invite small models to style the whole application again.
        if kind=='js':
            if item.get('parameters'):context['parameter_contracts']=item['parameters']
            future=[fn for part in recipe['parts'][step+1:] for fn in part.get('functions',[]) if re.search(r'\b'+re.escape(fn)+r'\b',item['task'])]
            if future:context['future_standalone_helpers']='These names will be implemented by later parts; call them directly, not as app/ui or DOM methods: '+', '.join(dict.fromkeys(future))
            context['architecture']=item.get('context','Use the existing app/ui globals and helpers. Browser-native APIs only; no class or module wrappers.')
            context['previous_source']=js_prompt_context(prior,item.get('relevant_fields'),item.get('relevant_functions'))
            helpers_context=validated_helper_context(item,helper_sources)
            if helpers_context:context['validated_helpers']=helpers_context
            if item.get('include_html') is False:
                context.pop('current_html')
                # A narrow helper contract is already derived from the owner
                # goal. Repeating the whole app request invites a tiny model
                # to rebuild the editor instead of writing this function.
                context.pop('owner_goal')
            else:
                dom=projects.Document();dom.feed(contents.get('index.html',''))
                context['dom_controls']=json.dumps(dom.elements,ensure_ascii=False)
                context.pop('current_html')
        context['task']=context.pop('task')
        request='\n\n'.join(key.upper()+':\n'+(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)) for key,value in context.items())
        system=part_system(kind)
        if kind=='css':
            system+=' Required selectors are literal CSS selectors, not placeholders: '+json.dumps(item.get('css_selectors',[]))+'.'
            if item.get('css_declarations'):system+=' Use exactly the required CSS properties/values; do not add other declarations.'
        if 'state_writes' in item:
            system+=(' Only these app state fields may be assigned: '+', '.join(item['state_writes'])+'. All other app state is read-only. Never reset it.' if item['state_writes'] else ' All app state is read-only in this function. Do not assign or reset app properties.')
        if item.get('system_contract'):system+=' '+item['system_contract']
        source='';repair_chain=[];origin_raw=None;errors=[];source_patchable=False;source_format='raw';initial_selection=''
        for attempt in range(3):
            response=None
            if attempt==0:
                cache=part_cache.get()
                candidates=[cache.get(step),*[saved for index,saved in cache.items() if index!=step]]
                response=next((reused for saved in candidates if (reused:=reusable_part(saved,item)) is not None),None)
            patch_error='';patch_base=None;previous_errors=list(errors)
            if response is None:
                if attempt and source_patchable and (kind in ('css','node','panel','document') or kind=='js' and item.get('functions')) and source and stats.get('finish_reason') not in ('length','max_tokens'):
                    patch_base=source
                    response=await project_patches.request(source,task=item['task'],errors=errors,
                        contracts=(js_prompt_context(prior,item.get('relevant_fields'),item.get('relevant_functions'))+'\n'+validated_helper_context(item,helper_sources)+'\n' if kind=='js' else '')+json.dumps(repair_contracts(item)),
                        max_tokens=min(1100,item.get('tokens',900)),diagnose=attempt>=2,indexed=True,single_line=kind!='document')
                else:
                    schema=None if item.get('raw_source') else css_source_schema(item) or html_source_schema(item) or js_source_schema(item)
                    generation_system=system
                    options={}
                    if schema:
                        generation_system=system.replace('Output raw source only, without explanations or fences.','Return one JSON object with source containing your complete source part as a string. No other keys, fences or explanations.')
                        generation_system+=' The source string must contain only the requested code part. Its structure, syntax and behavior will be checked after decoding.'
                        options['fmt']={'type':'json_schema','json_schema':{'name':kind+'_source' if kind in ('css','js') else 'html_source','strict':True,'schema':source_response_schema()}} if llm.active_backend()=='local' else 'json'
                    response=await llm.chat([{'role':'system','content':generation_system},{'role':'user','content':request}],max_tokens=item.get('tokens',1100)+(512 if llm.coding_reasoning.get() else 0),temperature=.3,**options)
                    response['source_format']='json_source' if schema else 'raw'
            raw=response.get('content','');stats=response.get('stats',{})
            if response.get('patched_source') is not None:
                source=response['patched_source'];repair_chain=response['repair_chain'];origin_raw=response['origin_raw_source'];source_format=response.get('source_format','raw')
                initial_selection=response.get('initial_selection','')
            elif patch_base is not None:
                try:
                    import jsonschema
                    if response.get('patch_validation_error'):raise ValueError(response['patch_validation_error'])
                    if stats.get('finish_reason') in ('length','max_tokens'):raise ValueError('Patch response truncated.')
                    source=project_patches.apply(patch_base,raw)
                    repair_chain.append({'base_sha256':project_patches.digest(patch_base),'raw_patch':raw,
                        'raw_sha256':project_patches.digest(raw),'source_sha256':project_patches.digest(source),
                        'model':stats.get('served_model',''),**({'repair_plan':response['repair_plan']} if response.get('repair_plan') else {})})
                except (ValueError,jsonschema.ValidationError) as exc:
                    source=patch_base;patch_error='Patch rejected: '+str(exc)[:400]
            else:
                source_format=response.get('source_format','raw')
                try:
                    decoded=decode_source(raw,path,source_format)
                    source=select_model_helper(decoded,item)
                    initial_selection=('one exact parsed model-written helper span' if item.get('behavior_checks') else 'one exact function span from byte-identical whole-response repetition') if source!=decoded else ''
                except (ValueError,TypeError) as exc:source='';patch_error='Source response rejected: '+str(exc)[:400]
                repair_chain=[];origin_raw=raw if kind in ('js','css','node','panel','document') else None
            extraction_error=''
            if kind=='document':
                try:source=document_container(source)
                except ValueError as exc:extraction_error=str(exc)
            if item.get('root_class'):
                try:source=extract_node(source,item['root_class'])
                except ValueError as exc:extraction_error=str(exc)
            await emit('source_attempt',{'index':step,'attempt':attempt,'raw_source':raw,'source':source,'stats':stats,'part':name,
                'response_kind':'model_patch' if patch_base is not None else 'reused_model_patch' if response.get('patched_source') is not None else 'source',
                'patch_error':patch_error,'source_format':source_format,'repair_chain':[dict(entry) for entry in repair_chain],
                **({'initial_selection':initial_selection} if initial_selection else {}),
                **({'repair_plan':response['repair_plan']} if response.get('repair_plan') else {})})
            await emit('code',{'path':root+'/'+path,'content':(prior+'\n'+source).strip() if kind not in ('shell','panel') else source,'draft':True,'part':name})
            errors=[]
            syntax_bad=bool(extraction_error)
            missing_structure=False
            if patch_error:errors.extend([patch_error,*previous_errors])
            errors+=part_contract_errors(source,item)
            if kind=='js' and any(error.startswith(('Do not redefine other helpers:','Duplicate requested function declaration:','Do not shadow existing shared state ')) for error in errors):missing_structure=True
            if kind in ('node','panel') and any(error.startswith(('Fragment closing tag ','Fragment has unclosed HTML tags:','Fragment must be an empty container','Root class ','Duplicate HTML attributes')) for error in errors):syntax_bad=True
            if extraction_error:errors.append(extraction_error)
            if not source or stats.get('finish_reason') in ('length','max_tokens'):errors.append('Source empty or truncated; finish the part concisely.')
            if kind in ('shell','shellchunk','document','node'):
                if kind=='shellchunk' and not re.match(r'\s*<(?:!?[a-zA-Z/])',source):errors.append('Output real HTML tags, not a verbal description.')
                if kind=='shellchunk' and step==0 and re.search(r'</(?:body|html)>',source,re.I):errors.append('Opening fragment must stop at opening body; do not close the document yet.')
                if kind in ('shell','document'):
                    html_structure_errors=projects.inspect_html(source,strict=True)['errors']
                    errors+=html_structure_errors
                    syntax_bad=syntax_bad or bool(html_structure_errors)
                if kind=='document' and not re.search(r'<body\b[^>]*>\s*</body\s*>',source,re.I):errors.append('The document body must be empty. Only document structure and asset links belong here.')
                if kind=='node' and item.get('slot')=='stage' and not re.fullmatch(r'\s*<(?:div|main)\b[^>]*>\s*</(?:div|main)\s*>\s*',source,re.I):errors.append('Output one empty stage div/main only.')
                if re.search(r'<style\b',source,re.I):errors.append('No inline CSS. HTML shell only, stylesheet already linked.')
                for slot in (recipe['panels'] if kind=='shell' else item.get('slots',[])):
                    if source.count('<!--panel:'+slot+'-->')!=1:errors.append('Include exactly one comment slot <!--panel:'+slot+'-->.')
                d=projects.Document();d.feed(source)
                if kind=='document':errors+=document_asset_errors(source)
                for ident,expected in item.get('controls',{}).items():
                    if ident not in d.ids or expected.get('tag') and d.elements.get(ident,{}).get('tag')!=expected['tag']:missing_structure=True
                    if any(d.elements.get(ident,{}).get(k)!=v for k,v in expected.items()):errors.append('Required shell control '+ident+' must be '+json.dumps(expected)+'.')
                for resource in d.resources:
                    if resource not in ('style.css','app.js'):errors.append('Only link style.css and deferred app.js; remove '+resource)
            elif kind=='panel':
                d=projects.Document();d.feed(source)
                if re.search(r'<(?:html|head|body|script|style)\b',source,re.I):errors.append('Panel is a fragment only; no document/script/style tags.')
                if d.duplicate_ids:errors.append('Remove duplicate IDs.')
                if d.resources:errors.append('Imported media must start empty, with no sample src or remote assets: '+str(d.resources))
                for ident,expected in item.get('controls',{}).items():
                    if ident not in d.ids or expected.get('tag') and d.elements.get(ident,{}).get('tag')!=expected['tag']:missing_structure=True
                    if any(d.elements.get(ident,{}).get(k)!=v for k,v in expected.items()):errors.append('Required control '+ident+' must be '+json.dumps(expected)+'.')
            elif kind=='css':
                if source.count('{')!=source.count('}') or re.search(r'<[a-z!/]',source,re.I):
                    errors.append('CSS only; close all rules.');syntax_bad=True
                css_errors=projects.inspect_css(source);errors+=css_errors;syntax_bad=syntax_bad or bool(css_errors)
            elif kind=='js':
                shared_errors=js_shared_reference_errors(source,prior)
                errors+=shared_errors
                errors+=standalone_helper_errors(source,known_helpers)
                if any(error.startswith('Do not shadow existing shared state ') for error in shared_errors):missing_structure=True
                checked=await tools._run_sandboxed(['node','--check','--input-type=commonjs'],timeout=15,stdin=(prior+'\n'+source).encode(),project=True)
                if not checked.startswith('[kode keluar 0]'):errors.append(checked[-1000:]);syntax_bad=True
                bindings=callable_names(source)
                for fn in item.get('functions',[]):
                    if fn not in bindings:
                        errors.append('Define complete named function '+fn+'.');missing_structure=True
                if re.search(r'module\.exports|\brequire\s*\(',source):errors.append('Browser source only; no Node exports/require.')
                if not errors:
                    dependencies=item.get('behavior_dependencies',[])
                    missing=[fn for fn in dependencies if fn not in helper_sources]
                    if missing:errors.append('Missing validated helper dependencies: '+', '.join(missing))
                    helper_source='\n'.join(dict.fromkeys(helper_sources[fn] for fn in dependencies if fn in helper_sources))
                    for check in item.get('behavior_checks',[]):
                        if not missing:errors+=await project_checks.inspect_helper(helper_source+'\n'+source,check)
            errors=list(dict.fromkeys(errors))
            old_cases={helper_failure_identity(error) for error in previous_errors if error.startswith('Helper behavior failed: ')}
            new_cases={helper_failure_identity(error) for error in errors if error.startswith('Helper behavior failed: ')}
            old_execution_failed=any(error.startswith('Helper execution failed: ') for error in previous_errors)
            new_execution_failed=any(error.startswith('Helper execution failed: ') for error in errors)
            # A thrown helper has not reached every assertion. Newly reached
            # failures after fixing it are not evidence of a regression.
            regression=bool(patch_base is not None and old_cases and not old_execution_failed and (new_execution_failed or new_cases-old_cases))
            await emit('source_check',{'index':step,'attempt':attempt,'part':name,'source_sha256':project_patches.digest(source),
                'passed':not errors,'errors':errors,'checks':item.get('behavior_checks',[])})
            if (syntax_bad or missing_structure or regression) and patch_base is not None and not patch_error:
                repair_chain.pop();source=patch_base
                if regression:errors=list(dict.fromkeys(previous_errors+['The patch introduced new failing behavior cases. Original source restored; fix existing failures without breaking passing cases.']))
                else:errors=list(dict.fromkeys(previous_errors+['The patch introduced invalid syntax/structure. Original source restored; repair its failing lines.']))
                source_patchable=False
                await emit('code',{'path':root+'/'+path,'content':(prior+'\n'+source).strip(),'draft':True,'part':name,'restored':True})
            else:
                # Exact edits are useful for a valid source with a failing
                # contract. A fragment without a syntax tree needs a complete
                # model-written part, not successive edits to a bare selector.
                async_header=missing_async_repairable(source,item,errors)
                # An unchanged patch is evidence that this edit path stalled.
                # Spend the remaining bounded attempt on fresh model source.
                source_patchable=(not syntax_bad or duplicate_declaration_repairable(source,item,errors) or async_header) and (not missing_structure or async_header) and not patch_error and bool(source)
            if not errors:break
            if attempt==2:raise ValueError(name+' gagal: '+' '.join(errors)[:1700])
            await emit('status','Memperbaiki bagian '+name+'â€¦')
            # Whole-part regeneration must not anchor the model to the very
            # fragment that omitted required structure. Keep that response in
            # the journal, but supply the specification and actual failures.
            # The separate exact-patch path still receives current source.
            request='TASK:\n'+item['task']+'\nCHECK ERRORS:\n'+json.dumps(project_patches.prompt_errors(errors))+'\nTOTAL ERROR COUNT:\n'+str(len(errors))+'\nREQUIRED CONTROLS:\n'+json.dumps(item.get('controls',{}))+'\nEXISTING CONTRACTS:\n'+(js_prompt_context(prior,item.get('relevant_fields'),item.get('relevant_functions')) if kind=='js' else '')+'\nVALIDATED HELPERS:\n'+(validated_helper_context(item,helper_sources) if kind=='js' else '')+'\nPARAMETER CONTRACTS:\n'+json.dumps(item.get('parameters',{}))+'\nFUTURE HELPERS:\n'+(context.get('future_standalone_helpers','') if kind=='js' else '')+'\nWrite a fresh complete source part satisfying the task and fixing every listed error. Include missing elements or functions. Follow the system output format, no labels, errors, explanation or other parts.'
        evidence.append({'part':name,'file':path,'sha256':hashlib.sha256(source.encode()).hexdigest(),'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),'task_sha256':hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'model':stats.get('served_model',''),'reused':stats.get('reused',False),'selection':'document container with unrequested content removed' if kind=='document' else 'exact element span' if item.get('root_class') else 'unwrap fences','assembly':'model source joined with newline'})
        if source_format=='json_source':evidence[-1].update(source_format=source_format,selection='exact element span from model-written JSON source string' if item.get('root_class') else 'exact model-written JSON source string decoded')
        if repair_chain:evidence[-1].update(repair_chain=repair_chain,origin_raw_source=origin_raw,selection='exact model-authored text edits applied to retained model source')
        if initial_selection:
            evidence[-1]['initial_selection']=initial_selection
            if not repair_chain:evidence[-1]['selection']=initial_selection
        await emit('source_part',{'index':step,'source':source,'raw_source':raw,'evidence':evidence[-1],
            **({'origin_raw_source':origin_raw,'repair_chain':repair_chain} if repair_chain else {})})
        if kind=='js':
            for fn in item.get('functions',[]):helper_sources[fn]=source
        if kind in ('shell','document'):shell=source
        elif kind=='node':nodes[item['slot']]=source
        elif kind=='shellchunk':shell+='\n'+source
        elif kind=='panel':
            panels[item['slot']]=source
        else:contents[path]=(prior+'\n'+source).strip()+'\n'
        if kind in ('node','panel') and shell and all(part['slot'] in (nodes if part['kind']=='node' else panels) for part in recipe['parts'] if part['kind'] in ('node','panel')):
            contents['index.html']=compose_document(shell,nodes,panels) if nodes else assemble(shell,panels)
        await emit('code',{'path':root+'/'+path,'content':contents.get(path,source),'draft':True})
    errors=projects.inspect_html(contents['index.html'],required_ids=recipe['required_ids'],strict=True)['errors']
    errors+=projects.project_errors(contents,brief)+await projects.inspect_browser_js(contents)
    if errors:raise ValueError('Kontrak bagian belum benar: '+' '.join(errors)[:2200])
    for resource in projects.inspect_html(contents['index.html'])['resources']:
        if resource not in contents:raise ValueError('Asset lokal belum ada: '+resource)
    folder=tools._workpath(root);folder.mkdir(parents=True)
    for path,code in contents.items():
        await tools.write_file(ctx,root+'/'+path,code)
        if tools._workpath(root+'/'+path).read_text(encoding='utf-8')!=code:raise ValueError('Verifikasi sumber gagal: '+path)
    provenance={'method':'model-written source parts; no runtime templates or evaluator source fixes','parts':evidence,
                'files':{p:hashlib.sha256(v.encode()).hexdigest() for p,v in contents.items()},'backend':llm.active_backend(),'behavior_verified':False}
    (folder/'generation.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    bundle=root+'/project.zip'
    with zipfile.ZipFile(tools._workpath(bundle),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in [*contents,'generation.json']:archive.write(folder/path,path)
    with zipfile.ZipFile(tools._workpath(bundle)) as archive:
        if archive.testzip():raise ValueError('ZIP rusak.')
    ctx.attachments=[p for p in ctx.attachments if not p.startswith(root+'/')]+[bundle];ctx.served_model=stats.get('served_model','')
    return 'Kode editor ditulis model per bagian; ZIP diperiksa. Buka index.html. Fungsi browser masih harus diuji nyata.\nBerkas: '+bundle
