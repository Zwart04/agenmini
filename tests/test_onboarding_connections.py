import pytest
from aiohttp import web as aio
from aiohttp.test_utils import TestClient, TestServer
from test_harnesses import isolated
from app import auto_router, control, db, llm, onboarding, web


@pytest.mark.parametrize('value',['http://169.254.169.254/v1','http://example.com/v1','http://user:secret@localhost/v1','http://localhost:99999/v1','http://localhost/v1?key=hidden','file:///v1'])
def test_local_discovery_rejects_non_loopback_credentials_and_invalid_ports(value):
    with pytest.raises(ValueError):onboarding.endpoint(value,local=True)


def test_invalid_connection_does_not_change_preferences(isolated):
    before=db.setting('llm_backend')
    for body in ({'source':'invented'},{'source':'online','connection':'gateway','model':''},{'source':'local','connection':'direct','url':'http://169.254.169.254/v1','model':'x'}):
        with pytest.raises(ValueError):onboarding.plan(body)
    assert db.setting('setup_profile')=='pending' and db.setting('llm_backend')==before


@pytest.mark.asyncio
@pytest.mark.parametrize('reply,ready',[('AGEN_OK',True),('not the expected response',False)])
@pytest.mark.parametrize('change_password',[False,True])
async def test_real_local_http_setup_requires_verified_response(isolated,monkeypatch,reply,ready,change_password):
    monkeypatch.setenv('AGENMINI_DESKTOP','1')
    async def models(_):return aio.json_response({'data':[{'id':'local-test-model'}]})
    async def response(request):
        body=await request.json();assert body['model']=='local-test-model'
        return aio.json_response({'choices':[{'message':{'content':reply}}]})
    model_app=aio.Application();model_app.router.add_get('/v1/models',models);model_app.router.add_post('/v1/chat/completions',response)
    model_server=TestServer(model_app);await model_server.start_server()
    app=aio.Application(middlewares=[control.errors,web.auth_mw]);app.add_routes(control.routes);app.add_routes(web.routes)
    client=TestClient(TestServer(app));await client.start_server();headers={'Cookie':'agen_sesi='+web.make_token()}
    url=str(model_server.make_url('/v1'))
    try:
        r=await client.post('/api/setup/local-models',json={'url':url});assert r.status==401
        r=await client.post('/api/setup/local-models',headers=headers,json={'url':url});assert (await r.json())['models']==['local-test-model']
        body={'profile':'blank','harness':'none','source':'local','connection':'direct','url':url,'model':'local-test-model'}
        if change_password:body['password']='test-only-new-password'
        r=await client.post('/api/setup',headers=headers,json=body);assert r.status==200,await r.text()
        if change_password:
            assert (await client.get('/api/setup',headers=headers)).status==401
            headers={'Cookie':'agen_sesi='+web.make_token()}
        assert db.setting('setup_complete')=='0' and db.setting('setup_ai_source')=='local'
        assert db.setting('llm_backend')=='online' and db.setting('auto_9router')=='0'
        r=await client.post('/api/ai/test',headers=headers,json={'backend':'online','model':'local-test-model'});assert r.status==200,await r.text()
        assert (await r.json())['ok']==ready
        assert (db.setting('setup_complete')=='1')==ready
    finally:await client.close();await model_server.close()


@pytest.mark.asyncio
async def test_provider_wide_free_limit_skips_same_provider_in_current_turn(isolated,monkeypatch):
    routes=[{'backend':'router','model':'oc/first','reason':'test'},{'backend':'router','model':'opencode/second','reason':'test'},{'backend':'online','model':'working','reason':'test'}]
    async def candidates(_):return routes
    monkeypatch.setattr(auto_router,'candidates',candidates);monkeypatch.setattr(auto_router,'_cooldown',{})
    original=llm.chat;calls=[]
    async def adapter(*args,**kwargs):
        if llm.active_backend()=='auto':return await original(*args,**kwargs)
        calls.append(args[2])
        if args[2]=='oc/first':raise llm.ProviderError({'error':{'type':'FreeUsageLimitError','message':'Free usage limit reached. Free models work in OpenCode'}})
        return {'content':'actual fallback','stats':{}}
    monkeypatch.setattr(llm,'chat',adapter)
    token=llm.backend_context.set('auto')
    try:
        result=await llm.chat([{'role':'user','content':'hello'}]);assert result['content']=='actual fallback'
        assert calls==['oc/first','working']
        assert auto_router.cooling(routes[1]) and not auto_router.cooling(routes[2])
    finally:llm.backend_context.reset(token)


def test_public_error_does_not_echo_upstream_url_or_credentials():
    error=llm.ProviderError({'error':{'code':'bad_gateway','message':'upstream error https://secret.example/path?api_key=private'}})
    assert error.failure.kind=='upstream' and 'private' not in str(error) and 'https://' not in str(error)
    assert 'provider' in str(error)


@pytest.mark.asyncio
async def test_busy_setup_rejects_connection_change_before_writing(isolated,monkeypatch):
    from app import office
    monkeypatch.setattr(office,'presence',{'orchestrator':{'status':'working'}})
    old=db.setting('llm_backend')
    app=aio.Application(middlewares=[control.errors,web.auth_mw]);app.add_routes(control.routes)
    client=TestClient(TestServer(app));await client.start_server()
    try:
        r=await client.post('/api/setup',headers={'Cookie':'agen_sesi='+web.make_token()},json={'source':'local','connection':'direct','url':'http://127.0.0.1:8080/v1','model':'test','profile':'blank'})
        assert r.status==400 and 'tugas AI aktif' in (await r.json())['error']
        assert db.setting('llm_backend')==old and db.setting('setup_profile')=='pending'
    finally:await client.close()
