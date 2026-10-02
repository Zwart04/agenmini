"""Multi-file frontend project generation, real artifact checks and ZIP delivery."""
import ast
import json
import re
import zipfile
from pathlib import PurePosixPath
from html.parser import HTMLParser
from . import llm,structured


def project_request(text):
    return bool(re.search(r'\b(buat(?:kan|in)?|bikin(?:kan)?|build|create|generate|kembangkan)\b',text,re.I)
                and re.search(r'\b(game|permainan|web\s*app|aplikasi|project|proyek)\b',text,re.I))


class Document(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=set();self.anchors=[];self.resources=[];self.tags={};self.viewport=False;self.title=False;self.scripts=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.tags[tag]=self.tags.get(tag,0)+1
        if a.get('id'):self.ids.add(a['id'])
        if tag=='meta' and a.get('name','').lower()=='viewport':self.viewport=True
        if tag=='title':self.title=True
        if tag=='a' and a.get('href','').startswith('#'):self.anchors.append(a['href'][1:])
        if tag in ('script','link','img'):
            url=a.get('src') or (a.get('href') if tag=='link' else None)
            if url:self.resources.append(url)
        if tag=='script':self.scripts+=1


def inspect_html(html):
    d=Document();d.feed(html);d.close();errors=[]
    for tag in ('html','head','body','title'):
        if not d.tags.get(tag):errors.append('Tag '+tag+' belum ada.')
    if not d.viewport:errors.append('Meta viewport belum ada.')
    if not re.search(r'</html\s*>',html,re.I):errors.append('Dokumen belum ditutup.')
    for target in d.anchors:
        if not target or target not in d.ids:errors.append('Tautan bagian tidak memiliki tujuan: #'+target)
    for tag in ('script','style'):
        if len(re.findall('<'+tag+r'\b',html,re.I))!=len(re.findall('</'+tag+r'\s*>',html,re.I)):errors.append(tag+' belum lengkap.')
    if re.search(r'lorem ipsum|YOUR_API_KEY|TODO:\s*implement',html,re.I):errors.append('Placeholder implementasi masih tersisa.')
    return {'ok':not errors,'errors':errors,'sections':d.tags.get('section',0),'buttons':d.tags.get('button',0),
            'scripts':d.scripts,'bytes':len(html.encode()),'resources':d.resources,
            'note':'Pemeriksaan struktur dan tautan. Tampilan/interaksi perlu diuji browser; backend hanya dianggap terhubung bila diuji nyata.'}


async def inspect_inline_js(html):
    from . import tools
    errors=[]
    for attrs,script in re.findall(r'<script\b([^>]*)>(.*?)</script\s*>',html,re.I|re.S):
        if not script.strip() or re.search(r'type=[\"\']application/',attrs,re.I):continue
        kind='module' if re.search(r'type=[\"\']module',attrs,re.I) else 'commonjs'
        checked=await tools._run_sandboxed(['node','--check','--input-type='+kind],timeout=10,stdin=script.encode(),project=True)
        if not checked.startswith('[kode keluar 0]'):errors.append(checked[:1000])
    return errors


def safe_name(name):
    if not isinstance(name,str) or '\\' in name or '\x00' in name:raise ValueError('Nama berkas proyek tidak valid.')
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(p.startswith('.') for p in path.parts) or not path.parts:
        raise ValueError('Jalur proyek harus relatif, tanpa dotfile/traversal.')
    if path.suffix.lower() not in ('.html','.css','.js','.json','.md','.py','.txt','.svg','.ts','.tsx','.jsx','.yml','.yaml','.toml','.sh','.sql'):raise ValueError('Jenis berkas belum didukung: '+name)
    return str(path)


def project_errors(contents,brief):
    html='\n'.join(code for path,code in contents.items() if path.endswith('.html'))
    js='\n'.join(code for path,code in contents.items() if path.endswith('.js'))+'\n'+'\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',html,re.S|re.I))
    errors=[];document=Document();document.feed(html)
    for name in re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)",js):
        if name not in document.ids and not re.search(r"\.id\s*=\s*['\"]"+re.escape(name),js):errors.append('JavaScript mengakses ID yang tidak ada di HTML: '+name)
    if re.search(r'game|permainan',brief,re.I) and re.search(r'HP|mobile|tombol arah|kontrol sentuh',brief,re.I):
        if not re.search(r'touchstart|touchmove|pointerdown|data-direction',js):errors.append('Kontrol HP yang diminta belum diterapkan. Tambahkan d-pad button data-direction up/down/left/right pada HTML dan handler JS yang benar-benar mengubah arah; cegah scroll saat bermain.')
    return list(dict.fromkeys(errors))


async def generate(brief, ctx, on_event=None):
    from . import tools,office
    local=llm.active_backend()=='local'
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
    plan,plan_response=await structured.request([{'role':'system','content':prompt},{'role':'user','content':brief[:6500]}],label='Rencana berkas',max_tokens=1000,schema=schema,on_event=on_event,fmt={'type':'json_schema','json_schema':{'name':'project_plan','schema':schema,'strict':True}})
    if not isinstance(plan.get('files'),list) or not 1<=len(plan['files'])<=8:raise ValueError('Rencana berkas proyek tidak lengkap.')
    root='project-'+str(__import__('time').time_ns());manifest=[];contents={};stats=plan.get('stats',{})
    for entry in plan['files']:
        path=safe_name(entry['path'])
        if path in manifest:raise ValueError('Nama berkas proyek berulang: '+path)
        manifest.append(path)
    for i,entry in enumerate(plan['files']):
        path=manifest[i];office.phase('Membuat '+path,'writing')
        if on_event:await on_event('status','Membuat '+path+f' ({i+1}/{len(manifest)})…')
        # Include previous modules to keep identifiers/imports consistent, with a bounded context.
        context='\n\n'.join(n+'\n'+v for n,v in contents.items())[-11000:]
        result=await llm.chat([{'role':'system','content':('Implement ONE complete file. Raw file content only, no fences. No truncation/placeholders. '
                 'Keep consistent with the project plan and previous modules. Finish all braces/tags. '+instructions)},
                {'role':'user','content':json.dumps({'brief':brief[:4500],'plan':plan,'current':entry},ensure_ascii=False)+'\nPrevious modules:\n'+context}],
                max_tokens=2400 if local else 4800,temperature=.3)
        code=result['content'].strip();code=re.sub(r'^```[^\n]*\n','',code);code=re.sub(r'\n```\s*$','',code)
        if not code or len(code.encode())>150000:raise ValueError('Berkas proyek kosong/terlalu besar: '+path)
        if path.endswith('.html'):
            check=inspect_html(code)
            if not check['ok']:raise ValueError(path+': '+' '.join(check['errors']))
        if path.endswith('.json'):json.loads(code)
        if path.endswith('.py'):ast.parse(code)
        contents[path]=code;stats=result.get('stats',{})
        # Stage files privately until all modules have passed validation.
    errors=project_errors(contents,brief)
    if errors:
        if on_event:await on_event('status','Memperbaiki kontrak antarberkas…')
        repaired=await llm.chat([{'role':'system','content':'Repair the complete multi-file project without losing working logic. Return JSON {files:[{path,content}]}, all existing files with complete content. No fences/placeholders. Fix ALL reported issues. Make canvas CSS width:min(100%,320px); height:auto; containers max-width:100%; box-sizing:border-box; controls wrap; fit viewport320px. Preserve matching IDs/imports.'},
                                {'role':'user','content':json.dumps({'brief':brief,'errors':errors,'files':contents},ensure_ascii=False)}],max_tokens=2400 if local else 7000,fmt='json',temperature=.2)
        patch=json.loads(repaired['content'].strip().removeprefix('```json').removesuffix('```').strip())
        replacement={safe_name(f['path']):f['content'] for f in patch['files']}
        if set(replacement)!=set(contents) or any(not isinstance(code,str) or not code.strip() for code in replacement.values()):raise ValueError('Perbaikan antarberkas tidak lengkap.')
        contents=replacement;stats=repaired.get('stats',{})
        errors=project_errors(contents,brief)
        if errors:raise ValueError('Proyek belum memenuhi kontrak setelah perbaikan: '+' '.join(errors))
        for path,code in contents.items():
            if path.endswith('.html') and not inspect_html(code)['ok']:raise ValueError('HTML proyek setelah perbaikan belum valid.')
            if path.endswith('.json'):json.loads(code)
            if path.endswith('.py'):ast.parse(code)
    for path,html in contents.items():
        if path.endswith('.html'):
            for resource in inspect_html(html)['resources']:
                if resource.startswith(('http:','https:','data:','//')):continue
                relative=str(PurePosixPath(path).parent/resource.split('?')[0].split('#')[0])
                if relative not in contents:raise ValueError('Berkas rujukan belum dibuat: '+relative)
    folder=tools._workpath(root);folder.mkdir(parents=True)
    __import__('os').chown(folder,tools.config.KERJA_UID,tools.config.KERJA_GID)
    for path,code in contents.items():
        await tools.write_file(ctx,root+'/'+path,code)
        if tools._workpath(root+'/'+path).read_text()!=code:raise ValueError('Verifikasi isi gagal: '+path)
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
