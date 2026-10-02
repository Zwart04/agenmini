import asyncio
import json
import os
import tempfile
os.environ.setdefault('DATA_DIR', tempfile.mkdtemp(prefix='agenmini-activity-'))
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from app import db, main, config, model_import, local_models, chat_models, agent, office, hub, llm, native_apps, router, free_router, control
from app import web as pages
main.bootstrap()


@pytest.mark.asyncio
async def test_import_pins_hash_rejects_split_and_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    calls = []
    async def metadata(url):
        calls.append(url)
        return {'sha': 'a'*40, 'siblings': [
            {'rfilename':'good-Q4.gguf','lfs':{'sha256':'b'*64,'size':579615840}},
            {'rfilename':'mmproj.gguf','lfs':{'sha256':'c'*64,'size':2048}},
            {'rfilename':'split-00001-of-00002.gguf','lfs':{'sha256':'d'*64,'size':2048}}]}
    monkeypatch.setattr(model_import, 'metadata', metadata)
    rows = await model_import.inspect('hf', 'https://huggingface.co/owner/model')
    assert len(rows) == 1 and '/resolve/' + 'a'*40 + '/' in rows[0]['url']
    model_import.save(rows[0]); model_import.save(rows[0])
    assert len(model_import.registry()) == 1
    assert next(m for m in local_models.catalogue({'ram_mb':3686,'available_mb':2867})['models'] if m['id']==rows[0]['id'])['fits']
    for name in ('http://127.0.0.1/secret', '../owner', 'owner/../model'):
        with pytest.raises(ValueError): await model_import.inspect('hf', name)
    assert len(calls) == 1
    with pytest.raises(ValueError): model_import.validate({**rows[0], 'file':'../../secret.gguf'})
    with pytest.raises(ValueError): model_import.validate({**rows[0], 'url':'http://127.0.0.1/secret'})


@pytest.mark.asyncio
async def test_ollama_import_uses_single_digest_without_ollama_runtime(monkeypatch):
    async def metadata(url):
        assert url == 'https://registry.ollama.ai/v2/library/qwen3/manifests/0.6b'
        return {'layers':[{'mediaType':'application/vnd.ollama.image.model','digest':'sha256:'+'e'*64,'size':522640096}]}
    monkeypatch.setattr(model_import, 'metadata', metadata)
    row = (await model_import.inspect('ollama', 'qwen3:0.6b'))[0]
    assert row['sha256'] == 'e'*64 and '/blobs/sha256:' in row['url']
    assert row['min_ram_gb'] == 3


@pytest.mark.asyncio
async def test_chat_model_is_scoped_to_history_and_validated(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(office, 'presence', {})
    monkeypatch.setattr(llm.gate, 'busy', False)
    requested=[]
    monkeypatch.setattr(chat_models.runtime_status,'request',lambda *a:requested.append(a))
    async def choices(mode):return [{'id':'real-model','name':'Verified'}]
    monkeypatch.setattr(chat_models, 'choices', choices)
    bot = db.bot('asisten'); chat = db.new_chat(bot['id'], 'test-model', 'scoped')
    try:
        with pytest.raises(ValueError): await chat_models.select(chat, 'router', 'imaginary')
        await chat_models.select(chat, 'router', 'real-model')
        saved=db.one('SELECT * FROM chats WHERE id=?',(chat['id'],))
        assert chat_models.effective(bot, saved)['model']=='real-model'
        assert db.bot(bot['id'])==bot
        db.add_message(chat['id'],'user','Retain this history')
        new=db.new_chat(bot['id'], 'test-model', 'scoped')
        assert chat_models.effective(bot, new)==bot
        db.open_chat(chat['id'])
        assert db.chat_for(bot['id'], 'test-model', 'scoped')['model']=='real-model'
    finally:
        for row in db.q("SELECT id FROM chats WHERE channel='test-model'"):db.delete_chat(row['id'])


@pytest.mark.asyncio
async def test_live_activity_tracks_thinking_tool_writing_and_finish(monkeypatch):
    q=asyncio.Queue(maxsize=30);hub.web_listeners.add(q)
    callbacks=[]
    async def cb(kind,data):callbacks.append((kind,data))
    bot=db.bot('orchestrator')
    token=office.start(bot['id'],'delegate an actual task')
    turn=agent.Turn(bot,'test','activity-sequence',cb)
    try:
        await turn.on_event('status','Berpikir…')
        office.phase('Berdiskusi dengan Riset','delegating')
        office.phase('Membaca berkas','tool')
        await turn.on_event('token','Jawaban')
        await turn.on_event('token',' selesai')
        office.finish(token,{'text':'Done'})
        events=[]
        while not q.empty():events.append(q.get_nowait())
        assert [e.get('phase') for e in events]==['thinking','thinking','delegating','tool','writing',None]
        assert callbacks[-2:]==[('token','Jawaban'),('token',' selesai')]
        assert events[-1]['status']=='idle'
    finally:
        office.finish(token);hub.web_listeners.discard(q)


@pytest.mark.asyncio
async def test_native_dashboards_are_owner_only_and_do_not_forward_owner_cookie(monkeypatch):
    seen=[]
    upstream=web.Application()
    async def handler(req):
        seen.append(dict(req.headers))
        return web.Response(text='<head></head><a href="/dashboard/providers">Providers</a><script src="/_next/static/main.js"></script>', content_type='text/html')
    upstream.router.add_route('*','/{path:.*}',handler)
    source=TestClient(TestServer(upstream));await source.start_server()
    monkeypatch.setattr(router,'base',lambda:str(source.make_url('')).rstrip('/'))
    monkeypatch.setattr(router,'headers',lambda:{'Cookie':'auth_token=native-test'})
    app=web.Application(middlewares=[control.errors,pages.auth_mw]);app.add_routes(native_apps.routes)
    client=TestClient(TestServer(app));await client.start_server()
    try:
        assert (await client.get('/apps/router/dashboard')).status==401
        r=await client.get('/apps/router/dashboard',headers={'Cookie':'agen_sesi='+pages.make_token()})
        assert r.status==200
        text=await r.text()
        assert '/apps/router/dashboard/providers' in text and '/apps/router/_next/static/main.js' in text
        assert seen[-1]['Cookie']=='auth_token=native-test'
        assert 'agen_sesi' not in json.dumps(seen)
        assert (await client.get('/apps/other/dashboard',headers={'Cookie':'agen_sesi='+pages.make_token()})).status==404
    finally:await client.close();await source.close()


def test_free_mount_preserves_routes_and_rebases_api_and_router():
    js='var x=`/`.replace(/\\/$/,``); jsx(Router,{basename:`/`}); jsx(Route,{path:`/keys`}); fetch(`/api/keys`);'
    rewritten=native_apps.rewrite(js,'free','application/javascript')
    assert 'basename:`/apps/free/`' in rewritten and 'path:`/keys`' in rewritten
    assert 'var x=`/apps/free/`' in rewritten


@pytest.mark.asyncio
async def test_website_is_created_verified_and_attached_without_long_tool_json(monkeypatch, tmp_path):
    from app import coding, tools
    monkeypatch.setattr(config, 'WORK_DIR', tmp_path)
    text='<!doctype html><html><head><title>Seller Studio</title></head><body><main>Konten AI untuk seller Indonesia</main></body></html>'
    calls=[]
    async def fake(messages, **kw):
        calls.append((messages,kw))
        return {'content':text,'tool_calls':[],'stats':{}}
    monkeypatch.setattr(llm,'chat',fake)
    monkeypatch.setattr(llm,'active_backend',lambda:'online')
    bot=db.bot('asisten')
    result=await agent.Turn(bot,'test','html-workflow').run('Bisa buatkan saya website/landingpage HTML untuk Seller Studio, membuat konten untuk seller Indonesia memakai AI?')
    assert len(calls)==1 and calls[0][1]['tools'] is None and calls[0][1]['max_tokens']==2600
    assert result['meta']['files'] and result['meta']['tools']==['build_website']
    assert (tmp_path/result['meta']['files'][0]).read_text(encoding='utf-8')==text
    assert 'dilampirkan' in result['text']
    with pytest.raises(ValueError): coding.extract_html('<html><body>cut off')


@pytest.mark.asyncio
async def test_send_missing_file_can_recover_by_writing_and_automatically_attach(monkeypatch, tmp_path):
    from app import tools
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    outputs=[{'tool_calls':[{'name':'send_file','arguments':{'path':'output.py'}}]},
             {'tool_calls':[{'name':'write_file','arguments':{'path':'output.py','content':'print(125*8)'}}]},
             {'content':'Skrip output.py sudah dibuat.'}]
    async def fake(*args,**kwargs):
        return {'content':'','tool_calls':[],'stats':{},**outputs.pop(0)}
    monkeypatch.setattr(llm,'chat',fake)
    result=await agent.Turn(db.bot('asisten'),'test','recover-file').run('Buat dan kirim file output.py')
    assert result['meta']['files']==['output.py']
    assert (tmp_path/'output.py').read_text()=='print(125*8)'
    assert not result['text'].startswith('Tugas belum berhasil')


def test_copied_telegram_history_cannot_reactivate_approvals():
    source=db.new_chat('asisten','tg','copy-test')
    db.add_message(source['id'],'user','Task')
    db.add_message(source['id'],'assistant','Needs approval',{'approval':991})
    copied=db.copy_chat(source['id'],'test-copy','web')
    try:
        assert copied['channel']=='test-copy'
        assert len(db.history(copied['id']))==2
        assert 'approval' not in db.history(copied['id'])[-1]['meta']
        assert db.history(source['id'])[-1]['meta']['approval']==991
    finally:db.delete_chat(source['id']);db.delete_chat(copied['id'])


@pytest.mark.asyncio
async def test_telegram_model_command_and_scoped_callback(monkeypatch, tmp_path):
    from app import telegram
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    monkeypatch.setattr(llm.gate,'busy',False)
    requested=[]
    monkeypatch.setattr(chat_models.runtime_status,'request',lambda *a:requested.append(a))
    async def choices(mode):return [{'id':'actual/model-'+('long'*20),'name':'Actual'}]
    monkeypatch.setattr(chat_models,'choices',choices)
    sent=[]
    class Tg(telegram.TgBot):
        async def send(self,chat_id,text,buttons=None):sent.append((text,buttons))
        async def call(self,*args,**kwargs):return {}
        def bot_for_chat(self,chat):return db.bot('asisten')
    tg=Tg('test-only-token')
    assert await tg.command('fixture-chat','/model router')
    callback=sent[-1][1][0][0]['callback_data']
    assert len(callback.encode())<64
    # callback is still subject to the ordinary paired-owner check.
    monkeypatch.setattr(telegram,'is_allowed',lambda *a:True)
    await tg.on_callback({'id':'test','from':{'id':'owner'},'message':{'chat':{'id':'fixture-chat'},'message_id':1},'data':callback})
    chat=db.chat_for('asisten','tg','fixture-chat')
    assert chat['backend']=='router' and chat['model'].startswith('actual/model-')
    assert 'disimpan' in sent[-1][0]
    other=db.new_chat('riset','tg','fixture-chat');db.add_message(other['id'],'user','Another bot history')
    await tg.command('fixture-chat','/riwayat')
    assert any(button['callback_data']=='buka:'+str(other['id']) for row in sent[-1][1] for button in row)
    assert chat_models.effective({'backend':'local','model':'old'}, {'backend':'local','model':'stale'})['model']==(db.setting('local_model_id') or 'qwenpaw-2b')
    db.delete_chat(other['id']);db.delete_chat(chat['id'])


@pytest.mark.asyncio
async def test_core_diagnostic_reports_actual_failures_and_cleans_scratch(monkeypatch,tmp_path):
    from app import tools
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    async def unavailable(*a,**k):return 'Error: unavailable test sandbox'
    monkeypatch.setattr(tools,'_run_sandboxed',unavailable)
    result=json.loads((await control.check_core_tools(None)).text)
    assert result['checks'][0]['ok']
    assert not result['checks'][1]['ok'] and 'unavailable' in result['checks'][1]['message']
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_compatible_stream_delivers_real_tokens_and_preserves_usage(monkeypatch):
    received=[]
    async def complete(req):
        body=await req.json();assert body['stream'] and body['chat_template_kwargs']['enable_thinking'] is False
        response=web.StreamResponse(headers={'Content-Type':'text/event-stream'})
        await response.prepare(req)
        for piece in ['Halo',' dunia']:
            await response.write(('data: '+json.dumps({'model':'actual-local-model','choices':[{'delta':{'content':piece}}]})+'\n\n').encode())
        await response.write(b'data: {"usage":{"completion_tokens":2},"choices":[]}\n\ndata: [DONE]\n\n')
        return response
    upstream=web.Application();upstream.router.add_post('/v1/chat/completions',complete)
    client=TestClient(TestServer(upstream));await client.start_server()
    monkeypatch.setenv('LOCAL_API_BASE',str(client.make_url('/v1')))
    async def ready():return {'ready':True}
    monkeypatch.setattr(chat_models.runtime_status,'state',ready)
    token=llm.backend_context.set('local')
    async def on_token(piece):received.append(piece)
    try:
        result=await llm._chat_online([{'role':'user','content':'Hai'}],None,.2,None,local=True,on_token=on_token)
        assert received==['Halo',' dunia']
        assert result['content']=='Halo dunia' and result['stats']['tokens']==2
    finally:llm.backend_context.reset(token);await client.close()


@pytest.mark.asyncio
async def test_compact_coding_escapes_model_copy_and_uses_bounded_output(monkeypatch):
    from app import coding
    async def fake(*args,**kw):
        assert kw['max_tokens']==700 and kw['tools'] is None
        return {'content':json.dumps({'title':'Seller Studio','headline':'<script>alert(1)</script>','description':'Konten untuk seller Indonesia.','features':[{'title':'Ide konten','description':'Susun draf sesuai produk.'}]*3})}
    monkeypatch.setattr(llm,'active_backend',lambda:'local');monkeypatch.setattr(llm,'chat',fake)
    html,stats=await coding.generate('Buat website Seller Studio')
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    assert 'grid-template-columns:1fr' in html and 'prototipe' in html


@pytest.mark.asyncio
async def test_repeated_failed_tool_cannot_become_success(monkeypatch):
    from app import tools
    replies=[{'tool_calls':[{'name':'run_python','arguments':{'code':'print(125*8)'}}]}]*2+[{'content':'125 x 8 = 1000.'}]
    async def fake(*a,**k):return {'content':'','tool_calls':[],'stats':{},**replies.pop(0)}
    async def unavailable(*a,**k):return 'Error: isolated execution unavailable'
    monkeypatch.setattr(llm,'chat',fake);monkeypatch.setattr(tools.REGISTRY['run_python'],'fn',unavailable)
    result=await agent.Turn(db.bot('asisten'),'test','duplicate-failed').run('Hitung 125*8 dengan Python')
    assert result['text'].startswith('Tugas belum berhasil')
    assert all(t['hasil'].startswith('Error:') for t in result['meta']['trace'])
    assert office.outcome(result)=='failed'

@pytest.mark.asyncio
async def test_same_local_selection_repairs_disconnected_runtime(monkeypatch):
    from app import chat_models
    requested=[]
    monkeypatch.setattr(chat_models.runtime_status,'request',lambda *args:requested.append(args))
    async def choices(mode): return [{'id':'qwen35-08b','fits':True}]
    async def state(): return {'ready':False,'phase':'failed'}
    monkeypatch.setattr(chat_models,'choices',choices)
    monkeypatch.setattr(chat_models.runtime_status,'state',state)
    old=db.setting('local_model_id')
    db.set_setting('local_model_id','qwen35-08b')
    chat=db.new_chat('asisten','repair-test','same-model')
    db.run('UPDATE chats SET backend=?,model=? WHERE id=?',('local','qwen35-08b',chat['id']))
    try:
        chat=db.one('SELECT * FROM chats WHERE id=?',(chat['id'],))
        await chat_models.select(chat,'local','qwen35-08b')
        assert requested==[('local','qwen35-08b')]
    finally:
        db.delete_chat(chat['id']);db.set_setting('local_model_id',old)
