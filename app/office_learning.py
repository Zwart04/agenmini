"""Bounded, serial discussions when the owner's queue is empty. Drafts are reviewable."""
import asyncio,json,time
from . import db,llm,office,usage_meter
_lock=asyncio.Lock()
TEAMS={'coordination':'Koordinasi','creative':'Kreatif','engineering':'Engineering','research':'Riset'}

def team(bot):
    try:override=json.loads(db.setting('office_teams') or '{}').get(bot['id'])
    except ValueError:override=None
    if override in TEAMS:return override
    if bot['id'] in ('orchestrator','strategi'):return 'coordination'
    if bot['id'] in ('desainer','copywriter'):return 'creative'
    if bot['id'] in ('teknisi','reviewer') or 'edit_project_file' in bot.get('tools',[]):return 'engineering'
    return 'research'

def init():
    db.run('CREATE TABLE IF NOT EXISTS office_discussions(id INTEGER PRIMARY KEY,created_at REAL,status TEXT,topic TEXT,result TEXT DEFAULT "",accepted INTEGER DEFAULT 0)')
    db.run('CREATE TABLE IF NOT EXISTS office_discussion_messages(id INTEGER PRIMARY KEY,discussion_id INTEGER,bot TEXT,text TEXT,created_at REAL)')

def status():
    init();rows=db.q('SELECT * FROM office_discussions ORDER BY id DESC LIMIT 12')
    for row in rows:row['messages']=db.q('SELECT bot,text,created_at FROM office_discussion_messages WHERE discussion_id=? ORDER BY id',(row['id'],))
    return {'enabled':db.setting('office_idle_enabled')=='1','minutes':int(db.setting('office_idle_minutes') or 60),'daily_budget':int(db.setting('office_idle_budget') or 60000),'discussions':rows,'error':db.setting('office_idle_error') or ''}

def ready(manual=False):
    if _lock.locked() or office.presence or llm.gate.busy or llm.gate.waiting():return False,'Model atau bot sedang bekerja.'
    if db.one("SELECT count(*) n FROM project_jobs WHERE status IN ('queued','working','planning')")['n'] or db.one("SELECT count(*) n FROM office_tasks WHERE status IN ('queued','working')")['n']:return False,'Ada pekerjaan pemilik dalam antrean.'
    if not manual and time.time()-llm.activity['last_user']<300:return False,'Menunggu pemilik selesai memakai chat.'
    init();now=time.time();last=db.one('SELECT max(created_at) t FROM office_discussions')['t'] or 0
    if not manual and now-last<60*int(db.setting('office_idle_minutes') or 60):return False,'Belum waktunya diskusi berikut.'
    today=int(now//86400)*86400;rounds=db.one('SELECT count(*) n FROM office_discussions WHERE created_at>=?',(today,))['n']
    if rounds*2000>=int(db.setting('office_idle_budget') or 60000):return False,'Batas diskusi harian tercapai.'
    return True,''

def publish(did,bot,text):
    from . import hub
    db.run('INSERT INTO office_discussion_messages(discussion_id,bot,text,created_at) VALUES(?,?,?,?)',(did,bot,text[:2000],time.time()))
    for queue in tuple(hub.web_listeners):
        try:queue.put_nowait({'type':'office_discussion','discussion':did,'bot':bot,'text':text[:300],'created_at':time.time()})
        except asyncio.QueueFull:pass

async def discuss(manual=False):
    office.init();from . import project_jobs
    project_jobs.init();ok,reason=ready(manual)
    if not ok:return {'ok':False,'reason':reason}
    async with _lock:
        bots=[b for b in db.bots(active_only=True) if b['id']!='orchestrator']
        if len(bots)<2:return {'ok':False,'reason':'Butuh dua anggota tim aktif.'}
        init();number=db.one('SELECT count(*) n FROM office_discussions')['n'];pair=[bots[number%len(bots)],bots[(number+1)%len(bots)]]
        topics=['ide fitur aplikasi yang berguna','ide konten seller Indonesia','pelajaran dari pekerjaan terbaru','literasi investasi dan pertanyaan yang perlu diverifikasi']
        topic=topics[number%len(topics)];did=db.run('INSERT INTO office_discussions(created_at,status,topic) VALUES(?,?,?)',(time.time(),'working',topic))
        text='';messages=[];coordinator=office.start('orchestrator','Diskusi senggang: '+topic);tids=[]
        backend=llm.backend_context.set(db.setting('llm_backend'))
        try:
            for index,bot in enumerate(pair+[db.bot('orchestrator')]):
                if llm.gate.busy or llm.gate.waiting() or db.one("SELECT count(*) n FROM project_jobs WHERE status IN ('queued','working','planning')")['n']:raise RuntimeError('Diskusi dijeda untuk pekerjaan pemilik.')
                if bot['id']!='orchestrator':
                    tid=office.enqueue('orchestrator',bot['id'],'Diskusi senggang: '+topic,owner_task=True);tids.append(tid);db.run("UPDATE office_tasks SET status='working' WHERE id=?",(tid,));office.task_event(tid)
                token=office.start(bot['id'],'Diskusi: '+topic);actor=usage_meter.actor.set(bot['id'])
                try:
                    system=('Diskusi internal singkat, bahasa Indonesia. Sampaikan satu ide yang spesifik dan bisa ditinjau. Maksimal dua paragraf. '
                            'Tidak menjalankan alat, mengubah kode, mengirim pesan luar, atau membuat transaksi. Bedakan usulan dan fakta terverifikasi. '
                            'Investasi: hanya edukasi/pertanyaan riset, tanpa saran beli/jual aset, angka harga terkini atau janji imbal hasil. '
                            'Pelajaran adalah draft sampai pemilik meninjau atau ada bukti uji. Jangan mengklaim bobot/model telah dilatih. ')
                    instruction=('Usulkan satu ide sebagai '+bot['name'] if index==0 else 'Tinjau ide rekan: cari kelemahan dan cara mengujinya.' if index==1 else 'Rangkum satu saran akhir beserta langkah verifikasinya; jelas bahwa ini belum diterapkan.')
                    result=await llm.chat([{'role':'system','content':system},{'role':'user','content':topic+'\n'+instruction+'\n'+'\n'.join(messages)[-1600:]}],tools=None,max_tokens=220,temperature=.6,prio=llm.PRIO_BACKGROUND)
                    text=result.get('content','').strip()
                    if not text:raise RuntimeError('Model belum memberikan saran.')
                    messages.append(bot['name']+': '+text);publish(did,bot['id'],text);office.finish(token,{'text':text})
                    if bot['id']!='orchestrator':db.run("UPDATE office_tasks SET status='done',result=?,updated_at=? WHERE id=?",(text,time.time(),tid));office.task_event(tid)
                except Exception:
                    office.finish(token,{'text':'Error: diskusi belum selesai.'});raise
                finally:usage_meter.actor.reset(actor)
            db.run("UPDATE office_discussions SET status='draft',result=? WHERE id=?",(text,did));db.set_setting('office_idle_error','')
            return {'ok':True,'id':did}
        except Exception as exc:
            db.run("UPDATE office_discussions SET status='paused',result=? WHERE id=?",('Diskusi belum selesai. '+str(exc)[:200],did));db.set_setting('office_idle_error',str(exc)[:200]);return {'ok':False,'reason':str(exc)[:200]}
        finally:
            for tid in tids:
                db.run("UPDATE office_tasks SET status='failed' WHERE id=? AND status='working'",(tid,));office.task_event(tid)
            office.finish(coordinator,{'text':text or 'Error: diskusi dijeda.'});llm.backend_context.reset(backend)

async def loop():
    await asyncio.sleep(60)
    while True:
        try:
            if db.setting('office_idle_enabled')=='1':await discuss()
        except Exception as exc:db.set_setting('office_idle_error',str(exc)[:200])
        await asyncio.sleep(60)
