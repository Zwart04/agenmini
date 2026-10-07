import pytest
from aiohttp import web as aio
from aiohttp.test_utils import TestClient, TestServer
from app import web, db
from test_agent_learning_profiles import isolated

@pytest.mark.asyncio
async def test_browser_mutations_require_matching_origin(isolated):
    app=aio.Application(middlewares=[web.auth_mw]);app.add_routes(web.routes)
    c=TestClient(TestServer(app));await c.start_server()
    try:
        for origin in ('https://evil.example','http://[invalid','null'):
            r=await c.post('/api/login',json={'password':'test'},headers={'Origin':origin})
            assert r.status==403
        r=await c.post('/api/login',json={},headers={'Sec-Fetch-Site':'cross-site'})
        assert r.status==403
        r=await c.get('/api/me');assert r.status==401
        # Same-origin requests still reach authentication rather than the origin guard.
        origin=str(c.make_url('/')).rstrip('/')
        db.set_setting('web_password_hash',web.hash_pw('test-local-password'))
        r=await c.post('/api/login',json={'password':'test-local-password'},headers={'Origin':origin})
        assert r.status==200
    finally: await c.close();web._fail.clear()

@pytest.mark.asyncio
async def test_forwarded_ip_cannot_bypass_login_throttle(isolated):
    app=aio.Application(middlewares=[web.auth_mw]);app.add_routes(web.routes)
    c=TestClient(TestServer(app));await c.start_server()
    import time
    web._fail['127.0.0.1']=[time.time()]*8
    try:
        r=await c.post('/api/login',json={},headers={'X-Forwarded-For':'198.51.100.77'})
        assert r.status==429
    finally: await c.close();web._fail.clear()
