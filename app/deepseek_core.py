"""Python adaptation of DeepSeek Harness agent-loop/tool-calls contracts.

Upstream: deepseek-ai/deepseek-harness, MIT, commit
5badb15009ae1756c3afe0ae0cef1faafc290ccc. See docs/DEEPSEEK-CORE.md.
Serial exclusive scheduling, call/result identity, durable lifecycle and
conservative interrupted-call recovery. No Cordis/Node service is installed.
This is an adaptation, not the original dsh runtime or a prompt-only profile.
"""
import asyncio
import contextvars
import json
import time
import uuid
from . import db

current = contextvars.ContextVar('agen_turn_core', default=None)

def ensure():
    db.run('CREATE TABLE IF NOT EXISTS harness_events (id INTEGER PRIMARY KEY, run_id TEXT, chat_id INTEGER, bot_id TEXT, kind TEXT, data TEXT, created_at REAL)')
    db.run('CREATE INDEX IF NOT EXISTS harness_events_chat ON harness_events(chat_id,id)')

def events(chat_id, after=0):
    ensure()
    return [{**dict(row), 'data': json.loads(row['data'])} for row in db.q(
        'SELECT * FROM harness_events WHERE chat_id=? AND id>? ORDER BY id LIMIT 200', (chat_id, after))]

class Core:
    def __init__(self, chat_id, bot_id, callback, seconds=900):
        ensure()
        self.chat_id, self.bot_id, self.callback = chat_id, bot_id, callback
        self.id = uuid.uuid4().hex
        self.deadline = time.monotonic() + max(10, min(float(seconds), 3600))
        self.pending = {}
        self.sequence = 0

    def record(self, kind, data):
        # Never persist model prompts, auth arguments or raw provider responses.
        db.run('INSERT INTO harness_events(run_id,chat_id,bot_id,kind,data,created_at) VALUES(?,?,?,?,?,?)',
               (self.id,self.chat_id,self.bot_id,kind,json.dumps(data,ensure_ascii=False),time.time()))

    async def emit(self, kind, data):
        self.record(kind,data)
        await self.callback('harness', {'run_id':self.id,'kind':kind,**data})

    def remaining(self):
        seconds=self.deadline-time.monotonic()
        if seconds<=0:raise TimeoutError('Batas waktu harness tercapai; periksa log sebelum mengulang tindakan.')
        return seconds

    async def model(self, operation):
        try:return await asyncio.wait_for(operation, self.remaining())
        except BaseException:
            # A coroutine rejected before scheduling must not remain unawaited.
            if hasattr(operation,'close'):operation.close()
            raise

    async def invoke(self, name, args, operation, timeout=150):
        # Every tool is exclusive here: predictable memory and no overlapping writes.
        self.sequence+=1; call_id=str(self.sequence)
        info={'call_id':call_id,'tool':name}
        if name in ('write_file','edit_project_file','read_file','send_file'):
            info['path']=str(args.get('path',''))[:240]
        self.pending[call_id]=info
        try:
            await self.emit('tool/call',info)
            result=await asyncio.wait_for(operation, min(timeout,self.remaining()))
        except (asyncio.CancelledError, TimeoutError):
            await self.emit('tool/result',{**info,'outcome':'unknown','code':'TOOL_OUTCOME_UNKNOWN'})
            self.pending.pop(call_id,None)
            raise
        except Exception:
            await self.emit('tool/result',{**info,'outcome':'error'})
            self.pending.pop(call_id,None)
            raise
        finally:
            if hasattr(operation,'close'):operation.close()
        text=str(result)
        outcome='error' if text.startswith(('Error:','Wrong arguments','Tool ')) or '[kode keluar ' in text and '[kode keluar 0]' not in text else 'returned'
        await self.emit('tool/result',{**info,'outcome':outcome})
        self.pending.pop(call_id,None)
        return result

    async def rejected(self,name,outcome):
        self.sequence+=1
        info={'call_id':str(self.sequence),'tool':name}
        await self.emit('tool/call',info)
        await self.emit('tool/result',{**info,'outcome':outcome})

    async def finish(self, outcome):
        for info in tuple(self.pending.values()):
            await self.emit('tool/result',{**info,'outcome':'unknown','code':'TOOL_OUTCOME_UNKNOWN'})
        self.pending.clear()
        await self.emit('turn/end',{'outcome':outcome})
        # Bound private journal size without changing chat history.
        db.run('WITH recent AS (SELECT id, ROW_NUMBER() OVER (ORDER BY id DESC) AS n, SUM(LENGTH(CAST(data AS BLOB))) OVER (ORDER BY id DESC) AS bytes FROM harness_events) DELETE FROM harness_events WHERE id IN (SELECT id FROM recent WHERE n>2000 OR bytes>8388608)')

async def changed(path, before, after):
    core=current.get()
    if core is not None:
        from .workbench import readable_name
        if not readable_name(path):return
        import hashlib
        await core.emit('file/change',{'path':path,'before':before[:24000],'after':after[:24000],
            'sha256':hashlib.sha256(after.encode()).hexdigest(),'truncated':len(before)>24000 or len(after)>24000})
