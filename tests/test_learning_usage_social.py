import asyncio,json,time
from pathlib import Path
import pytest
from app import db,llm,office,usage_meter,office_learning,social_connections,config,project_jobs


def test_usage_unknown_price_is_not_zero_and_tariff_is_snapshot(monkeypatch):
    old=db.setting('model_tariffs');marker='meter-regression';token=usage_meter.actor.set(marker)
    try:
        db.set_setting('model_tariffs','{}');usage_meter.record('online','test-model',{'usage_reported':True,'prompt_tokens':100,'tokens':50})
        db.set_setting('model_tariffs',json.dumps({'online|test-model':{'input':2,'output':4}}));usage_meter.record('online','test-model',{'usage_reported':True,'prompt_tokens':100,'tokens':50})
        usage_meter.record('online','test-model',{})
        rows=db.q('SELECT * FROM model_usage WHERE bot=? ORDER BY id',(marker,))
        assert rows[0]['usd'] is None and rows[1]['usd']==pytest.approx(.0004) and rows[2]['usd'] is None
        assert rows[2]['reported']==0
    finally:
        usage_meter.actor.reset(token);db.run('DELETE FROM model_usage WHERE bot=?',(marker,));db.set_setting('model_tariffs',old)


def test_idle_refuses_to_run_during_owner_work(monkeypatch):
    office.init();project_jobs.init();monkeypatch.setattr(office,'presence',{'teknisi':{'status':'working'}})
    assert office_learning.ready(manual=True)[0] is False

@pytest.mark.asyncio
async def test_idle_discussion_serial_and_draft_not_auto_saved(monkeypatch):
    office.init();project_jobs.init();office_learning.init();calls=[];active=0
    jobs=db.q("SELECT id,status FROM project_jobs WHERE status IN ('queued','working','planning')")
    tasks=db.q("SELECT id,status FROM office_tasks WHERE status IN ('queued','working')")
    for row in jobs:db.run("UPDATE project_jobs SET status='paused' WHERE id=?",(row['id'],))
    for row in tasks:db.run("UPDATE office_tasks SET status='paused' WHERE id=?",(row['id'],))
    monkeypatch.setattr(office,'presence',{});monkeypatch.setattr(office_learning,'ready',lambda *a:(True,''))
    before=db.one('SELECT count(*) n FROM memories')['n'];prior=db.one('SELECT max(id) n FROM office_tasks')['n'] or 0
    async def chat(messages,**kw):
        nonlocal active
        active+=1;assert active==1 and kw['tools'] is None and kw['max_tokens']<=220 and kw['prio']==llm.PRIO_BACKGROUND
        assert 'tanpa saran beli/jual' in messages[0]['content'];await asyncio.sleep(.01);calls.append(messages);active-=1
        return {'content':'Usulan: uji aksesibilitas katalog dan lihat hasil kontras warna. Belum diterapkan.'}
    monkeypatch.setattr(llm,'chat',chat)
    result=await office_learning.discuss(manual=True)
    try:
        assert result['ok'] and len(calls)==3
        row=db.one('SELECT status,accepted FROM office_discussions WHERE id=?',(result['id'],))
        assert row=={'status':'draft','accepted':0} and db.one('SELECT count(*) n FROM memories')['n']==before
        assert len(db.q('SELECT * FROM office_discussion_messages WHERE discussion_id=?',(result['id'],)))==3
    finally:
        if result.get('id'):db.run('DELETE FROM office_discussion_messages WHERE discussion_id=?',(result['id'],));db.run('DELETE FROM office_discussions WHERE id=?',(result['id'],))
        db.run('DELETE FROM office_tasks WHERE id>?',(prior,))
        for row in jobs:db.run('UPDATE project_jobs SET status=? WHERE id=?',(row['status'],row['id']))
        for row in tasks:db.run('UPDATE office_tasks SET status=? WHERE id=?',(row['status'],row['id']))


def test_social_saved_token_requires_actual_verification(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'DATA_DIR',tmp_path);social_connections.configure('threads',{'access_token':'TEST_ONLY_TOKEN','client_secret':'TEST_ONLY_SECRET'})
    row=next(r for r in social_connections.status() if r['id']=='threads')
    assert row['credential_found'] and not row['ready'] and 'TEST_ONLY' not in json.dumps(social_connections.status())
    assert (tmp_path/'integrations/social.json').stat().st_mode&0o077==0

@pytest.mark.asyncio
async def test_social_oauth_state_callback_and_replay(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'DATA_DIR',tmp_path);calls=[]
    social_connections.configure('youtube',{'client_id':'TEST_ID','client_secret':'TEST_SECRET','redirect_uri':'http://127.0.0.1/oauth/callback'})
    result=social_connections.start('youtube')
    from urllib.parse import urlparse,parse_qs
    params=parse_qs(urlparse(result['url']).query)
    assert params['scope']==['https://www.googleapis.com/auth/youtube.readonly'] and params['code_challenge_method']==['S256']
    async def exchange(provider,data):calls.append(data);return {'access_token':'TEST_TOKEN','expires_in':3600}
    async def request(provider,path,params):assert path=='channels';return {'items':[{'id':'test','snippet':{'title':'Test Channel'}}]}
    monkeypatch.setattr(social_connections,'exchange',exchange);monkeypatch.setattr(social_connections,'request',request)
    callback='http://127.0.0.1/oauth/callback?state='+params['state'][0]+'&code=TEST_CODE'
    with pytest.raises(ValueError):await social_connections.finish('youtube',callback.replace('127.0.0.1','evil.example'))
    assert (await social_connections.finish('youtube',callback))['ok']
    assert calls[0].get('code_verifier') and 'TEST_SECRET' not in json.dumps(social_connections.status())
    with pytest.raises(ValueError):await social_connections.finish('youtube',callback)

@pytest.mark.asyncio
async def test_social_connection_test_never_posts(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'DATA_DIR',tmp_path);social_connections.configure('threads',{'access_token':'TEST_TOKEN'});seen=[]
    async def request(provider,path,params=None,method='GET',**kw):seen.append((path,method));return {'id':'1','username':'test-account'}
    monkeypatch.setattr(social_connections,'request',request)
    assert (await social_connections.verify('threads'))['ok'];assert seen==[('me','GET')]
    with pytest.raises(ValueError):await social_connections.publish('threads','should never be posted')
    assert seen==[('me','GET')]

@pytest.mark.asyncio
async def test_connection_and_usage_apis_require_login_and_validate_prices(monkeypatch,tmp_path):
    from aiohttp import web
    from aiohttp.test_utils import TestClient,TestServer
    from app import control,web as pages
    app=web.Application(middlewares=[control.errors,pages.auth_mw]);app.add_routes(control.routes)
    async with TestClient(TestServer(app)) as c:
        for path in ('/api/social','/api/setup','/api/office/learning','/oauth/callback'):
            assert (await c.get(path)).status==401
        headers={'Cookie':'agen_sesi='+pages.make_token()}
        response=await c.post('/api/office/usage',headers=headers,json={'model':'test','backend':'online','input':'NaN','output':1})
        assert response.status==400
        response=await c.post('/api/office/learning',headers=headers,json={'enabled':True,'minutes':1,'daily_budget':60000})
        assert response.status==400
        response=await c.post('/api/social/youtube',headers=headers,json={'action':'finish','callback':'https://example.com/oauth/callback?state=none&code=none'})
        assert response.status==400 and 'kedaluwarsa' in (await response.json())['error']
