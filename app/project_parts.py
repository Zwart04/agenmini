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
import time
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from . import llm, projects, tools, project_checks, project_patches

part_cache = contextvars.ContextVar('model_source_part_cache', default={})


def part_system(kind):
    instruction={
        'document':'HTML document only. Empty body. No CSS or JavaScript implementation.',
        'node':'One HTML fragment only. No document, styles or scripts.',
        'shell':'Complete HTML document with empty comment slots. No panel implementations or styles.',
        'shellchunk':'One HTML fragment only for this task. No styles or other panels.',
        'panel':'One balanced HTML panel fragment. No document, styles or scripts.',
        'css':'Complete CSS rules only: exact selector, opening brace, property/value declarations with colons and semicolons, then closing brace. A selector alone is not a rule. Match the actual HTML. No markup or JavaScript.',
        'js':'Complete JavaScript functions exactly as requested. Reuse previous state. No global redeclarations, Node exports or copied previous functions.',
        'md':'Short honest Markdown instructions.'
    }[kind]
    return 'You write one source part. Output raw source only, without explanations or fences. '+instruction


def part_contract_errors(source, item):
    """Check declared contracts, without filling in missing model implementations."""
    errors=[]
    if item.get('kind') in ('document','node','panel','shell','shellchunk'):
        doc=projects.Document();doc.feed(source)
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
        unexpected=set(re.findall(r'\bfunction\s+(\w+)\s*\(',source))-set(item['functions'])
        if unexpected:errors.append('Do not redefine other helpers: '+', '.join(sorted(unexpected)))
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


def js_contract_context(prior, relevant=None):
    """Supply actual declarations and function signatures, not implementations to copy."""
    globals_=re.findall(r'\b(?:const|let|var)\s+(app|ui)\s*=\s*\{([^}]+)\}',prior,re.S)
    fields={name:[quoted or plain for quoted,plain in re.findall(r'''(?:["'](\w+)["']|\b(\w+))\s*:''',body)] for name,body in globals_}
    if relevant:fields={name:[key for key in keys if key in relevant.get(name,keys)] for name,keys in fields.items()}
    signatures=re.findall(r'\b(?:async\s+)?function\s+\w+\s*\([^)]*\)',prior)
    return json.dumps({'globals':fields,'existing_functions':signatures},ensure_ascii=False)


def js_shared_reference_errors(source, prior):
    fields=json.loads(js_contract_context(prior))['globals']
    errors=[]
    for obj,key in sorted(set(re.findall(r'\b(app|ui)\.(\w+)',source))):
        if obj in fields and key not in fields[obj]:
            errors.append('Undefined shared field '+obj+'.'+key+'; use the declared contracts.')
    for fake in ('createMediaSource','createMediaDestination'):
        if re.search(r'\.'+fake+r'\s*\(',source):
            errors.append('Unsupported Web Audio method '+fake+'; use documented browser APIs.')
    return errors


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
    if chain:
        try:
            selector=(lambda value:extract_node(value,item['root_class'])) if item.get('root_class') else None
            if project_patches.replay(origin,chain,item['file'],selector)!=source:return None
        except (ValueError,KeyError,TypeError):return None
        if raw!=chain[-1]['raw_patch']:return None
    elif origin is not None:return None
    return {'content':raw,'stats':{'served_model':evidence.get('model',''),'reused':True},
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
                if tag not in ('div','main','section','aside','header','footer'):return
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


def compose_document(shell,nodes,panels):
    """Insert model-written nodes into model-written empty containers, no tags added."""
    body=re.search(r'(<body\b[^>]*>)\s*(</body\s*>)',shell,re.I)
    stage=re.fullmatch(r'\s*(<(?:div|main)\b[^>]*>)\s*(</(?:div|main)\s*>)\s*',nodes['stage'],re.I)
    if not body or not stage:raise ValueError('Model document/body and stage must be empty containers.')
    inner='\n'.join(panels[key] for key in ('library','viewer','inspector'))
    markup='\n'.join((nodes['header'],stage[1]+'\n'+inner+'\n'+stage[2],panels['timeline'],nodes['footer']))
    return shell[:body.start()]+body[1]+'\n'+markup+'\n'+body[2]+shell[body.end():]


async def generate(brief,ctx,on_event=None):
    recipe=json.loads((Path(__file__).parent/'project_recipes'/'video_editor.json').read_text(encoding='utf-8'))
    root='project-'+str(time.time_ns());contents={};panels={};nodes={};evidence=[];stats={};shell=''
    async def emit(kind,value):
        if on_event:await on_event(kind,value)
    for step,item in enumerate(recipe['parts']):
        if item['kind']=='js':item={**item,'generation_contract_revision':2}
        path=item['file'];kind=item['kind'];name=item['name']
        await emit('status',f'Menyusun {name} ({step+1}/{len(recipe["parts"])})…')
        prior=contents.get(path,'')
        context={'owner_goal':brief.split('\n')[0][:250],'architecture':recipe['architecture'],
                 'current_html':contents.get('index.html',shell)[-6500:], 'previous_source':prior[-8500:], 'task':item['task']}
        if kind in ('shell','shellchunk','document','node','panel'):
            context.pop('architecture');context.pop('current_html');context.pop('previous_source')
            context.pop('owner_goal')
            context['required_controls']=item.get('controls',{})
        elif kind in ('css','md'):context.pop('architecture')
        if kind=='css':
            context.pop('current_html');context.pop('previous_source')
            context.pop('owner_goal')
            context['required_selectors']=item.get('css_selectors',[])
            # The part already names its exact selectors. Unrelated selectors
            # invite small models to style the whole application again.
        if kind=='js':
            context['architecture']=item.get('context','Use the existing app/ui globals and helpers. Browser-native APIs only; no class or module wrappers.')
            context['previous_source']=js_contract_context(prior,item.get('relevant_fields'))
            if item.get('include_html') is False:context.pop('current_html')
            else:
                dom=projects.Document();dom.feed(contents.get('index.html',''))
                context['dom_controls']=json.dumps(dom.elements,ensure_ascii=False)
                context.pop('current_html')
        context['task']=context.pop('task')
        request='\n\n'.join(key.upper()+':\n'+(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)) for key,value in context.items())
        system=part_system(kind)
        if kind=='css':
            system+=' Required selectors are literal CSS selectors, not placeholders: '+json.dumps(item.get('css_selectors',[]))+'.'
        if 'state_writes' in item:
            system+=' Only these app state fields may be assigned: '+', '.join(item['state_writes'])+'. All other app state is read-only. Never reset it.'
        if item.get('system_contract'):system+=' '+item['system_contract']
        source='';repair_chain=[];origin_raw=None;errors=[];source_patchable=False
        for attempt in range(3):
            response=reusable_part(part_cache.get().get(step),item) if attempt==0 else None
            patch_error='';patch_base=None;previous_errors=list(errors)
            if response is None:
                if attempt and source_patchable and (kind in ('css','node','panel') or kind=='js' and item.get('functions')) and source and stats.get('finish_reason') not in ('length','max_tokens'):
                    patch_base=source
                    response=await project_patches.request(source,task=item['task'],errors=errors,
                        contracts=(js_contract_context(prior,item.get('relevant_fields'))+'\n' if kind=='js' else '')+json.dumps({key:value for key,value in item.items() if key not in ('task','tokens','file','kind','name')}),
                        max_tokens=min(1100,item.get('tokens',900)),diagnose=attempt>=2,indexed=True)
                else:
                    response=await llm.chat([{'role':'system','content':system},{'role':'user','content':request}],max_tokens=item.get('tokens',1100)+(512 if llm.coding_reasoning.get() else 0),temperature=.3)
            raw=response.get('content','');stats=response.get('stats',{})
            if response.get('patched_source') is not None:
                source=response['patched_source'];repair_chain=response['repair_chain'];origin_raw=response['origin_raw_source']
            elif patch_base is not None:
                try:
                    import jsonschema
                    if stats.get('finish_reason') in ('length','max_tokens'):raise ValueError('Patch response truncated.')
                    source=project_patches.apply(patch_base,raw)
                    repair_chain.append({'base_sha256':project_patches.digest(patch_base),'raw_patch':raw,
                        'raw_sha256':project_patches.digest(raw),'source_sha256':project_patches.digest(source),
                        'model':stats.get('served_model',''),**({'repair_plan':response['repair_plan']} if response.get('repair_plan') else {})})
                except (ValueError,jsonschema.ValidationError) as exc:
                    source=patch_base;patch_error='Patch rejected: '+str(exc)[:400]
            else:
                source=projects.unwrap_file(raw,path);repair_chain=[];origin_raw=raw if kind in ('js','css','node','panel') else None
            extraction_error=''
            if kind=='document':
                try:source=document_container(source)
                except ValueError as exc:extraction_error=str(exc)
            if item.get('root_class'):
                try:source=extract_node(source,item['root_class'])
                except ValueError as exc:extraction_error=str(exc)
            await emit('source_attempt',{'index':step,'attempt':attempt,'raw_source':raw,'source':source,'stats':stats,'part':name,
                'response_kind':'model_patch' if patch_base is not None else 'reused_model_patch' if response.get('patched_source') is not None else 'source',
                'patch_error':patch_error,'repair_chain':[dict(entry) for entry in repair_chain],
                **({'repair_plan':response['repair_plan']} if response.get('repair_plan') else {})})
            await emit('code',{'path':root+'/'+path,'content':(prior+'\n'+source).strip() if kind not in ('shell','panel') else source,'draft':True,'part':name})
            errors=[]
            syntax_bad=bool(extraction_error)
            missing_structure=False
            if patch_error:errors.extend([patch_error,*previous_errors])
            errors+=part_contract_errors(source,item)
            if extraction_error:errors.append(extraction_error)
            if not source or stats.get('finish_reason') in ('length','max_tokens'):errors.append('Source empty or truncated; finish the part concisely.')
            if kind in ('shell','shellchunk','document','node'):
                if kind=='shellchunk' and not re.match(r'\s*<(?:!?[a-zA-Z/])',source):errors.append('Output real HTML tags, not a verbal description.')
                if kind=='shellchunk' and step==0 and re.search(r'</(?:body|html)>',source,re.I):errors.append('Opening fragment must stop at opening body; do not close the document yet.')
                if kind in ('shell','document'):errors+=projects.inspect_html(source,strict=True)['errors']
                if kind=='document' and not re.search(r'<body\b[^>]*>\s*</body\s*>',source,re.I):errors.append('The document body must be empty. Only document structure and asset links belong here.')
                if kind=='node' and item.get('slot')=='stage' and not re.fullmatch(r'\s*<(?:div|main)\b[^>]*>\s*</(?:div|main)\s*>\s*',source,re.I):errors.append('Output one empty stage div/main only.')
                if re.search(r'<style\b',source,re.I):errors.append('No inline CSS. HTML shell only, stylesheet already linked.')
                for slot in (recipe['panels'] if kind=='shell' else item.get('slots',[])):
                    if source.count('<!--panel:'+slot+'-->')!=1:errors.append('Include exactly one comment slot <!--panel:'+slot+'-->.')
                d=projects.Document();d.feed(source)
                if kind=='document' and not {'style.css','app.js'}<=set(d.resources):errors.append('Include stylesheet link href="style.css" and deferred script src="app.js" in the head.')
                for ident,expected in item.get('controls',{}).items():
                    if ident not in d.ids:missing_structure=True
                    if any(d.elements.get(ident,{}).get(k)!=v for k,v in expected.items()):errors.append('Required shell control '+ident+' must be '+json.dumps(expected)+'.')
                for resource in d.resources:
                    if resource not in ('style.css','app.js'):errors.append('Only link style.css and deferred app.js; remove '+resource)
            elif kind=='panel':
                d=projects.Document();d.feed(source)
                if re.search(r'<(?:html|head|body|script|style)\b',source,re.I):errors.append('Panel is a fragment only; no document/script/style tags.')
                if d.duplicate_ids:errors.append('Remove duplicate IDs.')
                if d.resources:errors.append('Imported media must start empty, with no sample src or remote assets: '+str(d.resources))
                for ident,expected in item.get('controls',{}).items():
                    if ident not in d.ids:missing_structure=True
                    if any(d.elements.get(ident,{}).get(k)!=v for k,v in expected.items()):errors.append('Required control '+ident+' must be '+json.dumps(expected)+'.')
            elif kind=='css':
                if source.count('{')!=source.count('}') or re.search(r'<[a-z!/]',source,re.I):
                    errors.append('CSS only; close all rules.');syntax_bad=True
                css_errors=projects.inspect_css(source);errors+=css_errors;syntax_bad=syntax_bad or bool(css_errors)
            elif kind=='js':
                errors+=js_shared_reference_errors(source,prior)
                checked=await tools._run_sandboxed(['node','--check','--input-type=commonjs'],timeout=15,stdin=(prior+'\n'+source).encode(),project=True)
                if not checked.startswith('[kode keluar 0]'):errors.append(checked[-1000:]);syntax_bad=True
                for fn in item.get('functions',[]):
                    if not re.search(r'\bfunction\s+'+re.escape(fn)+r'\s*\(',source):
                        errors.append('Define complete named function '+fn+'.');missing_structure=True
                if re.search(r'module\.exports|\brequire\s*\(',source):errors.append('Browser source only; no Node exports/require.')
                if not errors:
                    for check in item.get('behavior_checks',[]):
                        errors+=await project_checks.inspect_helper(source,check)
            errors=list(dict.fromkeys(errors))
            old_cases={error for error in previous_errors if error.startswith('Helper behavior failed: ')}
            new_cases={error for error in errors if error.startswith('Helper behavior failed: ')}
            regression=bool(patch_base is not None and old_cases and new_cases-old_cases)
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
                source_patchable=not syntax_bad and not missing_structure and not patch_error and bool(source)
            if not errors:break
            if attempt==2:raise ValueError(name+' gagal: '+' '.join(errors)[:1700])
            await emit('status','Memperbaiki bagian '+name+'…')
            # Whole-part regeneration must not anchor the model to the very
            # fragment that omitted required structure. Keep that response in
            # the journal, but supply the specification and actual failures.
            # The separate exact-patch path still receives current source.
            request='TASK:\n'+item['task']+'\nCHECK ERRORS:\n'+json.dumps(errors)+'\nREQUIRED CONTROLS:\n'+json.dumps(item.get('controls',{}))+'\nEXISTING CONTRACTS:\n'+(js_contract_context(prior,item.get('relevant_fields')) if kind=='js' else '')+'\nWrite a fresh complete source part satisfying the task and fixing every listed error. Include missing elements or functions. Return raw source only, no labels, errors, explanation or other parts.'
        evidence.append({'part':name,'file':path,'sha256':hashlib.sha256(source.encode()).hexdigest(),'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),'task_sha256':hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'model':stats.get('served_model',''),'reused':stats.get('reused',False),'selection':'document container with unrequested content removed' if kind=='document' else 'exact element span' if item.get('root_class') else 'unwrap fences','assembly':'model source joined with newline'})
        if repair_chain:evidence[-1].update(repair_chain=repair_chain,origin_raw_source=origin_raw,selection='exact model-authored text edits applied to retained model source')
        await emit('source_part',{'index':step,'source':source,'raw_source':raw,'evidence':evidence[-1],
            **({'origin_raw_source':origin_raw,'repair_chain':repair_chain} if repair_chain else {})})
        if kind in ('shell','document'):shell=source
        elif kind=='node':nodes[item['slot']]=source
        elif kind=='shellchunk':shell+='\n'+source
        elif kind=='panel':
            panels[item['slot']]=source
            if len(panels)==len(recipe['panels']):contents['index.html']=compose_document(shell,nodes,panels) if nodes else assemble(shell,panels)
        else:contents[path]=(prior+'\n'+source).strip()+'\n'
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
