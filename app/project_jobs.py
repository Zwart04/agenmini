"""Persistent project checkpoints processed by the existing single office worker."""
import json
import time
import re
import ast
from pathlib import Path
from . import db,config,llm,tools,office


def init():
    db.run("CREATE TABLE IF NOT EXISTS project_jobs(id INTEGER PRIMARY KEY,brief TEXT,repository TEXT,folder TEXT,status TEXT,plan TEXT DEFAULT '{}',cursor INTEGER DEFAULT 0,channel TEXT,ext_id TEXT,engine TEXT,model TEXT,result TEXT DEFAULT '',approval_id INTEGER DEFAULT 0,created_at REAL,updated_at REAL)")
    db.run('CREATE TABLE IF NOT EXISTS project_events(id INTEGER PRIMARY KEY,project_id INTEGER,phase TEXT,text TEXT,created_at REAL)')


def event(pid,phase,text):
    db.run('INSERT INTO project_events(project_id,phase,text,created_at) VALUES(?,?,?,?)',(pid,phase,text[:10000],time.time()))


def create(ctx,brief,repository=''):
    init()
    if not str(brief).strip():raise ValueError('Tujuan proyek belum diisi.')
    if repository and not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?/?',repository):raise ValueError('Gunakan URL repo publik GitHub tanpa token.')
    if db.one("SELECT count(*) n FROM project_jobs WHERE status IN ('queued','working','planning')")['n']>=5:raise ValueError('Selesaikan atau jeda proyek sebelumnya; maksimal lima antrean.')
    pid=db.run('INSERT INTO project_jobs(brief,repository,status,channel,ext_id,engine,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
               (brief[:12000],repository,'queued',ctx.channel,ctx.ext_id,ctx.bot.get('backend') or db.setting('llm_backend'),ctx.bot.get('model') or '',time.time(),time.time()))
    folder='projects/project-'+str(pid);db.run('UPDATE project_jobs SET folder=? WHERE id=?',(folder,pid));event(pid,'queued','Proyek dijadwalkan. Progress dihitung dari tahap yang benar-benar selesai.');return pid


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
            elif p.suffix=='.py':ast.parse(p.read_text());checks.append({'file':name,'check':'Python AST','ok':True})
            elif p.suffix=='.js' and len(checks)<50:
                output=await tools._run_sandboxed(['node','--check',str(p)],timeout=10,cwd=root,project=True)
                checks.append({'file':name,'check':'Node syntax','ok':output.startswith('[kode keluar 0]'),'output':output[:500]})
        except (ValueError,SyntaxError) as exc:checks.append({'file':name,'ok':False,'output':str(exc)[:300]})
    return {'files':files,'manifests':manifests,'checks':checks,'note':'Inventaris maksimal 500 berkas. TypeScript/build/runtime belum diuji oleh pemeriksaan sintaks ini.'}


def rows():
    init();result=db.q('SELECT * FROM project_jobs ORDER BY id DESC LIMIT 30')
    for row in result:
        row['plan']=json.loads(row['plan'] or '{}');row['events']=db.q('SELECT phase,text,created_at FROM project_events WHERE project_id=? ORDER BY id DESC LIMIT 12',(row['id'],))
    return result


def snapshot(root):
    import hashlib
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink() and p.stat().st_size<200000 and not any(part in ('.git','node_modules','.venv','__pycache__','dist','build') for part in p.relative_to(root).parts)}


def acceptance_problems(milestone,response,before,after):
    changed=[name for name,value in after.items() if before.get(name)!=value]
    task=milestone['task'];criteria=task+' '+milestone['acceptance'];problems=[]
    if re.search(r'\b(buat|create|implement|ubah|tambah|perbaiki|fix|update|edit|refactor)',task,re.I) and not changed:
        problems.append('Tahap meminta implementasi, tetapi belum ada perubahan berkas di folder proyek.')
    if re.search(r'\b(uji|test|assert|build)',criteria,re.I):
        commands=[t for t in response.get('meta',{}).get('trace',[]) if t.get('alat')=='run_project_command' and t.get('hasil','').startswith('[kode keluar 0]')]
        if not commands:problems.append('Build/test yang diminta belum memiliki perintah nyata dengan exit code 0.')
    return problems,changed


async def step():
    init();job=db.one("SELECT * FROM project_jobs WHERE status='queued' ORDER BY id LIMIT 1")
    if not job:return False
    pid=job['id'];db.run("UPDATE project_jobs SET status='working',updated_at=? WHERE id=?",(time.time(),pid))
    token=office.start('orchestrator','Proyek #'+str(pid)+': '+job['brief'][:90]);backend=llm.backend_context.set(job['engine']);response=None
    try:
        ctx=tools.Ctx({**db.bot('orchestrator'),'backend':job['engine'],'model':job['model']},db.chat_for('orchestrator',job['channel'],job['ext_id']),job['channel'],job['ext_id'],user_text=job['brief'])
        ctx.project_folder=job['folder']
        root=tools._workpath(job['folder'])
        if not root.exists():
            if job['repository']:
                office.phase('Membaca repositori','tool');r=await tools.clone_repository(ctx,url=job['repository'],folder=job['folder']);event(pid,'clone',r)
                if not r.startswith('[kode keluar 0]'):raise ValueError(r)
            else:
                root.mkdir(parents=True);__import__('os').chown(root,config.KERJA_UID,config.KERJA_GID)
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
            result=await llm.chat([{'role':'system','content':prompt},{'role':'user','content':job['brief'][:2500 if local else 12000]+'\nACTUAL REPO:\n'+json.dumps(report,ensure_ascii=False)[:context_limit]}],max_tokens=900 if local else 1800,fmt='json')
            raw=result['content'].strip().removeprefix('```json').removesuffix('```').strip();plan=json.loads(raw)
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
            milestone=milestones[cursor];office.phase(f'Tahap {cursor+1}/{len(milestones)}: '+milestone['bot'],'delegating')
            text=('Kerjakan satu tahap proyek di folder '+job['folder']+'. List folder dahulu. Baca AGENTS.md/README hanya jika ada, lalu source relevan. '
                  'Untuk kode panjang gunakan edit_project_file agar tidak terpotong dalam JSON alat. Edit melalui write_file untuk berkas pendek. Gunakan run_project_command untuk build/test pada folder proyek. Gunakan preview_project untuk frontend tersimpan dan periksa interaksi/galat; WebGL/layout butuh Chromium opsional. '
                  'Jangan menggunakan build_project yang membuat folder baru. Jangan mengulang proyek dari nol. '
                  'Jangan mengklaim uji berhasil tanpa exit code.\nTujuan proyek: '+job['brief'][:4000]+'\nTahap: '+milestone['task']+'\nKriteria: '+milestone['acceptance'])
            before=snapshot(root)
            response=await office.execute(ctx,milestone['bot'],text);event(pid,'milestone',json.dumps({'step':cursor+1,'response':response},ensure_ascii=False))
            after=snapshot(root);problems,changed=acceptance_problems(milestone,response,before,after)
            if not response.get('approval') and (office.outcome(response)=='failed' or problems):
                correction=text+'\nHasil sebelumnya: '+response.get('text','')[:1500]+'\nPemeriksaan nyata menemukan: '+' '.join(problems)+'\nKerjakan yang belum dilakukan; bukan memberi saran. Jalankan tes dari folder proyek memakai run_project_command. Jangan membaca berkas opsional yang tidak ada.'
                response=await office.execute(ctx,milestone['bot'],correction);event(pid,'correction',json.dumps(response,ensure_ascii=False))
                after=snapshot(root);problems,changed=acceptance_problems(milestone,response,before,after)
            event(pid,'evidence',json.dumps({'changed_files':changed,'acceptance_problems':problems},ensure_ascii=False))
            if problems and office.outcome(response)=='done':raise ValueError(' '.join(problems))
            state=office.outcome(response)
            if state!='done':
                db.run('UPDATE project_jobs SET status=?,result=?,approval_id=?,updated_at=? WHERE id=?',('waiting' if response.get('approval') else 'failed',response.get('text',''),response.get('approval',0),time.time(),pid));return True
            # No silent "done" for a coding milestone that never executed any allowed tool.
            used=response.get('meta',{}).get('tools',[])
            if 'build_project' in used or 'build_website' in used:raise ValueError('Tahap proyek membuat folder baru; tidak dianggap mengubah proyek yang sedang dikerjakan.')
            if milestone['bot'] in ('teknisi','desainer') and not used:
                raise ValueError('Tahap coding belum memakai alat nyata; hasil disimpan untuk diperiksa, bukan dianggap berhasil.')
            cursor+=1;db.run('UPDATE project_jobs SET cursor=?,result=? WHERE id=?',(cursor,response.get('text','')[:10000],pid))
        if cursor>=len(milestones):
            checks=await inspect(job['folder'])
            if not checks['files']:raise ValueError('Folder proyek kosong; tidak membuat ZIP kosong sebagai hasil selesai.')
            event(pid,'final_checks',json.dumps(checks,ensure_ascii=False))
            if any(not c['ok'] for c in checks['checks']):raise ValueError('Pemeriksaan sintaks akhir gagal; lanjutkan perbaikan dari checkpoint.')
            import zipfile
            archive=tools._workpath(job['folder']+'-source.zip');total=0
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                for name in checks['files']:
                    path=root/name
                    if any(part.startswith('.') for part in Path(name).parts) or path.suffix in ('.sqlite','.db','.log','.gguf','.pem','.key'):continue
                    size=path.stat().st_size
                    if size>10000000 or total+size>40000000:continue
                    total+=size;z.write(path,name)
            with zipfile.ZipFile(archive) as z:
                if z.testzip():raise ValueError('ZIP proyek gagal CRC.')
            event(pid,'artifact',json.dumps({'file':job['folder']+'-source.zip','bytes':archive.stat().st_size,'note':'Sumber proyek; build/runtime tetap mengikuti bukti log.'}))
            db.run("UPDATE project_jobs SET status='review',result=? WHERE id=?",('Tahapan selesai. ZIP: '+job['folder']+'-source.zip. Periksa hasil serta log build/test; sintaks saja tidak membuktikan seluruh aplikasi berjalan.',pid))
            event(pid,'review','Semua tahap tercatat. Menunggu pemeriksaan/penerimaan pemilik; tidak diterapkan atau dipush otomatis.')
        else:
            current=db.one('SELECT status FROM project_jobs WHERE id=?',(pid,))
            if current['status']=='working':db.run("UPDATE project_jobs SET status='queued' WHERE id=?",(pid,))
    except Exception as exc:
        event(pid,'failed',str(exc));db.run("UPDATE project_jobs SET status='failed',result=? WHERE id=?",(str(exc)[:2000],pid));response={'text':'Error: '+str(exc)}
    finally:
        db.run('UPDATE project_jobs SET updated_at=? WHERE id=?',(time.time(),pid));llm.backend_context.reset(backend);office.finish(token,response)
    return True
