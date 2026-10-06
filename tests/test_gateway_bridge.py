import json
import pytest
from app import router,control,web,db
from aiohttp import web as aiohttp_web
from aiohttp.test_utils import TestClient,TestServer
from test_harnesses import isolated

@pytest.fixture
def go_engine(monkeypatch):
    monkeypatch.setattr(router,'_engine_cache',None)
    monkeypatch.setattr(router,'_engine_at',0)

@pytest.mark.asyncio
async def test_go_pkce_contract_and_server_side_verifier(go_engine,monkeypatch):
    calls=[]
    async def request(method,path,body=None):
        calls.append((method,path,body))
        if path=='/api/version':return {'goVersion':'go1.27'}
        if method=='GET':return {'authUrl':'https://auth.example/login','state':'unique','codeVerifier':'PRIVATE_VERIFIER','redirectUri':'http://localhost:1455/auth/callback'}
        return {'status':'authorized','connectionId':'new-account'}
    monkeypatch.setattr(router,'request',request)
    kind,device,data=await router.oauth_begin('codex','http://localhost:8080/callback')
    assert kind=='go' and not device and '/pkce/authorize?' in calls[-1][1]
    result=await router.oauth_exchange({'provider':'codex','engine':kind,'device':False,'data':data},{'code':'callback-code','state':data['state'],'codeVerifier':data['codeVerifier']})
    assert result['status']=='authorized' and calls[-1][1]=='/api/oauth/pkce/exchange'
    assert calls[-1][2]['provider']=='codex'

@pytest.mark.asyncio
async def test_device_session_never_reaches_browser(isolated,go_engine,monkeypatch):
    calls=[]
    async def upstream(method,path,body=None):
        calls.append((method,path,body))
        if path=='/api/version':return {'goVersion':'native'}
        if path.endswith('/start'):return {'device_code':'PRIVATE_DEVICE','user_code':'DISPLAY','verification_uri':'https://example.com/login','session':{'clientSecret':'PRIVATE_CLIENT'}}
        return {'status':'pending'}
    monkeypatch.setattr(router,'request',upstream)
    app=aiohttp_web.Application(middlewares=[control.errors,web.auth_mw]);app.add_routes(control.routes)
    async with TestClient(TestServer(app)) as client:
        headers={'Cookie':'agen_sesi='+web.make_token()}
        r=await client.post('/api/router/oauth',headers=headers,json={'provider':'kiro'});data=await r.json()
        assert r.status==200 and 'PRIVATE' not in json.dumps(data)
        r=await client.post('/api/router/oauth/'+data['flow'],headers=headers,json={})
        assert (await r.json())['pending'] is True
        assert calls[-1][1]=='/api/oauth/device/poll' and calls[-1][2]['session']=={'clientSecret':'PRIVATE_CLIENT'}
        control._oauth.clear()

@pytest.mark.asyncio
async def test_api_accounts_not_hidden_by_usage_only_endpoint(isolated,go_engine,monkeypatch):
    db.set_setting('compatible_key','fixture-key')
    async def upstream(method,path,body=None):
        if path=='/api/version':return {'goVersion':'native'}
        if path=='/api/connections':return [{'provider':'openai','id':'one','isActive':1,'apiKey':'PRIVATE_KEY'}]
        if path.startswith('/api/models?'):return {'models':[{'id':'openai/fixture','provider':'openai'}]}
        if path=='/api/combos':return []
        if path=='/api/providers':pytest.fail('usage-only API would hide OpenAI account')
        return {}
    monkeypatch.setattr(router,'request',upstream)
    result=await router.state()
    assert result['models'][0]['id']=='openai/fixture' and len(result['connections'])==1
    assert 'PRIVATE_KEY' not in json.dumps(result)

@pytest.mark.asyncio
async def test_opencode_keyless_connection_without_fake_key(isolated,go_engine,monkeypatch):
    calls=[]
    async def upstream(method,path,body=None):
        calls.append((method,path,body))
        return {'goVersion':'native'} if path=='/api/version' else {'id':'fixture'}
    monkeypatch.setattr(router,'request',upstream)
    app=aiohttp_web.Application(middlewares=[control.errors,web.auth_mw]);app.add_routes(control.routes)
    async with TestClient(TestServer(app)) as client:
        r=await client.post('/api/router/provider',headers={'Cookie':'agen_sesi='+web.make_token()},json={'provider':'opencode'})
        assert r.status==200 and calls[-1][1]=='/api/connections'
        assert calls[-1][2]['apiKey']==''

def test_arithmetic_words_require_actual_tool():
    from app import agent
    assert not agent.is_light('37 dikali 19',['run_python'])
    assert agent.intents('37 dikali 19',['run_python'])[0][0]=='run_python'
