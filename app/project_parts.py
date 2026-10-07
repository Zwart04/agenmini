"""Bounded source-part generation. Every runtime byte comes from the model.

Recipes contain engineering/design instructions, never HTML/CSS/JS templates.
Only model-generated comment slots and whitespace are assembled by the harness.
This is a task-specific coding skill, not evidence of general frontier capability.
"""
import hashlib
import json
import re
import time
import zipfile
from pathlib import Path
from . import llm, projects, tools


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


async def generate(brief,ctx,on_event=None):
    recipe=json.loads((Path(__file__).parent/'project_recipes'/'video_editor.json').read_text(encoding='utf-8'))
    root='project-'+str(time.time_ns());contents={};panels={};evidence=[];stats={};shell=''
    async def emit(kind,value):
        if on_event:await on_event(kind,value)
    for step,item in enumerate(recipe['parts']):
        path=item['file'];kind=item['kind'];name=item['name']
        await emit('status',f'Menyusun {name} ({step+1}/{len(recipe["parts"])})…')
        prior=contents.get(path,'')
        context={'owner_goal':brief.split('\n')[0][:250],'architecture':recipe['architecture'],'task':item['task'],
                 'current_html':contents.get('index.html',shell)[-6500:], 'previous_source':prior[-8500:]}
        if kind in ('shell','shellchunk','panel'):
            context.pop('architecture');context.pop('current_html');context.pop('previous_source')
            context.pop('owner_goal')
            context['required_controls']=item.get('controls',{})
        elif kind in ('css','md'):context.pop('architecture')
        request='\n\n'.join(key.upper()+':\n'+(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)) for key,value in context.items())
        language='HTML' if kind in ('shell','shellchunk','panel') else 'JavaScript' if kind=='js' else 'CSS' if kind=='css' else 'Markdown'
        system=('Follow CURRENT TASK exactly. Output only raw '+language+' source, no explanations or fences. '
                'Do not implement other parts of the app. Keep this part small. '+
                ('HTML fragment only, exactly this task; do not add CSS or other panels.' if kind=='shellchunk' else
                 'The shell is a complete document with EMPTY comment slots, never panel controls.' if kind=='shell' else
                 'One balanced panel fragment only; no document, CSS or JavaScript.' if kind=='panel' else
                 'CSS rules only for this task. Match actual HTML. No invented selectors or markup.' if kind=='css' else
                 'Complete named JavaScript functions only as requested. Reuse actual previous code/state. No fake APIs, placeholders, Node exports, global redeclarations or copied previous functions.' if kind=='js' else
                 'Short honest Markdown only.'))
        source=''
        for attempt in range(2):
            response=await llm.chat([{'role':'system','content':system},{'role':'user','content':request}],max_tokens=item.get('tokens',1100)+(512 if llm.coding_reasoning.get() else 0),temperature=.6)
            source=projects.unwrap_file(response.get('content',''),path);stats=response.get('stats',{})
            await emit('code',{'path':root+'/'+path,'content':(prior+'\n'+source).strip() if kind not in ('shell','panel') else source,'draft':True,'part':name})
            errors=[]
            if not source or stats.get('finish_reason') in ('length','max_tokens'):errors.append('Source empty or truncated; finish the part concisely.')
            if kind in ('shell','shellchunk'):
                if kind=='shellchunk' and not re.match(r'\s*<(?:!?[a-zA-Z/])',source):errors.append('Output real HTML tags, not a verbal description.')
                if kind=='shellchunk' and step==0 and re.search(r'</(?:body|html)>',source,re.I):errors.append('Opening fragment must stop at opening body; do not close the document yet.')
                if kind=='shell':errors+=projects.inspect_html(source,strict=True)['errors']
                if re.search(r'<style\b',source,re.I):errors.append('No inline CSS. HTML shell only, stylesheet already linked.')
                for slot in (recipe['panels'] if kind=='shell' else item.get('slots',[])):
                    if source.count('<!--panel:'+slot+'-->')!=1:errors.append('Include exactly one comment slot <!--panel:'+slot+'-->.')
                d=projects.Document();d.feed(source)
                for ident,expected in item.get('controls',{}).items():
                    if any(d.elements.get(ident,{}).get(k)!=v for k,v in expected.items()):errors.append('Required shell control '+ident+' must be '+json.dumps(expected)+'.')
                for resource in d.resources:
                    if resource not in ('style.css','app.js'):errors.append('Only link style.css and deferred app.js; remove '+resource)
            elif kind=='panel':
                d=projects.Document();d.feed(source)
                if re.search(r'<(?:html|head|body|script|style)\b',source,re.I):errors.append('Panel is a fragment only; no document/script/style tags.')
                if d.duplicate_ids:errors.append('Remove duplicate IDs.')
                for ident,expected in item.get('controls',{}).items():
                    if any(d.elements.get(ident,{}).get(k)!=v for k,v in expected.items()):errors.append('Required control '+ident+' must be '+json.dumps(expected)+'.')
            elif kind=='css':
                if source.count('{')!=source.count('}') or re.search(r'<[a-z!/]',source,re.I):errors.append('CSS only; close all rules.')
            elif kind=='js':
                checked=await tools._run_sandboxed(['node','--check','--input-type=commonjs'],timeout=15,stdin=(prior+'\n'+source).encode(),project=True)
                if not checked.startswith('[kode keluar 0]'):errors.append(checked[-1000:])
                for fn in item.get('functions',[]):
                    if not re.search(r'\bfunction\s+'+re.escape(fn)+r'\s*\(',source):errors.append('Define complete named function '+fn+'.')
                if re.search(r'module\.exports|\brequire\s*\(',source):errors.append('Browser source only; no Node exports/require.')
            if not errors:break
            if attempt:raise ValueError(name+' gagal: '+' '.join(errors)[:1700])
            await emit('status','Memperbaiki bagian '+name+'…')
            request='TASK:\n'+item['task']+'\nCHECK ERRORS:\n'+json.dumps(errors)+'\nRewrite only this part from scratch. Be concise. No other parts or styling.'
        evidence.append({'part':name,'file':path,'sha256':hashlib.sha256(source.encode()).hexdigest(),'model':stats.get('served_model',''),'assembly':'slot replacement' if kind=='panel' else 'model source joined with newline'})
        await emit('source_part',{'index':step,'source':source,'evidence':evidence[-1]})
        if kind=='shell':shell=source
        elif kind=='shellchunk':shell+='\n'+source
        elif kind=='panel':
            panels[item['slot']]=source
            if len(panels)==len(recipe['panels']):contents['index.html']=assemble(shell,panels)
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
