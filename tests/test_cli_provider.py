import pytest
from app import cli, db


@pytest.mark.parametrize('backend,key',[('online','online_model'),('local','local_model_id'),('router','router_last_model'),('ollama','model')])
def test_model_changes_selected_backend_only(monkeypatch,backend,key):
    saved={}
    monkeypatch.setattr(cli.main,'bootstrap',lambda:None)
    monkeypatch.setattr(cli.llm,'active_backend',lambda:backend)
    monkeypatch.setattr(db,'set_setting',lambda name,value:saved.update({name:value}))
    monkeypatch.setattr(cli.sys,'argv',['agen','model','chosen-model'])
    cli.run()
    assert saved=={key:'chosen-model'}


def test_provider_invalid_name_does_not_write(monkeypatch):
    monkeypatch.setattr(cli.main,'bootstrap',lambda:None)
    monkeypatch.setattr(db,'set_setting',lambda *_:pytest.fail('Invalid provider must not persist'))
    monkeypatch.setattr(cli.sys,'argv',['agen','provider','untrusted'])
    with pytest.raises(SystemExit):cli.run()
