import pytest
from aiohttp import web as aio
from aiohttp.test_utils import TestClient, TestServer
from app import config, update_control, control, web
from test_agent_learning_profiles import isolated


@pytest.mark.parametrize('data', [None, [], {}, {'install':'yes'}, {'auto':1},
    {'check':True,'install':True}, {'url':'https://elsewhere.invalid/install.sh'}, {'shell':'echo unsafe'}])
def test_update_rejects_non_boolean_or_arbitrary_commands(isolated, monkeypatch, data):
    monkeypatch.setattr(update_control,'managed',lambda:True)
    with pytest.raises(ValueError):update_control.request(data)
    assert not (config.DATA_DIR/'update-request').exists()
    assert not (config.DATA_DIR/'auto-update.enabled').exists()


def test_unmanaged_installation_returns_official_installer_without_queue(isolated, monkeypatch):
    monkeypatch.setattr(update_control,'managed',lambda:False)
    assert not update_control.state()['managed']
    with pytest.raises(ValueError,match='installer/manual'):update_control.request({'install':True})
    assert not (config.DATA_DIR/'update-request').exists()


def test_complete_request_is_published_without_overwriting_pending_install(isolated, monkeypatch):
    monkeypatch.setattr(update_control,'managed',lambda:True)
    original=update_control.os.link
    def link(source,target):
        assert source.read_text()=='install'
        assert not target.exists()
        return original(source,target)
    monkeypatch.setattr(update_control.os,'link',link)
    assert update_control.request({'install':True})['pending']
    with pytest.raises(ValueError,match='sebelumnya'):update_control.request({'check':True})
    assert (config.DATA_DIR/'update-request').read_text()=='install'
    assert not list(config.DATA_DIR.glob('.update-*'))


@pytest.mark.parametrize('raw', ['{bad', 'null', '[]', '"text"', '{"message": [1], "version":"fake", "repository":"https://evil.invalid"}'])
def test_corrupt_status_cannot_replace_version_or_download_destination(isolated, monkeypatch, raw):
    monkeypatch.setattr(update_control,'managed',lambda:True)
    (config.DATA_DIR/'update-status.json').write_text(raw)
    state=update_control.state()
    assert isinstance(state['message'],str) and state['version']!='fake'
    assert state['releases_url']=='https://github.com/Zwart04/agenmini/releases/latest'
    assert state['repository']=='https://github.com/Zwart04/agenmini'


@pytest.mark.parametrize('guard',['harness-install-busy','harness-run-busy'])
def test_pending_update_reports_harness_work_and_processing(isolated, monkeypatch, guard):
    monkeypatch.setattr(update_control,'managed',lambda:True)
    (config.DATA_DIR/guard).write_text('opencode')
    update_control.request({'install':True})
    assert 'harness selesai' in update_control.state()['message']
    (config.DATA_DIR/'update-request').rename(config.DATA_DIR/'update-processing')
    assert update_control.state()['pending']
    with pytest.raises(ValueError):update_control.request({'check':True})


@pytest.mark.asyncio
async def test_update_api_requires_login_and_matching_origin(isolated,monkeypatch):
    monkeypatch.setattr(update_control,'managed',lambda:True)
    app=aio.Application(middlewares=[control.errors,web.auth_mw]);app.add_routes(control.routes)
    client=TestClient(TestServer(app));await client.start_server()
    try:
        response=await client.post('/api/update',json={'install':True})
        assert response.status==401
        headers={'Cookie':'agen_sesi='+web.make_token(),'Origin':'https://evil.invalid'}
        response=await client.post('/api/update',headers=headers,json={'install':True})
        assert response.status==403 and not (config.DATA_DIR/'update-request').exists()
        headers.pop('Origin')
        response=await client.post('/api/update',headers=headers,json={'install':True})
        assert response.status==200 and (await response.json())['pending']
        response=await client.post('/api/update',headers=headers,json={'check':True})
        assert response.status==400 and (config.DATA_DIR/'update-request').read_text()=='install'
    finally:await client.close()


@pytest.mark.parametrize('command',['support','dukung'])
def test_support_cli_prints_exact_owner_link_without_initializing_data(monkeypatch,capsys,command):
    from app import cli
    monkeypatch.setattr(cli.sys,'argv',['agen',command])
    monkeypatch.setattr(cli.main,'bootstrap',lambda:pytest.fail('Support must not initialize or scan host data'))
    cli.run()
    assert 'https://tako.id/Zwart04/gift' in capsys.readouterr().out


def test_windows_or_manual_update_cli_points_to_installer(isolated,monkeypatch,capsys):
    from app import cli
    monkeypatch.setattr(cli.sys,'argv',['agen','update'])
    monkeypatch.setattr(cli.main,'bootstrap',lambda:None)
    monkeypatch.setattr(update_control,'managed',lambda:False)
    cli.run()
    assert update_control.RELEASES_URL in capsys.readouterr().out
    assert not (config.DATA_DIR/'update-request').exists()


def test_cli_busy_update_is_a_clear_error_without_overwriting_request(isolated,monkeypatch):
    from app import cli
    monkeypatch.setattr(cli.sys,'argv',['agen','update'])
    monkeypatch.setattr(cli.main,'bootstrap',lambda:None)
    monkeypatch.setattr(update_control,'managed',lambda:True)
    update_control.request({'check':True})
    with pytest.raises(SystemExit,match='sebelumnya'):cli.run()
    assert (config.DATA_DIR/'update-request').read_text()=='check'
