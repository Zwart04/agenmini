import importlib.util
import os
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('linux_launcher',ROOT/'linux/launcher.py')
launcher=importlib.util.module_from_spec(spec)
if sys.platform.startswith('linux'):spec.loader.exec_module(launcher)
pytestmark=pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Linux desktop launcher')


def test_secret_storage_is_private_and_reused(tmp_path,monkeypatch):
    monkeypatch.setenv('AGENMINI_DATA_DIR',str(tmp_path/'data'))
    data=launcher.private_dir();token=launcher.secret(data,'secret')
    assert len(token)>=32 and launcher.secret(data,'secret')==token
    assert data.stat().st_mode&0o777==0o700
    assert (data/'secret').stat().st_mode&0o777==0o600
    (data/'short').write_text('')
    with pytest.raises(ValueError):launcher.secret(data,'short')
    (data/'link').symlink_to(data/'secret')
    with pytest.raises(ValueError):launcher.secret(data,'link')


def test_launcher_rejects_invalid_ports_and_pid_reuse(tmp_path,monkeypatch):
    monkeypatch.setenv('AGENMINI_PORT','80')
    with pytest.raises(ValueError):launcher.environment(tmp_path)
    monkeypatch.setenv('AGENMINI_PORT','8765');monkeypatch.setenv('AGENMINI_GATEWAY_PORT','8765')
    with pytest.raises(ValueError):launcher.environment(tmp_path)
    assert launcher.identity(os.getpid()) is None
    (tmp_path/'desktop.pid').write_text('{"pid":1,"start":"wrong"}')
    assert launcher.running(tmp_path) is None


def test_coffee_does_not_create_data(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['launcher','coffee'])
    monkeypatch.setattr(launcher,'private_dir',lambda:pytest.fail('Coffee must not initialize data'))
    assert launcher.main()==0
    assert 'Buy me a coffee' in capsys.readouterr().out


def test_desktop_keeps_session_uid_process_limit(monkeypatch):
    from app import tools
    calls=[]
    monkeypatch.setenv('AGENMINI_DESKTOP','1')
    monkeypatch.setattr(tools.resource,'setrlimit',lambda *args:calls.append(args))
    monkeypatch.setattr(tools.os,'setsid',lambda:None)
    tools._kerja_limits()
    assert any(kind==tools.resource.RLIMIT_AS for kind,_ in calls)
    assert not any(kind==tools.resource.RLIMIT_NPROC for kind,_ in calls)
