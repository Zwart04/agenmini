import json
import pytest
from test_harnesses import isolated
from app import profiles,db,config,host_setup,web,control

def test_orchestrator_and_optional_bot_presets_preserve_user_data(isolated):
    assert [b['id'] for b in db.bots()]==['orchestrator']
    profiles.choose('blank')
    db.save_bot({'id':'riset','name':'Riset milik saya','persona':'Instruksi pribadi','tools':[]})
    before=profiles.status()
    assert profiles.install_bots(['riset','sosmed'])==['sosmed']
    assert db.bot('riset')['persona']=='Instruksi pribadi'
    assert profiles.status()['skills']==before['skills'] and profiles.status()['memories']==before['memories']
    assert profiles.install_bots(['sosmed'])==[]
    with pytest.raises(ValueError):profiles.install_bots(['invented'])

def test_skill_template_can_be_selected_without_bot_templates(isolated):
    from app import main
    profiles.choose('template',bot_templates=False)
    assert [b['id'] for b in db.bots()]==['orchestrator']
    assert profiles.status()['skills']>0
    main.bootstrap()
    assert [b['id'] for b in db.bots()]==['orchestrator']

@pytest.mark.parametrize('ram,swap,recommended',[(1800,0,4),(3700,0,2),(9000,0,0),(3700,2048,0)])
def test_swap_recommendation_uses_physical_memory_and_preserves_existing(isolated,ram,swap,recommended):
    (config.DATA_DIR/'hardware.json').write_text(json.dumps({'ram_mb':ram,'swap_mb':swap}))
    assert host_setup.status()['recommended_swap_gb']==recommended

def test_host_requests_are_explicit_fixed_and_deduplicated(isolated,monkeypatch):
    monkeypatch.setattr(host_setup,'status',lambda:{'managed':True,'ram_mb':3700})
    for data in ({'swap_gb':True},{'swap_gb':99},{'retry':'../../shell'},{'harness_memory':'yes'}):
        with pytest.raises(ValueError):host_setup.request(**data)
    host_setup.request(2,True,'omp')
    assert json.loads((config.DATA_DIR/'host-setup-request.json').read_text())=={'swap_gb':2,'harness_memory':True,'retry':'omp'}
    with pytest.raises(ValueError,match='menunggu'):host_setup.request(2)

@pytest.mark.asyncio
async def test_setup_password_auth_and_main_bot_guard(isolated):
    from aiohttp import web as aio
    from aiohttp.test_utils import TestClient,TestServer
    app=aio.Application(middlewares=[control.errors,web.auth_mw]);app.add_routes(control.routes);app.add_routes(web.routes)
    c=TestClient(TestServer(app));await c.start_server()
    try:
        r=await c.post('/api/host-setup',json={'swap_gb':2});assert r.status==401
        h={'Cookie':'agen_sesi='+web.make_token()}
        r=await c.post('/api/setup',headers=h,json={'profile':'blank','password':'tiny'})
        assert r.status==400 and db.setting('setup_profile')=='pending'
        r=await c.post('/api/setup',headers=h,json={'profile':'blank','bot_templates':True,'password':'test-setup-password'})
        assert r.status==200 and len(db.bots())==10
        r=await c.get('/api/bot-templates',headers=h);assert r.status==401
        h={'Cookie':'agen_sesi='+web.make_token()}
        r=await c.delete('/api/bots/orchestrator',headers=h);assert r.status==400 and db.bot('orchestrator')
        assert web.verify_pw('test-setup-password')
    finally:await c.close()
