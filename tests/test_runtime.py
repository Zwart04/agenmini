import hashlib
import io
import json
import os
import tempfile
os.environ.setdefault('DATA_DIR', tempfile.mkdtemp(prefix='agenmini-runtime-tests-'))
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from app import config, db, llm, model_runtime, runtime_status, main, free_router, agent, control

main.bootstrap(profile='template')


def fixture_model():
    content = b'GGUF' + b'verified weights' * 100
    return {'id':'fixture', 'file':'fixture.gguf', 'repo':'fixture/model', 'revision':'abc',
            'bytes':len(content), 'sha256':hashlib.sha256(content).hexdigest()}, content


class Response(io.BytesIO):
    status = 200
    headers = {}


def test_download_verification_reuses_good_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    model, content = fixture_model()
    path = model_runtime.download(model, lambda *a,**k: Response(content))
    assert path.read_bytes() == content
    assert json.loads((tmp_path/'runtime-status.json').read_text())['phase']=='verifying'
    assert model_runtime.download(model, lambda *a,**k: pytest.fail('should reuse verified cache')) == path


def test_download_resume_requires_matching_range(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    model, content = fixture_model()
    directory=tmp_path/'models'/'fixture';directory.mkdir(parents=True)
    (directory/'fixture.gguf.part').write_bytes(content[:100])
    def opener(req, **kw):
        assert req.headers['Range']=='bytes=100-'
        response=Response(content[100:]);response.status=206;response.headers={'Content-Range':f'bytes 100-{len(content)-1}/{len(content)}'}
        return response
    assert model_runtime.download(model, opener).read_bytes()==content


def test_corrupt_download_cannot_be_used(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    model, content = fixture_model()
    with pytest.raises(ValueError, match='SHA256'):
        model_runtime.download(model, lambda *a,**k: Response(b'GGUF'+b'x'*(len(content)-4)))
    assert not (tmp_path/'models'/'fixture'/'fixture.gguf').exists()
    assert not (tmp_path/'models'/'fixture'/'fixture.gguf.part').exists()


@pytest.mark.asyncio
async def test_ready_requires_live_matching_model(monkeypatch, tmp_path):
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    original=db.setting
    monkeypatch.setattr(db,'setting',lambda key:{'llm_backend':'local','local_model_id':'fixture'}.get(key,original(key)))
    model_runtime.write_status('loading','Loading')
    app=web.Application();current={'model':'different'}
    async def health(req): return web.json_response({'status':'ok'})
    async def models(req): return web.json_response({'data':[{'id':current['model']}]})
    app.router.add_get('/health',health);app.router.add_get('/v1/models',models)
    c=TestClient(TestServer(app));await c.start_server()
    monkeypatch.setenv('LOCAL_API_BASE',str(c.make_url('/v1')))
    try:
        assert (await runtime_status.state())['phase']=='failed'
        current['model']='fixture'
        model_runtime.write_status('failed','Previous failure')
        assert (await runtime_status.state())['ready'] is True
        (tmp_path/'runtime-request').write_text('local')
        assert (await runtime_status.state())['phase']=='queued'
        with pytest.raises(ValueError): runtime_status.request('api')
    finally: await c.close()


@pytest.mark.asyncio
async def test_free_models_are_live_and_keys_not_exposed(monkeypatch):
    async def models():return [{'id':'actual-id','name':'Actual'}]
    async def request(method,path,body=None):
        if path.endswith('providers'):return {'providers':[{'platform':'groq','name':'Groq','keyless':False}]}
        return [{'id':1,'platform':'groq','key':'must-not-leak','encrypted_key':'never','label':'main','status':'unknown'}]
    monkeypatch.setattr(free_router,'models',models);monkeypatch.setattr(free_router,'request',request)
    state=await free_router.state()
    assert state['models'][0]['id']=='actual-id'
    assert 'must-not-leak' not in json.dumps(state) and 'encrypted_key' not in json.dumps(state)


@pytest.mark.asyncio
async def test_each_bot_has_isolated_backend_and_restores_context(monkeypatch):
    calls=[]
    async def fake(self,*a,**kw):
        calls.append(llm.active_backend())
        if self.bot['id']=='outer':
            await agent.Turn({'id':'inner','backend':'freellmapi'},'test','backend-inner').run('x')
            calls.append(llm.active_backend())
        return {'text':'verified'}
    monkeypatch.setattr(agent.Turn,'_run',fake)
    before=llm.active_backend()
    await agent.Turn({'id':'outer','backend':'router'},'test','backend-outer').run('x')
    assert calls==['router','freellmapi','router']
    assert llm.active_backend()==before


def test_team_seed_preserves_custom_persona():
    assert {'orchestrator','trading','sosmed','copywriter','desainer','reviewer'} <= {b['id'] for b in db.bots()}
    before=db.bot('orchestrator')['persona']
    try:
        db.save_bot({'id':'orchestrator','persona':'My custom coordinator'})
        main.bootstrap(profile='template')
        assert db.bot('orchestrator')['persona']=='My custom coordinator'
    finally: db.save_bot({'id':'orchestrator','persona':before})


@pytest.mark.asyncio
async def test_bot_model_selection_rejects_invented_id(monkeypatch, tmp_path):
    from app import web as pages
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    async def models():return [{'id':'actual-model','name':'Actual model'}]
    monkeypatch.setattr(free_router,'models',models)
    async def sync():pass
    monkeypatch.setattr(pages.telegram,'sync',sync)
    app=web.Application(middlewares=[control.errors,pages.auth_mw]);app.add_routes(control.routes);app.add_routes(pages.routes)
    c=TestClient(TestServer(app));await c.start_server()
    headers={'Cookie':'agen_sesi='+pages.make_token()}
    old=db.bot('orchestrator')
    try:
        r=await c.post('/api/bots',headers=headers,json={'id':'orchestrator','name':'Orchestrator','backend':'freellmapi','model':'invented-id','tools':['ask_bot']})
        assert r.status==400
        assert db.bot('orchestrator')['model']==old['model']
        r=await c.post('/api/bots',headers=headers,json={'id':'orchestrator','name':'Orchestrator','backend':'freellmapi','model':'actual-model','tools':['ask_bot']})
        assert r.status==200 and db.bot('orchestrator')['model']=='actual-model'
        assert (tmp_path/'runtime-request').read_text()=='reconcile'
    finally:db.save_bot(old);await c.close()


@pytest.mark.asyncio
async def test_mode_switch_preserves_fitting_model_and_starts_router_before_auth(monkeypatch):
    from app import local_models
    saved={k:db.setting(k) for k in ('llm_backend','local_model_id','model')}
    calls=[]
    monkeypatch.setattr(runtime_status,'request',lambda *args:calls.append(args))
    monkeypatch.setattr(local_models,'catalogue',lambda:{'models':[{'id':'qwen35-08b','fits':True}], 'recommended':'qwenpaw-2b'})
    async def premature_auth():pytest.fail('router can still be stopped during a mode switch')
    monkeypatch.setattr(control.router,'ensure_key',premature_auth)
    class Request:
        def __init__(self,mode):self.mode=mode
        async def json(self):return {'mode':self.mode}
    try:
        db.set_setting('local_model_id','qwen35-08b')
        db.set_setting('llm_backend','freellmapi')
        assert (await control.change_mode(Request('local'))).status==200
        assert db.setting('local_model_id')=='qwen35-08b'
        assert calls[-1]==('local','qwen35-08b')
        assert (await control.change_mode(Request('router'))).status==200
        assert db.setting('llm_backend')=='router'
        assert calls[-1]==('api',)
    finally:
        for k,v in saved.items():db.set_setting(k,v)
