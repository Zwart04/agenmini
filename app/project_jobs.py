"""Persistent project checkpoints processed by the existing single office worker."""
import json
import time
import re
import ast
from pathlib import Path
from . import db,config,llm,tools,office


running_projects=set()

def init():
    db.run('CREATE TABLE IF NOT EXISTS project_stage_receipts(project_id INTEGER,cursor INTEGER,response TEXT,files TEXT,PRIMARY KEY(project_id,cursor))')
    db.run('CREATE TABLE IF NOT EXISTS project_stage_snapshots(project_id INTEGER,cursor INTEGER,files TEXT,PRIMARY KEY(project_id,cursor))')
    db.run("CREATE TABLE IF NOT EXISTS project_jobs(id INTEGER PRIMARY KEY,brief TEXT,repository TEXT,folder TEXT,status TEXT,plan TEXT DEFAULT '{}',cursor INTEGER DEFAULT 0,channel TEXT,ext_id TEXT,engine TEXT,model TEXT,result TEXT DEFAULT '',approval_id INTEGER DEFAULT 0,created_at REAL,updated_at REAL)")
    columns={r['name'] for r in db.q('PRAGMA table_info(project_jobs)')}
    for name,definition in [('autonomous','INTEGER DEFAULT 0'),('retry_count','INTEGER DEFAULT 0'),('next_run','REAL DEFAULT 0'),('name',"TEXT DEFAULT ''")]:
        if name not in columns:db.run('ALTER TABLE project_jobs ADD COLUMN '+name+' '+definition)
    db.run('CREATE TABLE IF NOT EXISTS project_events(id INTEGER PRIMARY KEY,project_id INTEGER,phase TEXT,text TEXT,created_at REAL)')


def event(pid,phase,text):
    # Keep structured event text valid JSON when bounding long traces.
    if len(text)>10000:
        try:
            payload=json.loads(text)
            response=payload.get('response',payload)
            meta=response.get('meta',{}) if isinstance(response,dict) else {}
            traces=meta.get('trace',[])
            meta['trace']=[{**t,'arg':str(t.get('arg',''))[:300],'hasil':str(t.get('hasil',''))[-600:]} for t in traces[-5:]]
            text=json.dumps(payload,ensure_ascii=False)
            if len(text)>10000:text=json.dumps({'summary':str(response.get('text',''))[:3000],'truncated':True},ensure_ascii=False)
        except (ValueError,AttributeError,TypeError):text=text[:10000]
    db.run('INSERT INTO project_events(project_id,phase,text,created_at) VALUES(?,?,?,?)',(pid,phase,text,time.time()))


def repository_protected(brief, repository):
    """Honor explicit do-not-touch lists before a project worker edits a repo."""
    if not repository:return False
    normalized=repository.rstrip('/').removesuffix('.git').lower()
    protected=False
    for line in brief.splitlines():
        if re.search(r'jangan\s*(?:di\s*)?sentuh|do[ -]not[ -]touch|protected repositories',line,re.I):
            protected=True
        elif protected and line.strip() and not re.match(r'\s*[-*•]',line):
            protected=False
        if protected:
            urls=re.findall(r'https://github\.com/[\w.-]+/[\w.-]+',line)
            if any(u.rstrip('/').removesuffix('.git').lower()==normalized for u in urls):return True
    return False


def create(ctx,brief,repository=''):
    init()
    if not isinstance(brief,str) or not brief.strip():raise ValueError('Tujuan proyek belum diisi.')
    if not isinstance(repository,str):raise ValueError('URL repo wajib berupa teks.')
    if repository and not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?/?',repository):raise ValueError('Gunakan URL GitHub tanpa token; repo privat memakai login host yang terverifikasi.')
    if db.one("SELECT count(*) n FROM project_jobs WHERE status IN ('queued','working','planning')")['n']>=5:raise ValueError('Selesaikan atau jeda proyek sebelumnya; maksimal lima antrean.')
    if repository_protected(brief,repository):raise ValueError('Repo ini ada dalam daftar jangan disentuh. Pilih repo lain; proyek lama tetap dipertahankan.')
    # SQLite INTEGER PRIMARY KEY can reuse IDs after record deletion. Persist a
    # high-water mark and skip preserved folders/archives before allocating one.
    with db._lock:
        highest=db.one('SELECT max(id) n FROM project_jobs')['n'] or 0
        pid=max(highest+1,int(db.setting('project_next_id') or 1))
        while tools._workpath('projects/project-'+str(pid)).exists() or tools._workpath('projects/project-'+str(pid)+'-source.zip').exists():pid+=1
        folder='projects/project-'+str(pid)
        db.run('INSERT INTO project_jobs(id,brief,repository,folder,status,channel,ext_id,engine,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
               (pid,brief[:12000],repository,folder,'queued',ctx.channel,ctx.ext_id,ctx.bot.get('backend') or db.setting('llm_backend'),ctx.bot.get('model') or '',time.time(),time.time()))
        db.set_setting('project_next_id',str(pid+1))
    event(pid,'queued','Proyek dijadwalkan. Progress dihitung dari tahap yang benar-benar selesai.');return pid


async def inspect(folder):
    root=tools._workpath(folder)
    if not root.is_dir():raise ValueError('Folder proyek belum tersedia.')
    files=[];checks=[];manifests={}
    def walk(path):
        for p in sorted(path.iterdir()):
            if p.name in ('.git','node_modules','.venv','dist','build','__pycache__'):continue
            if p.is_symlink():continue
            if p.is_dir():yield from walk(p)
            elif p.is_file():yield p
    for p in walk(root):
        if len(files)>=500:break
        name=str(p.relative_to(root));files.append(name)
        if p.stat().st_size>200000:continue
        if p.name in ('AGENTS.md','README.md','package.json','pyproject.toml','requirements.txt'):
            manifests[name]=p.read_text(errors='replace')[:5000]
        try:
            if p.suffix=='.json' and p.name not in ('tsconfig.json','jsconfig.json'):json.loads(p.read_text());checks.append({'file':name,'check':'JSON','ok':True})
            elif p.suffix=='.py':compile(p.read_text(),str(p),'exec');checks.append({'file':name,'check':'Python compile','ok':True})
            elif p.suffix=='.js' and len(checks)<50:
                output=await tools._run_sandboxed(['node','--check',str(p)],timeout=10,cwd=root,project=True)
                checks.append({'file':name,'check':'Node syntax','ok':output.startswith('[kode keluar 0]'),'output':output[:500]})
        except (ValueError,SyntaxError) as exc:checks.append({'file':name,'ok':False,'output':str(exc)[:300]})
    return {'files':files,'manifests':manifests,'checks':checks,'note':'Inventaris maksimal 500 berkas. TypeScript/build/runtime belum diuji oleh pemeriksaan sintaks ini.'}


def rows():
    init();result=db.q('SELECT * FROM project_jobs ORDER BY id DESC LIMIT 200')
    for row in result:
        row['plan']=json.loads(row['plan'] or '{}');row['events']=db.q('SELECT phase,text,created_at FROM project_events WHERE project_id=? ORDER BY id DESC LIMIT 12',(row['id'],))
        row['approval']=None
        if row.get('approval_id'):
            approval=db.one('SELECT id,tool,args,reason,status FROM approvals WHERE id=?',(row['approval_id'],))
            if approval and approval['status']=='menunggu':row['approval']=approval
    return result


def approval_completed(approval_id,allowed,response):
    """Called for web, Telegram and office decisions, using the actual tool result."""
    init()
    jobs=db.q("SELECT id,cursor,folder FROM project_jobs WHERE status='waiting' AND approval_id=?",(approval_id,))
    failed=office.outcome(response)=='failed' or bool(re.match(r'\[kode keluar (?!0\])',response.get('text','')))
    state='paused' if not allowed else 'waiting' if response.get('approval') else 'failed' if failed else 'queued'
    for job in jobs:
        if allowed and not failed and response.get('meta',{}).get('trace'):
            root=tools._workpath(job['folder']);files=snapshot(root)
            db.run('INSERT OR REPLACE INTO project_stage_receipts VALUES(?,?,?,?)',(job['id'],job['cursor'],json.dumps(response,ensure_ascii=False),json.dumps(files)))
        db.run('UPDATE project_jobs SET status=?,approval_id=?,result=?,updated_at=? WHERE id=?',
               (state,response.get('approval',0),response.get('text','')[:2000],time.time(),job['id']))
        event(job['id'],'approval',('Diizinkan' if allowed else 'Ditolak')+': '+response.get('text','')[:2000])
    return state


def recover_consumed_approvals():
    """Legacy decisions had no checkpoint callback. Recheck the milestone, never advance it."""
    for row in db.q("SELECT p.id,a.status FROM project_jobs p JOIN approvals a ON a.id=p.approval_id WHERE p.status='waiting' AND a.status IN ('diizinkan','ditolak')"):
        state='queued' if row['status']=='diizinkan' else 'paused'
        db.run('UPDATE project_jobs SET status=?,approval_id=0 WHERE id=?',(state,row['id']))
        event(row['id'],'recovery','Keputusan izin lama disinkronkan. Tahap dijalankan ulang dari berkas sekarang dan harus memiliki bukti uji; cursor tidak dinaikkan.')


def snapshot(root):
    import hashlib
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix not in ('.db','.sqlite','.log','.pyc','.gguf') and not p.name.endswith(('-wal','-shm')) and p.stat().st_size<200000 and not any(part in ('.git','node_modules','.venv','__pycache__','dist','build') for part in p.relative_to(root).parts)}


def stage_baseline(pid,cursor,root):
    row=db.one('SELECT files FROM project_stage_snapshots WHERE project_id=? AND cursor=?',(pid,cursor))
    if row:return json.loads(row['files'])
    before=snapshot(root)
    db.run('INSERT INTO project_stage_snapshots VALUES(?,?,?)',(pid,cursor,json.dumps(before)))
    return before


def receipt_for_stage(pid,cursor,root):
    row=db.one('SELECT response,files FROM project_stage_receipts WHERE project_id=? AND cursor=?',(pid,cursor))
    if not row or json.loads(row['files'])!=snapshot(root):return None
    return json.loads(row['response'])


def acceptance_problems(milestone,response,before,after):
    changed=[name for name,value in after.items() if before.get(name)!=value]
    task=milestone['task'];criteria=task+' '+milestone['acceptance'];problems=[]
    if re.search(r'\b(buat|pembuatan|create|implement|inisialisasi|pengembangan|ubah|tambah|perbaiki|fix|update|edit|refactor)',task,re.I) and not changed:
        problems.append('Tahap meminta implementasi, tetapi belum ada perubahan berkas di folder proyek.')
    if re.search(r'\btes\b|uji|test|assert|build|kompil|compile|\bAPI\b|\bHTTP\b|cookie|otentikasi|autentikasi|isolasi data|checkout|stok|backend|frontend',criteria,re.I):
        commands=[t for t in response.get('meta',{}).get('trace',[]) if t.get('alat')=='run_project_command' and not t.get('cached') and t.get('hasil','').startswith('[kode keluar 0]')]
        def verifies(t):
            arg=t.get('arg','')
            try:command=json.loads(arg).get('command','')
            except (ValueError,TypeError,AttributeError):command=str(arg)
            # Installing a test runner is not running tests, even if its name says pytest.
            command=re.sub(r'(?:python(?:3)?\s+-m\s+)?pip(?:3)?\s+install[^;&|\n]*','',command,flags=re.I)
            command=re.sub(r'(?:npm|pnpm|yarn)\s+(?:install|ci)[^;&|\n]*','',command,flags=re.I)
            return bool(re.search(r'(?:^|[;&|\n])\s*(?:pytest\b|jest\b|vitest\b|tsc\b|npm\s+(?:run\s+)?(?:test|build|check)\b|(?:python(?:3)?|node)\s+[^;&|\n]*(?:test|assert|compile)|(?:go|cargo|dotnet)\s+(?:test|build)\b|make\s+(?:test|check|build)\b)',command,re.I))
        commands=[t for t in commands if verifies(t)]
        if not commands:problems.append('Build/test yang diminta belum memiliki perintah nyata dengan exit code 0.')
    return problems,changed


def capable_worker(milestone,parent_tools):
    required=[]
    if re.search(r'\b(buat|pembuatan|pengembangan|inisialisasi|create|implement|ubah|tambah|perbaiki|fix|update|edit|refactor|struktur|structure)',milestone['task'],re.I):
        required.append({'write_file','edit_project_file'})
    if re.search(r'\btes\b|uji|test|assert|build|kompil|compile|\bAPI\b|\bHTTP\b|cookie|autentikasi|backend|frontend|checkout',milestone['task']+' '+milestone['acceptance'],re.I):
        required.append({'run_project_command'})
    original=db.bot(milestone['bot'])
    candidates=[original]+[db.bot('teknisi'),db.bot('desainer'),db.bot('reviewer')]
    for bot in candidates:
        if not bot or not bot.get('active'):continue
        available=set(bot['tools']) & set(parent_tools)
        if all(available & group for group in required):return bot['id']
    raise ValueError('Belum ada bot dengan izin alat yang diperlukan untuk tahap ini. Periksa alat bot di Workspace.')


async def execute_declared_check(ctx,milestone,worker):
    """A concrete check/repair loop, avoiding repeated planning instead of execution.

    Only owner-authorized project jobs use this path. It invokes the same scoped
    tools as the assigned worker; it cannot acquire missing worker permissions.
    """
    command=milestone.get('test_command')
    targets=milestone.get('repair_files',[])
    bot=db.bot(worker)
    if not command or not isinstance(targets,list) or len(targets)>3:return None
    allowed=set(bot['tools']) & set(ctx.bot['tools'])
    if 'run_project_command' not in allowed or (targets and 'edit_project_file' not in allowed):return None
    child=tools.Ctx({**bot,'tools':list(allowed),'backend':ctx.bot.get('backend',''),'model':ctx.bot.get('model','')},ctx.chat,ctx.channel,ctx.ext_id,user_text=ctx.user_text)
    child.project_folder=ctx.project_folder
    trace=[];used=[]
    token=office.start(worker,milestone['task'])
    try:
        for round_no in range(2):
            args={'folder':ctx.project_folder,'command':command,'timeout':180}
            office.phase('Menjalankan tes penerimaan yang ditetapkan','tool')
            output=await tools.run_project_command(child,**args)
            used.append('run_project_command');trace.append({'alat':'run_project_command','arg':json.dumps(args),'hasil':output[-6000:],'cached':False})
            if output.startswith('[kode keluar 0]'):
                return {'text':output,'meta':{'tools':used,'trace':trace,'status':'done'}}
            if round_no==1 or not targets:break
            for target in targets:
                office.phase('Memperbaiki '+target+' dari galat tes nyata','writing')
                args={'folder':ctx.project_folder,'path':target,'instructions':
                      'Perbaiki implementasi yang ada agar tes penerimaan berikut benar-benar lulus. Jangan mengubah tes atau membuat API palsu. '+milestone['task']+'\nKriteria: '+milestone['acceptance']+'\nCommand: '+command+'\nGALAT AKTUAL: '+output[-4500:]+'\nPertahankan interface dari source sekitar dan schema DB, gunakan path portable. Semua fungsi public lama tetap tersedia.'}
                result=await tools.edit_project_file(child,**args)
                used.append('edit_project_file');trace.append({'alat':'edit_project_file','arg':json.dumps(args)[:400],'hasil':result,'cached':False})
                if result.startswith('Error:'):return {'text':result,'meta':{'tools':used,'trace':trace,'status':'failed'}}
        return {'text':output,'meta':{'tools':used,'trace':trace,'status':'failed','tool_failures':[output[-4500:]]}}
    finally:office.finish(token,{'text':trace[-1]['hasil'] if trace else 'Error: belum dijalankan'})


def fail_checkpoint(job,reason):
    """Recover boundedly from the current source; never advance or fake success."""
    current=db.one('SELECT status FROM project_jobs WHERE id=?',(job['id'],))
    if current and current['status']=='paused':return 'paused'
    if re.search(r'belum memiliki kandidat siap|all models exhausted|rate_limit_exceeded|quota_exhausted|rate-limited|too many requests',reason,re.I):
        db.run("UPDATE project_jobs SET status='waiting_model',result=?,next_run=0,updated_at=? WHERE id=?",('Menunggu kapasitas model; source dan checkpoint dipertahankan. '+reason[:1500],time.time(),job['id']))
        event(job['id'],'waiting_model','Koneksi/model belum memiliki kapasitas; akan dilanjutkan saat model benar-benar siap. '+reason[:1500])
        return 'waiting_model'
    retry=int(job.get('retry_count') or 0)+1
    recover=bool(job.get('autonomous')) and retry<=4
    state='queued' if recover else 'failed'
    next_run=time.time()+min(120,15*retry) if recover else 0
    db.run('UPDATE project_jobs SET status=?,result=?,retry_count=?,next_run=?,updated_at=? WHERE id=?',
           (state,reason[:2000],retry,next_run,time.time(),job['id']))
    event(job['id'],'recovery' if recover else 'failed',
          ('Perbaikan otomatis '+str(retry)+'/4 dari checkpoint yang sama: ' if recover else '')+reason[:2000])
    return state


_model_check_at=0
async def recover_waiting_models():
    global _model_check_at
    now=time.monotonic()
    if now-_model_check_at<30:return
    _model_check_at=now
    rows=db.q("SELECT id,engine FROM project_jobs WHERE status='waiting_model'")
    if not rows:return
    from . import auto_router
    available=await auto_router.discover()
    for row in rows:
        if any(r.get('ready') and (row['engine']=='auto' or row['engine']==r['backend']) for r in available):
            db.run("UPDATE project_jobs SET status='queued',retry_count=0,next_run=0,updated_at=? WHERE id=? AND status='waiting_model'",(time.time(),row['id']))
            event(row['id'],'recovery','Model kembali siap; melanjutkan checkpoint yang sama, tanpa menganggap tahap sudah lulus.')


async def step():
    init();await recover_waiting_models();job=db.one("SELECT * FROM project_jobs WHERE status='queued' AND COALESCE(next_run,0)<=? ORDER BY updated_at,id LIMIT 1",(time.time(),))
    if not job:return False
    if repository_protected(job['brief'],job['repository']):
        reason='Dijeda: repo tujuan ada dalam daftar jangan disentuh. Repo sumber dan salinan lokal dipertahankan. Pilih repo lain untuk implementasi.'
        event(job['id'],'protected',reason)
        db.run("UPDATE project_jobs SET status='paused',result=?,updated_at=? WHERE id=?",(reason,time.time(),job['id']))
        return True
    pid=job['id'];running_projects.add(pid);db.run("UPDATE project_jobs SET status='working',updated_at=? WHERE id=?",(time.time(),pid))
    token=office.start('orchestrator','Proyek #'+str(pid)+': '+job['brief'][:90]);backend=llm.backend_context.set(job['engine']);response=None
    try:
        ctx=tools.Ctx({**db.bot('orchestrator'),'backend':job['engine'],'model':job['model']},db.chat_for('orchestrator',job['channel'],job['ext_id']),job['channel'],job['ext_id'],user_text=job['brief'])
        ctx.project_folder=job['folder']
        ctx.project_autonomous=bool(job.get('autonomous'))
        root=tools._workpath(job['folder'])
        if not root.exists():
            if job['repository']:
                office.phase('Membaca repositori','tool');r=await tools.clone_repository(ctx,url=job['repository'],folder=job['folder']);event(pid,'clone',r)
                if not r.startswith('[kode keluar 0]'):raise ValueError(r)
            else:
                root.mkdir(parents=True);__import__('os').chown(root,config.KERJA_UID,config.KERJA_GID)
        if job['repository']:
            verified=await tools._run_sandboxed(['git','-C',str(root),'rev-parse','--verify','HEAD'],timeout=20,project=True)
            if not verified.startswith('[kode keluar 0]'):
                raise ValueError('Folder proyek dipertahankan, tetapi repo belum valid. '+verified)
        plan=json.loads(job['plan'] or '{}')
        if not plan:
            report=await inspect(job['folder']);event(pid,'inspect',json.dumps(report,ensure_ascii=False)[:8000])
            office.phase('Menyusun tahap berdasarkan kode nyata','thinking')
            prompt=('Plan a substantial coding project in sequential milestones. Use the actual repository tree, README, AGENTS and manifests. '
                    'Do not rewrite an existing repository or ignore its conventions. Return JSON {summary,milestones:[{bot,task,acceptance}]}. '
                    '3-10 milestones. Prefer existing bot IDs: '+','.join(b['id'] for b in db.bots(active_only=True) if b['id']!='orchestrator')+'. '
                    'If a missing domain needs its own expert, include specialists:[{id,name,persona,tools:[tool names]}] and reference its id in milestones. '
                    'Available tools for specialists: '+','.join(ctx.bot['tools'])+'. Each task is a concrete bounded code change or test/review. '
                    'Include reading relevant source, implementation in small increments, build/test commands supported by manifests, integration and final review. '
                    'The VPS has 3.6GB RAM/2CPU, one worker: no parallel heavy builds/model processes, no deployment/email/social/trading or secrets. '
                    'If requirements need credentials, explicitly leave a checkpoint instead of pretending it works. Preserve existing code and user data.')
            local=llm.active_backend()=='local'
            context_limit=3500 if local else 14000
            from . import structured
            plan_schema={'type':'object','properties':{'summary':{'type':'string'},'milestones':{'type':'array','minItems':1,'maxItems':10,'items':{'type':'object','properties':{'bot':{'type':'string'},'task':{'type':'string'},'acceptance':{'type':'string'}},'required':['bot','task','acceptance']}}},'required':['summary','milestones']}
            plan,result=await structured.request([{'role':'system','content':prompt},{'role':'user','content':job['brief'][:2500 if local else 12000]+'\nACTUAL REPO:\n'+json.dumps(report,ensure_ascii=False)[:context_limit]}],label='Rencana tahapan',max_tokens=900 if local else 1800,schema=plan_schema)
            specialists=plan.get('specialists',[])
            if not isinstance(specialists,list) or len(specialists)>4:raise ValueError('Maksimal empat spesialis baru per rencana.')
            aliases={}
            for spec in specialists:
                created=await tools.create_specialist(ctx,name=spec.get('name',''),persona=spec.get('persona',''),tools=spec.get('tools',[]))
                if created.startswith('Error:'):raise ValueError(created)
                aliases[spec['id']]=json.loads(created)['bot'];event(pid,'specialist',created)
            milestones=plan.get('milestones')
            if isinstance(milestones,list):
                for milestone in milestones:milestone['bot']=aliases.get(milestone.get('bot'),milestone.get('bot'))
            if not isinstance(milestones,list) or not 1<=len(milestones)<=12 or any(m.get('bot')=='orchestrator' or not db.bot(m.get('bot','')) or not m.get('task') or not m.get('acceptance') for m in milestones):raise ValueError('Rencana proyek belum valid.')
            db.run('UPDATE project_jobs SET plan=? WHERE id=?',(json.dumps(plan,ensure_ascii=False),pid));event(pid,'plan',json.dumps(plan,ensure_ascii=False))
        cursor=job['cursor'];milestones=plan['milestones']
        if cursor<len(milestones):
            milestone=milestones[cursor]
            # A repository-wide job keeps each target isolated under its workspace.
            # Protected source repositories and earlier work folders are never overwritten.
            stage_folder=job['folder']
            if milestone.get('repository'):
                repository=milestone['repository']
                if not re.fullmatch(r'https://github.com/[\w.-]+/[\w.-]+(?:\.git)?/?',repository):raise ValueError('URL repo tahap tidak valid.')
                if repository_protected(job['brief'],repository):raise ValueError('Repo tahap dilindungi brief pemilik.')
                name=repository.rstrip('/').removesuffix('.git').rsplit('/',1)[-1]
                stage_folder=job['folder']+'/repos/'+name
                root=tools._workpath(stage_folder)
                if not root.exists():
                    output=await tools.clone_repository(ctx,url=repository,folder=stage_folder)
                    event(pid,'clone',output)
                    if not output.startswith('[kode keluar 0]'):raise ValueError(output)
                ctx.project_folder=stage_folder
            selected=capable_worker(milestone,ctx.bot['tools'])
            if selected!=milestone['bot']:
                event(pid,'capability','Tahap dialihkan dari '+milestone['bot']+' ke '+selected+' karena kebutuhan alat build/edit.')
                milestone['bot']=selected
                db.run('UPDATE project_jobs SET plan=? WHERE id=?',(json.dumps(plan,ensure_ascii=False),pid))
            office.phase(f'Tahap {cursor+1}/{len(milestones)}: '+milestone['bot'],'delegating')
            text=('Kerjakan satu tahap proyek di folder '+stage_folder+'. Gunakan inventaris kode yang sudah disediakan; baca hanya source yang perlu diubah. Jangan mengulang pembacaan berkas yang sama tanpa perubahan. '
                  'Untuk kode panjang gunakan edit_project_file agar tidak terpotong dalam JSON alat. Edit melalui write_file untuk berkas pendek. Gunakan run_project_command untuk build/test pada folder proyek. Gunakan preview_project untuk frontend tersimpan dan periksa interaksi/galat; WebGL/layout butuh Chromium opsional. '
                  'run_project_command sudah berjalan di folder proyek; gunakan path relatif seperti backend/app/main.py, bukan mengulangi projects/project-N di dalam command. Berkas panjang dapat dibaca bertahap dengan read_file start_line/max_lines. Jalankan skrip smoke test mandiri langsung dengan python/node; hanya tes yang memang ditulis sebagai pytest memakai pytest. '
                  'Jangan menggunakan build_project yang membuat folder baru. Jangan mengulang proyek dari nol. '
                  'Periksa import/dependensi yang sudah terpasang sebelum memasang ulang; jangan meminta izin instalasi yang tidak diperlukan. Untuk uji server, jangan menjalankan server foreground lalu menunggu timeout. Buat smoke test HTTP localhost (misalnya aiohttp TestClient/TestServer atau harness subprocess) yang memulai server, memeriksa respons, menutup server dan keluar 0. Timeout bukan bukti server sehat. Jalankan tes secara serial; hanya untuk runner Jest gunakan --runInBand; pytest dan unittest tidak menerima flag Jest. Jangan memasang runner lain jika tes proyek sudah berjalan dengan runner yang ada. Pilih test runner ringan bila transpiler menghabiskan RAM. Jangan mengklaim uji berhasil tanpa exit code.\nTujuan proyek: '+job['brief'][:4000]+'\nTahap: '+milestone['task']+'\nKriteria: '+milestone['acceptance'])
            inventory=await inspect(stage_folder)
            if job.get('retry_count'):
                text+='\nCheckpoint sebelumnya belum lulus: '+job['result'][:2000]+'. Perbaiki sebabnya dengan alat nyata; jangan mengulang klaim atau hanya menuliskan tool tag.'
            text+='\nInventaris aktual: '+json.dumps(inventory,ensure_ascii=False)[:6000]
            ctx.stage_goal=milestone['task']+' '+milestone['acceptance']
            before=stage_baseline(pid,cursor,root)
            receipt=receipt_for_stage(pid,cursor,root)
            if receipt and not acceptance_problems(milestone,receipt,before,snapshot(root))[0]:
                response=receipt
                event(pid,'recovery','Hasil tindakan yang diizinkan dipakai untuk tahap ini: hash source masih sama dan kriteria bukti uji terpenuhi. Tidak menjalankan ulang tindakan.')
            else:
                if receipt:text+='\nTindakan yang diizinkan sudah dijalankan, jangan mengulang tanpa alasan. Bukti: '+json.dumps(receipt,ensure_ascii=False)[:3500]
                response=await execute_declared_check(ctx,milestone,milestone['bot']) if job.get('autonomous') and milestone.get('test_command') else None
                if response is None:response=await office.execute(ctx,milestone['bot'],text)
            event(pid,'milestone',json.dumps({'step':cursor+1,'response':response},ensure_ascii=False))
            if (db.one('SELECT status FROM project_jobs WHERE id=?',(pid,)) or {}).get('status')=='paused':return True
            after=snapshot(root);problems,changed=acceptance_problems(milestone,response,before,after)
            if not response.get('approval') and (office.outcome(response)=='failed' or problems):
                correction=text+'\nGalat alat aktual (perbaiki source yang ditunjuk stack trace, jangan hanya mengulang tes): '+json.dumps(response.get('meta',{}).get('tool_failures',[]),ensure_ascii=False)[-4000:]+'\nHasil sebelumnya: '+response.get('text','')[:1500]+'\nPemeriksaan nyata menemukan: '+' '.join(problems)+'\nKerjakan yang belum dilakukan; bukan memberi saran. Jalankan tes dari folder proyek memakai run_project_command. Jangan membaca berkas opsional yang tidak ada.'
                response=await office.execute(ctx,milestone['bot'],correction);event(pid,'correction',json.dumps(response,ensure_ascii=False))
                after=snapshot(root);problems,changed=acceptance_problems(milestone,response,before,after)
            event(pid,'evidence',json.dumps({'changed_files':changed,'acceptance_problems':problems},ensure_ascii=False))
            if problems and office.outcome(response)=='done':raise ValueError(' '.join(problems))
            state=office.outcome(response)
            if state!='done':
                if response.get('approval'):
                    db.run("UPDATE project_jobs SET status='waiting',result=?,approval_id=?,updated_at=? WHERE id=?",(response.get('text',''),response['approval'],time.time(),pid))
                else:fail_checkpoint(job,response.get('text','')+' '+ ' '.join(problems)+' '+ ' '.join(str(f) for f in response.get('meta',{}).get('tool_failures',[]))[-1500:])
                return True
            # No silent "done" for a coding milestone that never executed any allowed tool.
            used=response.get('meta',{}).get('tools',[])
            if 'build_project' in used or 'build_website' in used:raise ValueError('Tahap proyek membuat folder baru; tidak dianggap mengubah proyek yang sedang dikerjakan.')
            if milestone['bot'] in ('teknisi','desainer') and not used:
                raise ValueError('Tahap coding belum memakai alat nyata; hasil disimpan untuk diperiksa, bukan dianggap berhasil.')
            cursor+=1;db.run('UPDATE project_jobs SET cursor=?,result=?,retry_count=0,next_run=0 WHERE id=?',(cursor,response.get('text','')[:10000],pid))
        if cursor>=len(milestones):
            checks=await inspect(job['folder'])
            if not checks['files']:raise ValueError('Folder proyek kosong; tidak membuat ZIP kosong sebagai hasil selesai.')
            event(pid,'final_checks',json.dumps(checks,ensure_ascii=False))
            if any(not c['ok'] for c in checks['checks']):raise ValueError('Pemeriksaan sintaks akhir gagal; lanjutkan perbaikan dari checkpoint.')
            from . import project_archive
            archive=tools._workpath(job['folder']+'-source.zip')
            archive_report=project_archive.create_source_zip(tools._workpath(job['folder']),archive)
            event(pid,'artifact',json.dumps({'file':job['folder']+'-source.zip','bytes':archive.stat().st_size,
                  'included_files':archive_report['included_files'],'omitted_count':len(archive_report['omitted']),
                  'note':'Sumber proyek; pengecualian ada di AGENMINI-ARCHIVE.json. Build/runtime mengikuti bukti log.'}))
            final_state='done' if job.get('autonomous') else 'review'
            db.run("UPDATE project_jobs SET status=?,result=? WHERE id=?",(final_state,'Tahapan selesai dengan bukti uji yang tercatat. ZIP: '+job['folder']+'-source.zip. Batasan/kredensial mengikuti laporan proyek.',pid))
            event(pid,final_state,'Semua tahap dan pemeriksaan akhir tercatat. '+('Kelanjutan sampai selesai diotorisasi pemilik.' if job.get('autonomous') else 'Menunggu penerimaan pemilik.'))
            chat=db.chat_for('orchestrator',job['channel'],job['ext_id'])
            db.add_message(chat['id'],'assistant','Proyek #'+str(pid)+' selesai tahap dan pengujiannya. ZIP sumber terlampir. Rincian serta batasan ada di Workspace.',{'files':[job['folder']+'-source.zip'],'project_id':pid})
        else:
            current=db.one('SELECT status FROM project_jobs WHERE id=?',(pid,))
            if current['status']=='working':db.run("UPDATE project_jobs SET status='queued' WHERE id=?",(pid,))
    except Exception as exc:
        fail_checkpoint(job,str(exc));response={'text':'Error: '+str(exc)}
    finally:
        running_projects.discard(pid);db.run('UPDATE project_jobs SET updated_at=? WHERE id=?',(time.time(),pid));llm.backend_context.reset(backend);office.finish(token,response)
    return True
