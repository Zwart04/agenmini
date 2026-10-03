import json
import os
import tempfile
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="agenmini-tests-"))
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from app import control, web as pages, db, llm, router, config, office, agent, tools, mcp_bridge


from app import main
main.bootstrap()

async def client():
    app = web.Application(middlewares=[control.errors, pages.auth_mw])
    app.add_routes(control.routes)
    app.add_routes(pages.routes)
    c = TestClient(TestServer(app))
    await c.start_server()
    return c


@pytest.mark.asyncio
async def test_admin_auth_and_skill_creation():
    c = await client()
    try:
        response = await c.post('/api/skills', json={'name': 'unauthorized'})
        assert response.status == 401
        headers={'Cookie': 'agen_sesi=' + pages.make_token()}
        response = await c.post('/api/skills', headers=headers, json={'name':'Regression procedure', 'when_to_use':'verify a deployment', 'steps':'Check health before claiming success'})
        assert response.status == 200
        sid = (await response.json())['id']
        assert db.one('SELECT source FROM skills WHERE id=?', (sid,))['source'] == 'manual'
        response = await c.post('/api/skills/from-message', headers=headers, json={'message_id':999999999})
        assert response.status == 200 and 'tidak ditemukan' in (await response.json())['message']
    finally:
        await c.close()


@pytest.mark.asyncio
async def test_router_key_generated_once_and_not_exposed(monkeypatch):
    calls=[]
    async def upstream(method,path,body=None):
        calls.append((method,path))
        if path == '/api/keys': return {'key':'server-only-key'}
        if path == '/api/providers': return {'connections':[{'id':'x','provider':'openai','apiKey':'must-not-leak','accessToken':'secret'}]}
        if path.split('?')[0] == '/api/models': return {'models':[{'provider':'openai','routedModel':'openai/small','name':'Small'}]}
        if path == '/api/combos': return {'combos':[]}
        return {}
    old=db.setting('compatible_key')
    db.set_setting('compatible_key','')
    monkeypatch.setattr(router,'request',upstream)
    try:
        state=await router.state()
        await router.state()
        assert calls.count(('POST','/api/keys')) == 1
        assert state['models'][0]['id'] == 'openai/small'
        assert 'server-only-key' not in json.dumps(state)
        assert 'must-not-leak' not in json.dumps(state)
        assert db.setting('compatible_key') == 'server-only-key'
    finally:
        db.set_setting('compatible_key',old)


def test_router_signed_session(monkeypatch):
    import jwt
    monkeypatch.setenv('ROUTER_JWT_SECRET','disposable-secret-at-least-32-bytes-long')
    token=router.headers()['Cookie'].split('=',1)[1]
    assert jwt.decode(token,'disposable-secret-at-least-32-bytes-long',algorithms=['HS256'])['authenticated'] is True


@pytest.mark.asyncio
async def test_oauth_secrets_stay_server_side_and_state_checked(monkeypatch):
    async def upstream(method,path,body=None):
        return {'state':'expected-state', 'codeVerifier':'server-secret', 'authUrl':'https://example.com/login'}
    monkeypatch.setattr(router,'request',upstream)
    c=await client()
    headers={'Cookie':'agen_sesi='+pages.make_token()}
    try:
        response=await c.post('/api/router/oauth',headers=headers,json={'provider':'codex'})
        payload=await response.json()
        assert 'server-secret' not in json.dumps(payload)
        result=await c.post('/api/router/oauth/'+payload['flow'],headers=headers,json={'callback':'http://localhost:1455/auth/callback?code=abc&state=wrong'})
        assert result.status == 400 and 'State' in (await result.json())['error']
    finally:
        control._oauth.clear()
        await c.close()


@pytest.mark.asyncio
async def test_consultation_removes_sensitive_tools_and_prevents_cycle(monkeypatch):
    target=db.bot('teknisi')
    class FakeTurn:
        def __init__(self,bot,*args,**kwargs):
            assert 'run_shell' not in bot['tools'] and 'write_file' not in bot['tools']
        async def run(self,text): return {'text':'Verified answer'}
    monkeypatch.setattr(agent,'Turn',FakeTurn)
    result=await office.consult('asisten','teknisi','Question')
    assert result == 'Verified answer' and 'teknisi' not in office.presence
    token=office._chain.set(('teknisi',))
    try: assert (await office.consult('asisten','teknisi','Cycle')).startswith('Error:')
    finally: office._chain.reset(token)


@pytest.mark.asyncio
async def test_update_controls_write_flags_not_shell(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    c=await client()
    headers={'Cookie':'agen_sesi='+pages.make_token()}
    try:
        r=await c.post('/api/update',headers=headers,json={'auto':True,'check':True})
        assert r.status == 200 and (tmp_path/'auto-update.enabled').exists()
        assert (tmp_path/'update-request').read_text() == 'check'
        r=await c.post('/api/update',headers=headers,json={'auto':False})
        assert not (tmp_path/'auto-update.enabled').exists()
    finally: await c.close()

@pytest.mark.asyncio
async def test_office_log_contains_real_trace_and_requires_login():
    cid = db.chat_for('asisten', 'office', 'log-regression')['id']
    mid = db.add_message(cid, 'assistant', 'Checked source', {'trace':[{'alat':'read_webpage','hasil':'Verified source'}]})
    c = await client()
    try:
        assert (await c.get('/api/office/log/asisten')).status == 401
        response = await c.get('/api/office/log/asisten', headers={'Cookie':'agen_sesi='+pages.make_token()})
        payload = await response.json()
        row = next(r for r in payload['entries'] if r['id']==mid)
        assert row['trace'][0] == {'tool':'read_webpage','result':'Verified source'}
    finally:
        await c.close()


def test_dot_state_assets_are_small_self_contained_vectors():
    import xml.etree.ElementTree as ET
    folder = config.STATIC_DIR / 'dots'
    for shape in ['round','triangle','square','cloud','star','flame']:
        for state in ['idle','listening','thinking','writing','success','alert','error','asleep']:
            content = (folder / (shape+'-'+state+'.svg')).read_bytes()
            ET.fromstring(content)
            assert len(content) < 6000
            assert b'<script' not in content and b'https:' not in content

def test_hardware_catalogue_does_not_offer_large_model_on_small_vps():
    from app import local_models
    small=local_models.catalogue({'ram_mb':4096,'available_mb':3000,'cpus':2})
    assert small['recommended']=='qwenpaw-2b'
    assert not next(m for m in small['models'] if m['id']=='qwen35-9b')['fits']
    assert local_models.catalogue({'ram_mb':16384,'cpus':4})['recommended']=='qwen35-9b'
    assert local_models.catalogue({'ram_mb':2048})['recommended'] is None


def test_current_price_must_be_supported_by_read_source():
    question='Berapa harga Bitcoin saat ini?'
    assert 'belum terverifikasi' in agent.grounded_current_answer(question,'Harga $117.234',['https://example.com BTC naik 3%'],['web_search'])
    assert 'belum terverifikasi' in agent.grounded_current_answer(question,'Harga $117.234',['https://example.com Harga $110.000'],['web_search','read_webpage'])
    assert '$117.234' in agent.grounded_current_answer(question,'Harga $117.234',['https://example.com Harga $117.234'],['web_search','read_webpage'])


@pytest.mark.asyncio
async def test_password_guard_does_not_ask_model(monkeypatch):
    async def fail(*a,**kw): raise AssertionError('Guard must not ask the model')
    monkeypatch.setattr(llm,'chat',fail)
    result=await agent.Turn(db.bot('asisten'),'web','credential-guard').run('Apa kata sandi email saya?')
    assert 'tidak mengetahui' in result['text']

@pytest.mark.asyncio
async def test_bundled_mcp_is_real_read_only_server():
    import sys
    async with mcp_bridge.connection({'command':sys.executable,'args':['-m','app.builtin_mcp']}) as connection:
        listed=await connection.list_tools()
        assert {t.name for t in listed.tools}=={'hardware','search_skills'}
        assert all(t.annotations.readOnlyHint for t in listed.tools)
        result=await connection.call_tool('hardware',arguments={})
        assert not result.isError and 'recommended' in str(result.structuredContent or result.content)

def test_invented_tool_output_is_rejected():
    assert tools.validate_arguments('run_python',{'code':'print(1)','output':'invented'})

def test_overlapping_bot_turns_do_not_leave_stale_busy_marker():
    first=office.start('overlap-test','first task')
    second=office.start('overlap-test','second task')
    office.finish(first,{'text':'done'})
    assert office.presence['overlap-test']['task']=='second task'
    office.finish(second,{'text':'done'})
    assert 'overlap-test' not in office.presence
    assert not (config.DATA_DIR/'task-busy').exists()

@pytest.mark.asyncio
async def test_negative_feedback_requires_explicit_correction(monkeypatch):
    cid=db.chat_for('asisten','web','feedback-regression')['id']
    mid=db.add_message(cid,'assistant','wrong answer')
    async def fail(*args,**kwargs):raise AssertionError('Do not guess a correction')
    monkeypatch.setattr(agent.memory,'reflect',fail)
    await agent.feedback(mid,False)
    await agent.feedback(mid,False,'Use the verified source instead of guessing')
    assert db.one("SELECT 1 FROM memories WHERE kind='pelajaran' AND text LIKE 'Koreksi pemilik: Use the verified source%'")

@pytest.mark.asyncio
async def test_office_owner_task_waits_for_approval_and_executes_after_login(monkeypatch,tmp_path):
    import asyncio
    from app.tools import Tool
    bot=db.bot('teknisi');old_tools=bot['tools'][:]
    target=tmp_path/'approved.txt'
    async def write(ctx,text):target.write_text(text);return 'Verified write'
    tools.REGISTRY['fixture_write']=Tool('fixture_write','Write fixture','Write a test fixture',{'text':{'type':'string'}},['text'],write,lambda args:'writes fixture data')
    db.save_bot({'id':'teknisi','tools':['fixture_write']})
    async def fake(messages,**kwargs):
        if 'Izin diberikan' in messages[-1].get('content',''):
            return {'content':'Verified write completed','tool_calls':[]}
        return {'content':'','tool_calls':[{'name':'fixture_write','arguments':{'text':'approved'}}]}
    monkeypatch.setattr(llm,'chat',fake)
    tid=office.enqueue('owner','teknisi','Write the fixture',owner_task=True)
    worker=asyncio.create_task(office.loop())
    c=await client()
    try:
        async with asyncio.timeout(5):
            while db.one('SELECT status FROM office_tasks WHERE id=?',(tid,))['status']!='waiting':await asyncio.sleep(.05)
        assert not target.exists()
        response=await c.post('/api/office/approval/'+str(tid),json={'ok':True})
        assert response.status==401 and not target.exists()
        response=await c.post('/api/office/approval/'+str(tid),headers={'Cookie':'agen_sesi='+pages.make_token()},json={'ok':True})
        assert response.status==200
        assert target.read_text()=='approved'
        assert db.one('SELECT status FROM office_tasks WHERE id=?',(tid,))['status']=='done'
        response=await c.post('/api/office/approval/'+str(tid),headers={'Cookie':'agen_sesi='+pages.make_token()},json={'ok':True})
        assert response.status==400
    finally:
        worker.cancel();await c.close();tools.REGISTRY.pop('fixture_write',None)
        db.save_bot({'id':'teknisi','tools':old_tools})


@pytest.mark.asyncio
async def test_settings_cannot_bypass_runtime_switch():
    c = await client()
    old = db.setting('llm_backend')
    try:
        db.set_setting('llm_backend', 'local')
        response = await c.post('/api/settings', headers={'Cookie': 'agen_sesi=' + pages.make_token()}, json={'llm_backend':'router', 'model':'unwanted'})
        assert response.status == 400
        assert db.setting('llm_backend') == 'local'
    finally:
        db.set_setting('llm_backend', old)
        await c.close()

@pytest.mark.asyncio
async def test_office_clear_preserves_active_tasks_and_chat():
    office.init();ids=[];c=await client()
    try:
        for status in ('done','failed','working','waiting','queued'):
            ids.append((status,db.run('INSERT INTO office_tasks(source,target,text,status) VALUES(?,?,?,?)',('owner','teknisi','clear-test',status))))
        before=db.one('SELECT count(*) n FROM messages')['n']
        assert (await c.delete('/api/office/history')).status==401
        response=await c.delete('/api/office/history',headers={'Cookie':'agen_sesi='+pages.make_token()})
        assert response.status==200
        for status,tid in ids:
            assert bool(db.one('SELECT id FROM office_tasks WHERE id=?',(tid,))) == (status not in ('done','failed'))
        assert db.one('SELECT count(*) n FROM messages')['n']==before
    finally:
        for _,tid in ids:db.run('DELETE FROM office_tasks WHERE id=?',(tid,))
        await c.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('allow,outcome,expected',[(True,'done','queued'),(True,'failed','failed'),(False,'done','paused')])
async def test_project_approval_preview_and_decision(monkeypatch,allow,outcome,expected):
    from app import project_jobs
    project_jobs.init();c=await client();aid=pid=None;calls=[]
    try:
        aid=db.run('INSERT INTO approvals(chat_id,bot_id,tool,args,reason,status) VALUES(?,?,?,?,?,?)',(1,'teknisi','run_project_command',json.dumps({'folder':'projects/example','command':'npm test'}),'Run scoped command','menunggu'))
        pid=db.run('INSERT INTO project_jobs(brief,folder,status,approval_id) VALUES(?,?,?,?)',('Approval test','projects/example','waiting',aid))
        headers={'Cookie':'agen_sesi='+pages.make_token()}
        listing=await (await c.get('/api/projects',headers=headers)).json()
        entry=next(p for p in listing['projects'] if p['id']==pid)
        assert json.loads(entry['approval']['args'])['command']=='npm test'
        assert (await c.post(f'/api/projects/{pid}/approval',json={'ok':allow})).status==401
        async def resolve(id,ok):
            calls.append((id,ok));db.run('UPDATE approvals SET status=? WHERE id=?',('diizinkan' if ok else 'ditolak',id))
            return {'text':'Tugas belum berhasil: exit 1' if outcome=='failed' else 'Actual command result','meta':{'status':outcome}}
        monkeypatch.setattr(agent,'resolve_approval',resolve)
        response=await c.post(f'/api/projects/{pid}/approval',headers=headers,json={'ok':allow})
        assert response.status==200 and (await response.json())['status']==expected
        assert db.one('SELECT status FROM project_jobs WHERE id=?',(pid,))['status']==expected
        assert (await c.post(f'/api/projects/{pid}/approval',headers=headers,json={'ok':True})).status==400
        assert calls==[(aid,allow)]
    finally:
        if pid:db.run('DELETE FROM project_jobs WHERE id=?',(pid,));db.run('DELETE FROM project_events WHERE project_id=?',(pid,))
        if aid:db.run('DELETE FROM approvals WHERE id=?',(aid,))
        await c.close()

@pytest.mark.asyncio
async def test_router_quota_is_shown_without_exposing_token_or_hiding_catalog(monkeypatch):
    import time
    async def upstream(method,path,body=None):
        if path=='/api/providers':return {'connections':[{'id':'quota','provider':'antigravity','isActive':True,'testStatus':'active','accessToken':'PRIVATE_FIXTURE','lastError':'QUOTA_EXHAUSTED PRIVATE_FIXTURE','modelLock_real-model':time.time()+3600}]}
        if path.split('?')[0]=='/api/models':return {'models':[{'id':'ag/real-model','provider':'antigravity'},{'id':'ag/other-model','provider':'antigravity'}]}
        return {'combos':[]}
    monkeypatch.setattr(router,'request',upstream)
    old=db.setting('compatible_key');db.set_setting('compatible_key','TEST_KEY')
    try:
        result=await router.state()
        assert result['connections'][0]['available'] is True and result['models'][0]['ready'] is False
        assert result['models'][1]['ready'] is True
        assert 'kuota' in result['connections'][0]['testStatus'] and 'PRIVATE_FIXTURE' not in json.dumps(result)
    finally:db.set_setting('compatible_key',old)
