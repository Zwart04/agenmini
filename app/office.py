"""Persistent office task queue; one worker and bounded bot consultation."""
import asyncio
import contextvars
import time
from . import db, llm

_chain = contextvars.ContextVar('bot_chain', default=())
presence = {}
_jobs = {}
_recent = {}
_active = contextvars.ContextVar("office_job",default=None)
_context_tokens = {}


def start(bot, text):
    from . import config
    token = object()
    state = {'status':'working','task':text[:100],'since':time.time(),'phase':'thinking'}
    (config.DATA_DIR / 'task-busy').write_text('working')
    log(bot,'start',text[:500])
    _jobs[token] = (bot,state)
    _context_tokens[token] = _active.set(token)
    presence[bot] = state
    broadcast(bot)
    return token


def finish(token, result=None):
    from . import config
    job = _jobs.pop(token,None)
    context_token = _context_tokens.pop(token,None)
    if context_token is not None and _active.get() is token:
        _active.reset(context_token)
        if _active.get() not in _jobs:
            _active.set(None)
    if not job:return
    bot,state = job
    remaining = [s for b,s in _jobs.values() if b==bot]
    if remaining:
        presence[bot] = remaining[-1]
    else:
        presence.pop(bot,None)
        text = (result or {}).get('text','')
        status=outcome(result or {'text':'Error: interrupted'})
        log(bot,status,text[:500])
        _recent[bot] = {'status':'idle','last_status':status,'task':'Terakhir: '+state['task']}
    broadcast(bot)
    if not _jobs:(config.DATA_DIR / 'task-busy').unlink(missing_ok=True)


def phase(text, phase='thinking'):
    job = _jobs.get(_active.get())
    if job:
        job[1]['action'] = text[:100]
        job[1]['phase'] = phase
        broadcast(job[0])


def broadcast(bot):
    from . import hub
    event = {'type': 'activity', 'bot': bot, **state(bot)}
    # Already bounded queues on the existing SSE connection; no task per token.
    for q in tuple(hub.web_listeners):
        try: q.put_nowait(event)
        except asyncio.QueueFull: pass


def state(bot):
    return presence.get(bot) or _recent.get(bot) or {'status':'idle'}


def log(bot,kind,text):
    init()
    db.run('INSERT INTO office_events(bot,kind,text,created_at) VALUES(?,?,?,?)',(bot,kind,text[:800],time.time()))
    db.run('DELETE FROM office_events WHERE id < (SELECT COALESCE(MAX(id),0)-2000 FROM office_events)')


def init():
    db.run('CREATE TABLE IF NOT EXISTS office_events (id INTEGER PRIMARY KEY,bot TEXT,kind TEXT,text TEXT,created_at REAL)')
    db.run('CREATE INDEX IF NOT EXISTS office_events_bot ON office_events(bot,id)')
    db.run('''CREATE TABLE IF NOT EXISTS office_tasks (
        id INTEGER PRIMARY KEY, source TEXT, target TEXT, text TEXT,
        status TEXT DEFAULT 'queued', result TEXT DEFAULT '', created_at REAL, updated_at REAL)''')

    columns={r['name'] for r in db.q('PRAGMA table_info(office_tasks)')}
    for name in ('approval_id','owner_task'):
        if name not in columns:db.run('ALTER TABLE office_tasks ADD COLUMN '+name+' INTEGER DEFAULT 0')


def outcome(result):
    text=result.get('text','')
    if result.get('approval'):return 'waiting'
    return 'failed' if text.startswith(('Error:','Galat:','Terjadi galat','Tugas belum berhasil','Saya belum berhasil','Angka terkini belum terverifikasi','Argumen tidak valid','Pembuatan halaman belum berhasil')) else 'done'


def enqueue(source, target, text, owner_task=False):
    init()
    if not db.bot(target) or not db.bot(target).get('active'):
        raise ValueError('Bot tujuan tidak aktif atau tidak ditemukan.')
    if db.one("SELECT count(*) n FROM office_tasks WHERE status='queued'")['n'] >= 30:
        raise ValueError('Antrean penuh; tunggu tugas sebelumnya selesai.')
    return db.run('INSERT INTO office_tasks(source,target,text,created_at,updated_at,owner_task) VALUES(?,?,?,?,?,?)',
                  (source, target, text[:4000], time.time(), time.time(), int(owner_task)))


async def consult(source, target, text, task_id=None):
    from . import agent
    chain = _chain.get()
    if source == target or target in chain or len(chain) >= 2:
        return 'Error: batas delegasi atau siklus antarbot tercapai.'
    bot = db.bot(target)
    if not bot or not bot.get('active'):
        return 'Error: bot tujuan tidak tersedia.'
    # Consultation cannot widen tool authority to send email, delete data, or execute shell.
    bot = dict(bot)
    allowed = {'web_search', 'read_webpage', 'read_file', 'list_files', 'recall',
               'list_schedules', 'server_status', 'ask_bot'}
    bot['tools'] = [name for name in bot['tools'] if name in allowed]
    token = _chain.set(chain + (source,))
    try:
        async with asyncio.timeout(300):
            turn = agent.Turn(bot, 'office', str(task_id or time.time()), prio=llm.PRIO_TASK)
            turn.display_task = text
            result = await turn.run(
                f'Bot {source} meminta bantuan: {text}\nJawab dengan temuan dan sumber; jangan mengaku melakukan tindakan yang tidak dijalankan.')
        return result['text']
    finally:
        _chain.reset(token)


async def loop():
    init()
    db.run("UPDATE office_tasks SET status='queued' WHERE status='working'")
    while True:
        row = db.one("SELECT * FROM office_tasks WHERE status='queued' ORDER BY id LIMIT 1")
        if not row:
            await asyncio.sleep(2)
            continue
        db.run("UPDATE office_tasks SET status='working',updated_at=? WHERE id=?", (time.time(), row['id']))
        try:
            approval_id=0
            if row.get('owner_task'):
                from . import agent
                async with asyncio.timeout(600):
                    response=await agent.Turn(db.bot(row['target']),'office',str(row['id']),prio=llm.PRIO_TASK).run(row['text'])
                result=response['text'];status=outcome(response);approval_id=response.get('approval',0)
            else:
                result = await consult(row['source'], row['target'], row['text'], row['id'])
                status = outcome({'text':result})
        except Exception as exc:
            result, status, approval_id = str(exc)[:500], 'failed',0
        db.run('UPDATE office_tasks SET result=?,status=?,updated_at=?,approval_id=? WHERE id=?',
               (result[:6000], status, time.time(), approval_id, row['id']))
