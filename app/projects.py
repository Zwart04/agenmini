"""Multi-file frontend project generation, real artifact checks and ZIP delivery."""
import ast
import json
import re
import zipfile
from pathlib import PurePosixPath
from html.parser import HTMLParser
from . import llm,structured


def project_request(text):
    from .coding import functional_request
    return bool(re.search(r'\b(buat(?:kan|in)?|bikin(?:kan)?|build|create|generate|kembangkan)\b',text,re.I)
                and (functional_request(text) or re.search(r'\b(game|permainan|web\s*app|aplikasi|project|proyek)\b',text,re.I)))


class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=set();self.elements={};self.attributes={};self.inline_styles=0;self.duplicate_ids=set();self.classes=set();self.anchors=[];self.resources=[];self.classic_scripts=[];self.tags={};self.viewport=False;self.title=False;self.scripts=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.tags[tag]=self.tags.get(tag,0)+1
        if 'style' in a:self.inline_styles+=1
        if a.get('id'):
            if a['id'] in self.ids:self.duplicate_ids.add(a['id'])
            self.ids.add(a['id'])
            self.elements[a['id']]={'tag':tag,'type':a.get('type','text' if tag=='input' else '')}
            self.attributes[a['id']]=a
        self.classes.update(a.get('class','').split())
        if tag=='meta' and a.get('name','').lower()=='viewport':self.viewport=True
        if tag=='title':self.title=True
        if tag=='a' and a.get('href','').startswith('#') and 'download' not in a:self.anchors.append(a['href'][1:])
        if tag in ('script','link','img','video','audio','source'):
            url=a.get('src') or (a.get('href') if tag=='link' else None)
            if url:self.resources.append(url)
        if tag=='script':self.scripts+=1
        if tag=='script' and a.get('src') and a.get('type','').lower() in ('','text/javascript','application/javascript'):self.classic_scripts.append(a['src'])


def inspect_html(html,required_ids=(),strict=False,required_controls=None):
    d=Document();d.feed(html);d.close();errors=[]
    for name in sorted(d.duplicate_ids):errors.append('ID HTML berulang: '+name)
    for tag in ('html','head','body','title'):
        if not d.tags.get(tag):errors.append('Tag '+tag+' belum ada.')
    if not d.viewport:errors.append('Meta viewport belum ada.')
    if not re.search(r'</html\s*>',html,re.I):errors.append('Dokumen belum ditutup.')
    for target in d.anchors:
        if not target or target not in d.ids:errors.append('Tautan bagian tidak memiliki tujuan: #'+target+'. For a file download, use an anchor with download attribute and no href until the generated blob is ready; do not use a placeholder navigation link.')
    for tag in ('script','style'):
        if len(re.findall('<'+tag+r'\b',html,re.I))!=len(re.findall('</'+tag+r'\s*>',html,re.I)):errors.append(tag+' belum lengkap.')
    if re.search(r'lorem ipsum|YOUR_API_KEY|TODO:\s*implement',html,re.I):errors.append('Placeholder implementasi masih tersisa.')
    for name in required_ids:
        if name not in d.ids:errors.append('Kontrol yang diminta belum ada: '+name)
    for name,expected in (required_controls or {}).items():
        actual=d.elements.get(name,{})
        if any(actual.get(key)!=value for key,value in expected.items()):errors.append('Jenis kontrol tidak sesuai: '+name+' harus '+json.dumps(expected))
    if strict and (re.search(r'^\s*```',html,re.M) or not re.match(r'\s*(?:<!doctype\b|<html\b|<!--)',html,re.I)):
        errors.append('HTML bercampur label/Markdown atau berkas lain. Output hanya dokumen HTML, bukan seluruh proyek.')
    return {'ok':not errors,'errors':errors,'sections':d.tags.get('section',0),'buttons':d.tags.get('button',0),
            'scripts':d.scripts,'bytes':len(html.encode()),'resources':d.resources,
            'note':'Pemeriksaan struktur dan tautan. Tampilan/interaksi perlu diuji browser; backend hanya dianggap terhubung bila diuji nyata.'}


def inspect_css(source):
    """Syntax guard, not a claim about browser layout or supported property values."""
    import tinycss2
    errors=[]
    def visit(entries):
        for entry in entries:
            if entry.type=='error':errors.append(f'CSS line {entry.source_line}: {entry.message}')
            elif entry.type in ('qualified-rule','at-rule') and entry.content is not None:
                visit(tinycss2.parse_blocks_contents(entry.content,skip_comments=True,skip_whitespace=True))
            elif entry.type=='declaration':
                if not entry.name.startswith('--') and any(t.type=='literal' and t.value==':' for t in entry.value):
                    errors.append(f'CSS line {entry.source_line}: extra colon in {entry.name}; separate declarations with semicolons, no prose in values.')
                for token in entry.value:
                    if token.type=='error':errors.append(f'CSS line {token.source_line}: {token.message}')
    visit(tinycss2.parse_stylesheet(source,skip_comments=True,skip_whitespace=True))
    return errors[:12]


async def inspect_inline_js(html):
    from . import tools
    errors=[]
    for attrs,script in re.findall(r'<script\b([^>]*)>(.*?)</script\s*>',html,re.I|re.S):
        if not script.strip() or re.search(r'type=[\"\']application/',attrs,re.I):continue
        kind='module' if re.search(r'type=[\"\']module',attrs,re.I) else 'commonjs'
        checked=await tools._run_sandboxed(['node','--check','--input-type='+kind],timeout=10,stdin=script.encode(),project=True)
        if not checked.startswith('[kode keluar 0]'):errors.append(checked[:1000])
    return errors


async def inspect_browser_js(contents):
    """Check shared browser script scope, not just each file's Node syntax."""
    from . import tools
    errors=[]
    for page,html in contents.items():
        if not page.endswith('.html'):continue
        d=Document();d.feed(html);scripts=[]
        for url in d.classic_scripts:
            name=str(PurePosixPath(page).parent/url.split('?')[0].split('#')[0])
            if name not in contents:continue
            code=contents[name];scripts.append('// '+name+'\n'+code)
            if re.search(r'(?:^|;)\s*(?:module\.exports|exports\.\w+)\s*=',code,re.M):errors.append(name+': CommonJS exports cannot run in a plain browser script. Use shared browser state/functions, not module.exports.')
        if len(scripts)>1:
            checked=await tools._run_sandboxed(['node','--check','--input-type=commonjs'],timeout=15,stdin='\n\n'.join(scripts).encode(),project=True)
            if not checked.startswith('[kode keluar 0]'):errors.append(page+': Browser scripts share global scope; remove duplicate declarations. '+checked[-1400:])
    return errors


def safe_name(name):
    if not isinstance(name,str) or '\\' in name or '\x00' in name:raise ValueError('Nama berkas proyek tidak valid.')
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(p.startswith('.') for p in path.parts) or not path.parts:
        raise ValueError('Jalur proyek harus relatif, tanpa dotfile/traversal.')
    if path.suffix.lower() not in ('.html','.css','.js','.json','.md','.py','.txt','.svg','.ts','.tsx','.jsx','.yml','.yaml','.toml','.sh','.sql'):raise ValueError('Jenis berkas belum didukung: '+name)
    return str(path)


def unwrap_file(value,path):
    """Recover the requested fenced file only; never synthesize source content."""
    value=value.strip()
    langs={'.html':'html', '.css':'css', '.js':'javascript|js', '.py':'python|py', '.json':'json', '.md':'markdown|md'}
    lang=langs.get(PurePosixPath(path).suffix,re.escape(PurePosixPath(path).suffix.lstrip('.')))
    blocks=list(re.finditer(r'^```([\w-]*)[ \t]*\r?\n(.*?)\r?\n```[ \t]*(?=\r?$)',value,re.S|re.M))
    matches=[block for block in blocks if not block[1] or re.fullmatch(lang,block[1],re.I)]
    if len(matches)==1:return matches[0][2].strip()
    return value


def project_errors(contents,brief):
    html='\n'.join(code for path,code in contents.items() if path.endswith('.html'))
    js='\n'.join(code for path,code in contents.items() if path.endswith('.js'))+'\n'+'\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',html,re.S|re.I))
    errors=[];document=Document();document.feed(html)
    for name in re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)",js):
        if name not in document.ids and not re.search(r"\.id\s*=\s*['\"]"+re.escape(name),js):errors.append('JavaScript mengakses ID yang tidak ada di HTML: '+name)
    if re.search(r'game|permainan',brief,re.I) and re.search(r'HP|mobile|tombol arah|kontrol sentuh',brief,re.I):
        if not re.search(r'touchstart|touchmove|pointerdown|data-direction',js):errors.append('Kontrol HP yang diminta belum diterapkan. Tambahkan d-pad button data-direction up/down/left/right pada HTML dan handler JS yang benar-benar mengubah arah; cegah scroll saat bermain.')
    return list(dict.fromkeys(errors))


def requested_controls(brief):
    required_ids=set()
    # Descriptive prose such as "semua ID sesuai HTML" is not a control declaration.
    brief=re.sub(r'\b(?:semua|setiap|all|each|every|matching|existing)\s+IDs?\b','identifiers',brief,flags=re.I)
    for group in re.findall(r'\bID\s+([A-Za-z]\w*(?:\s*,\s*[A-Za-z]\w*)*)',brief):
        names=re.split(r'\s*,\s*',group)
        required_ids.add(names[0])
        required_ids.update(n for n in names[1:] if n.lower() not in ('input','select','tombol','link','textarea','button'))
    for name in re.findall(r'\b(?:input|select|tombol|link|textarea)\s+([A-Za-z]\w*)',brief):
        if re.search(r'[a-z][A-Z]',name):required_ids.add(name)
    return required_ids


def typed_controls(brief):
    """Honor explicit user control types, without guessing from identifier names."""
    aliases={'tombol':'button','link':'a'};controls={}
    for match in re.finditer(r'\b(input|textarea|select|button|tombol|link|video|canvas)\s+(?:type\s*=\s*(file|range|number|text|checkbox|color)\s+)?(?:ID\s+)?([A-Za-z]\w*)',brief):
        tag,kind,name=match.groups()
        explicit_id=bool(re.search(r'\bID\s+[A-Za-z]\w*$',match.group(0)))
        if name=='ID' or (not explicit_id and not re.search(r'[a-z][A-Z]',name)):continue
        controls[name]={'tag':aliases.get(tag,tag)}
        if kind and tag=='input':controls[name]['type']=kind
    return controls


async def generate(brief, ctx, on_event=None):
    from . import tools,office
    local=llm.active_backend()=='local'
    from . import project_parts
    from . import db
    if db.setting('coding_parts_experimental')=='1' and project_parts.supports(brief):
        return await project_parts.generate(brief,ctx,on_event)
    required_types=typed_controls(brief);required_ids=requested_controls(brief)|set(required_types)
    if local:
        # Local uses bounded planning and generates one module at a time, no second model process.
        instructions='Use vanilla HTML/CSS/JavaScript only; offline browser frontend. Keep each module short, no frameworks.'
    else:instructions='Use clear modular HTML/CSS/JavaScript for browser projects, or Python aiohttp for required server logic. Avoid build tooling unless explicitly requested.'
    prompt=('Plan a complete runnable project for this brief. '+instructions+' Return JSON {name,files:[{path,purpose}],instructions}. '
            'Use 3-6 files, include index.html for browser projects and README.md. For 2D games use canvas; for 3D use native WebGL '
            'or a pinned documented library if required. Include real controls, gameplay/state/UI, persistence where useful, accessible '
            'responsive UI. Do not create a landing page when a functional game/app is requested. No unavailable API claims, no secrets. '
            'Paths relative with extensions html/css/js/json/md/py/txt/svg only. State required backend/dependencies honestly. JSON only.')
    schema={'type':'object','properties':{'name':{'type':'string'},'files':{'type':'array','minItems':3,'maxItems':6,'items':{'type':'object','properties':{'path':{'type':'string'},'purpose':{'type':'string'}},'required':['path','purpose'],'additionalProperties':False}},'instructions':{'type':'string'}},'required':['name','files','instructions'],'additionalProperties':False}
    if local:
        control_schema={'type':'object','properties':{'tag':{'type':'string','enum':['input','textarea','button','select','a','video','canvas','div','span']},'type':{'type':'string'},'label':{'type':'string'}},'required':['tag','type','label'],'additionalProperties':False}
        planned_controls={}
        for name in sorted(required_ids):
            item=json.loads(json.dumps(control_schema))
            for key,value in required_types.get(name,{}).items():item['properties'][key]={'type':'string','const':value}
            planned_controls[name]=item
        schema['properties']['interface']={'type':'object','properties':{'layout':{'type':'string'},'controls':{'type':'object','properties':planned_controls,'required':sorted(required_ids),'additionalProperties':False}},'required':['layout','controls'],'additionalProperties':False}
        schema['required'].append('interface')
        prompt+=' Also return interface:{layout,controls:{ID:{tag,type,label}}}. Describe the visual layout in at most 100 words, including the requested palette. Map each required control ID to its correct HTML tag/input type. No source code or JavaScript algorithms in interface. Keep purposes short; reuse shared state across JS modules.'
    plan,plan_response=await structured.request([{'role':'system','content':prompt},{'role':'user','content':brief[:6500]}],label='Rencana berkas',max_tokens=1600 if local else 1000,schema=schema,on_event=on_event,fmt={'type':'json_schema','json_schema':{'name':'project_plan','schema':schema,'strict':True}})
    if not isinstance(plan.get('files'),list) or not 1<=len(plan['files'])<=8:raise ValueError('Rencana berkas proyek tidak lengkap.')
    # Markup defines the styling/DOM contract. Preserve order within dependent JS modules.
    plan['files'].sort(key=lambda entry: 0 if entry['path'].endswith('.html') else 1 if entry['path'].endswith('.css') else 3 if entry['path'].endswith('.md') else 2)
    root='project-'+str(__import__('time').time_ns());manifest=[];contents={};stats=plan.get('stats',{})
    for entry in plan['files']:
        path=safe_name(entry['path'])
        if path in manifest:raise ValueError('Nama berkas proyek berulang: '+path)
        manifest.append(path)
    for i,entry in enumerate(plan['files']):
        path=manifest[i];office.phase('Membuat '+path,'writing')
        if on_event:await on_event('status','Membuat '+path+f' ({i+1}/{len(manifest)})…')
        draft='';last_emit=0
        async def code_token(piece):
            nonlocal draft,last_emit
            draft=(draft+piece)[-48000:]
            now=__import__('time').monotonic()
            if on_event and now-last_emit>=.4:
                last_emit=now
                await on_event('code',{'path':root+'/'+path,'content':draft,'draft':True})
        # Include previous modules to keep identifiers/imports consistent, with a bounded context.
        context='\n\n'.join(n+'\n'+v for n,v in contents.items())[-11000:]
        contract=Document()
        for name,source in contents.items():
            if name.endswith('.html'):contract.feed(source)
        language={'.css':'CSS rules only, no HTML tags or JavaScript','.js':'JavaScript only, no HTML tags, CSS rules or explanations',
                  '.html':'one complete HTML document','.md':'short Markdown instructions only'}.get(PurePosixPath(path).suffix,'raw source')
        file_task='CURRENT FILE: '+path+'\nOutput '+language+'. Use these existing HTML IDs exactly: '+', '.join(sorted(contract.ids))+'. Keep the implementation concise; no repeated scaffolding.'
        if path=='index.html' and required_ids:file_task+='\nRequired control IDs: '+', '.join(sorted(required_ids))
        source_request=json.dumps({'brief':brief[:4500],'plan':plan,'current':entry},ensure_ascii=False)+'\nPrevious modules:\n'+context+'\n\n'+file_task
        if local:
            if path.endswith('.css'):
                source_request=('Design a complete responsive stylesheet for the ACTUAL markup below. Match its classes and IDs, never invent a form wrapper. '
                    'Implement the requested visual direction: cohesive palette, deliberate spacing, typography, grid/flex layout, styled controls, focus/disabled states, '
                    'empty/loading/error states, and a mobile breakpoint without horizontal overflow. Keep preview media inside its panel. '
                    'Use CSS only, no imports, frameworks or template markup.\nRequirements: '+brief[:3500]+'\n'+file_task+
                    '\nExisting classes: '+', '.join(sorted(contract.classes))+'\nActual HTML:\n'+
                    '\n'.join(v for n,v in contents.items() if n.endswith('.html'))[-6500:])
            elif path.endswith('.md'):
                source_request='Write short usage instructions, including limitations. No source code.\n'+brief[:2000]+'\n'+file_task
            elif path.endswith('.html'):
                source_request=('Write ONLY the HTML user interface for '+str(plan.get('name','Browser utility'))+'. Purpose: '+str(entry.get('purpose',''))+
                    '.\nInterface specification (create this layout and these controls only; all behavior belongs to JS): '+json.dumps(plan.get('interface',{'layout':brief[:3500]}),ensure_ascii=False)+
                    '\nEvery required ID must appear exactly once: '+', '.join(sorted(required_ids))+
                    '\nUse appropriate input types for the requested controls (file, range, number, text), a video/canvas element for preview when requested, and an anchor with download attribute and no href until JS prepares a blob for downloads. '
                    'Do not reference imaginary sample images/videos; show a meaningful empty state before import.\nReference these local files: '+', '.join(manifest)+
                    '.\nOutput a complete HTML document. No inline style, no inline JavaScript, no function implementation. Use deferred script src for JS and link rel=stylesheet for CSS. Include title and viewport. End at </html>.')
            else:
                source_request=(brief[:3500]+'\nModule purpose: '+str(entry.get('purpose',''))+'\n'+file_task+
                    '\nExisting HTML (match its elements, do not reproduce it in JS):\n'+'\n'.join(v for n,v in contents.items() if n.endswith('.html'))[-6000:]+
                    '\nExisting JavaScript (reuse its state/functions; do not duplicate declarations):\n'+'\n'.join(n+'\n'+v for n,v in contents.items() if n.endswith('.js'))[-6500:])
        result=await llm.chat([{'role':'system','content':('Implement ONE complete file. '+file_task+' Raw file content only, no fences. No truncation/placeholders. '
                 'Keep consistent with previous modules. Finish all braces/tags. '+instructions)},
                {'role':'user','content':source_request}],
                max_tokens=(1600 if path.endswith('.css') else 400 if path.endswith('.md') else 3000) if local else 4800,temperature=.3,on_token=code_token if on_event else None)
        code=unwrap_file(result['content'],path)
        if on_event:await on_event('code',{'path':root+'/'+path,'content':code,'draft':True})
        async def source_errors(value):
            problems=[]
            if result.get('stats',{}).get('finish_reason') in ('length','max_tokens'):problems.append('Response exceeded output token budget.')
            if path.endswith('.css'):
                if re.search(r'<[a-z!/][^>]*>',value,re.I) or value.count('{')!=value.count('}'):problems.append('CSS file contains HTML or unmatched braces.')
                problems.extend(inspect_css(value))
            if path.endswith('.js'):
                checked=await tools._run_sandboxed(['node','--check','--input-type=commonjs'],timeout=15,stdin=value.encode(),project=True)
                if not checked.startswith('[kode keluar 0]'):problems.append(checked[-1800:])
            if path.endswith('.html'):
                problems.extend(inspect_html(value,required_ids if path=='index.html' else (),strict=True,required_controls=required_types if path=='index.html' else None)['errors'])
                problems.extend(await inspect_inline_js(value))
                if local and any(n.endswith('.js') for n in manifest) and any(source.strip() for _,source in re.findall(r'<script\b([^>]*)>(.*?)</script\s*>',value,re.I|re.S)):
                    problems.append('HTML must contain only markup. Move all inline JavaScript to the planned JS file; use script src instead.')
            if path.endswith('.json'):
                try:json.loads(value)
                except ValueError as exc:problems.append(str(exc))
            if path.endswith('.py'):
                try:compile(value,path,'exec')
                except SyntaxError as exc:problems.append(str(exc))
            return problems
        problems=await source_errors(code)
        if problems:
            if on_event:await on_event('status','Memperbaiki '+path+': jenis/sintaks keluaran belum benar…')
            draft='';last_emit=0
            result=await llm.chat([{'role':'system','content':'Write ONE complete concise source file. '+file_task+' No prose, code fences or placeholder logic. Complete the brief, preserve the HTML IDs. Do not output other files.'},
                {'role':'user','content':source_request+'\nFix these errors: '+json.dumps(problems)+'\nCurrent model draft (repair this file, preserve valid layout/logic rather than starting over):\n'+code[:10000]}],
                max_tokens=1600 if path.endswith(('.css','.md')) else 3000 if local else 4800,temperature=.1,on_token=code_token if on_event else None)
            code=unwrap_file(result['content'],path)
            if on_event:await on_event('code',{'path':root+'/'+path,'content':code,'draft':True})
            problems=await source_errors(code)
            if problems:raise ValueError(path+' belum valid setelah perbaikan: '+' '.join(problems)[:1800])
        if not code or len(code.encode())>150000:raise ValueError('Berkas proyek kosong/terlalu besar: '+path)
        if path.endswith('.html'):
            check=inspect_html(code)
            if not check['ok']:raise ValueError(path+': '+' '.join(check['errors']))
        if path.endswith('.json'):json.loads(code)
        if path.endswith('.py'):compile(code,path,'exec')
        contents[path]=code;stats=result.get('stats',{})
        # Stage files privately until all modules have passed validation.
    errors=project_errors(contents,brief)+await inspect_browser_js(contents)
    if errors and local:
        if on_event:await on_event('status','Memperbaiki JavaScript sesuai HTML yang sudah dibuat…')
        # A tiny model cannot rewrite every module inside one JSON token budget.
        # Repair the actual JS contract without silently editing the DOM or adding templates.
        html='\n'.join(v for n,v in contents.items() if n.endswith('.html'))
        for js_path in [n for n in contents if n.endswith('.js')]:
            repaired=await llm.chat([{'role':'system','content':'Repair ONE JavaScript file. Output complete raw JavaScript only. Match the actual HTML IDs and controls exactly. Preserve all requested functionality. No HTML, fences, explanations or placeholders.'},
                {'role':'user','content':json.dumps({'brief':brief[:3500],'errors':errors,'html':html,'file':js_path,'javascript':contents[js_path],'other_javascript':{n:v for n,v in contents.items() if n.endswith('.js') and n!=js_path}},ensure_ascii=False)}],max_tokens=3000,temperature=.1)
            if repaired.get('stats',{}).get('finish_reason') in ('length','max_tokens'):raise ValueError('Perbaikan JavaScript terpotong; proyek belum disimpan.')
            source=unwrap_file(repaired['content'],js_path)
            checked=await tools._run_sandboxed(['node','--check','--input-type=commonjs'],timeout=15,stdin=source.encode(),project=True)
            if not source or not checked.startswith('[kode keluar 0]'):raise ValueError('Perbaikan JavaScript belum valid: '+checked[-1800:])
            contents[js_path]=source;stats=repaired.get('stats',{})
        errors=project_errors(contents,brief)+await inspect_browser_js(contents)
        if errors:raise ValueError('Kontrak HTML/JS belum benar: '+' '.join(errors))
    if errors:
        if on_event:await on_event('status','Memperbaiki kontrak antarberkas…')
        repaired=await llm.chat([{'role':'system','content':'Repair the complete multi-file project without losing working logic. Return JSON {files:[{path,content}]}, all existing files with complete content. No fences/placeholders. Fix ALL reported issues. Make canvas CSS width:min(100%,320px); height:auto; containers max-width:100%; box-sizing:border-box; controls wrap; fit viewport320px. Preserve matching IDs/imports.'},
                                {'role':'user','content':json.dumps({'brief':brief,'errors':errors,'files':contents},ensure_ascii=False)}],max_tokens=2400 if local else 7000,fmt='json',temperature=.2)
        patch=json.loads(repaired['content'].strip().removeprefix('```json').removesuffix('```').strip())
        replacement={safe_name(f['path']):f['content'] for f in patch['files']}
        if set(replacement)!=set(contents) or any(not isinstance(code,str) or not code.strip() for code in replacement.values()):raise ValueError('Perbaikan antarberkas tidak lengkap.')
        contents=replacement;stats=repaired.get('stats',{})
        errors=project_errors(contents,brief)+await inspect_browser_js(contents)
        if errors:raise ValueError('Proyek belum memenuhi kontrak setelah perbaikan: '+' '.join(errors))
        for path,code in contents.items():
            if path.endswith('.html') and not inspect_html(code)['ok']:raise ValueError('HTML proyek setelah perbaikan belum valid.')
            if path.endswith('.json'):json.loads(code)
            if path.endswith('.py'):compile(code,path,'exec')
    for path,html in contents.items():
        if path.endswith('.html'):
            for resource in inspect_html(html)['resources']:
                if resource.startswith(('http:','https:','data:','//')):continue
                relative=str(PurePosixPath(path).parent/resource.split('?')[0].split('#')[0])
                if relative not in contents:raise ValueError('Berkas rujukan belum dibuat: '+relative)
    folder=tools._workpath(root);folder.mkdir(parents=True)
    try:__import__('os').chown(folder,tools.config.KERJA_UID,tools.config.KERJA_GID)
    except (AttributeError,OSError):pass
    for path,code in contents.items():
        await tools.write_file(ctx,root+'/'+path,code)
        if tools._workpath(root+'/'+path).read_text(encoding='utf-8')!=code:raise ValueError('Verifikasi isi gagal: '+path)
        if path.endswith('.js'):
            check=await tools._run_sandboxed(['node','--check',str(tools._workpath(root+'/'+path))],timeout=15,cwd=folder,project=True)
            if not check.startswith('[kode keluar 0]'):raise ValueError('JavaScript belum valid: '+path+' '+check)

    bundle=root+'/project.zip'
    with zipfile.ZipFile(tools._workpath(bundle),'w',zipfile.ZIP_DEFLATED) as archive:
        for path in contents:archive.write(tools._workpath(root+'/'+path),path)
    with zipfile.ZipFile(tools._workpath(bundle)) as archive:
        if archive.testzip():raise ValueError('ZIP proyek gagal CRC.')
    ctx.attachments=[p for p in ctx.attachments if not p.startswith(root+'/')]+[bundle]
    ctx.served_model=stats.get('served_model','')
    return 'Proyek multi-berkas sudah dibuat dan ZIP diperiksa. '+plan.get('instructions','')+'\nPemeriksaan sintaks/struktur bukan pengganti menjalankan semua alur di browser/backend.\nBerkas: '+bundle
