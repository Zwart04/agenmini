import pytest
from app import progress_reports as reports

@pytest.mark.asyncio
async def test_report_requires_authorized_destination(monkeypatch):
    settings={'progress_reports_enabled':'1','progress_report_chat':'unknown'}
    monkeypatch.setattr(reports.db,'setting',lambda k:settings.get(k,''))
    monkeypatch.setattr(reports.telegram,'is_allowed',lambda *a:False)
    with pytest.raises(ValueError):await reports.emit(force=True)

@pytest.mark.asyncio
async def test_report_records_only_confirmed_delivery(monkeypatch):
    settings={'progress_reports_enabled':'1','progress_report_chat':'owner','telegram_token':'fake-token'}
    monkeypatch.setattr(reports.db,'setting',lambda k:settings.get(k,''))
    monkeypatch.setattr(reports.db,'set_setting',lambda k,v:settings.update({k:v}))
    monkeypatch.setattr(reports.telegram,'is_allowed',lambda *a:True)
    monkeypatch.setattr(reports,'snapshot',lambda:('real report','fingerprint',False))
    class Bot:
        async def send(self,*a):return None
    monkeypatch.setattr(reports.telegram,'_running',{'fake-token':Bot()})
    with pytest.raises(RuntimeError):await reports.emit(force=True)
    assert 'progress_report_last_at' not in settings
    async def success(*a):return {'message_id':123}
    reports.telegram._running['fake-token'].send=success
    assert await reports.emit(force=True)==123
    assert settings['progress_report_message_id']=='123'
    assert await reports.emit() is None

@pytest.mark.asyncio
async def test_reports_disabled_by_default(monkeypatch):
    monkeypatch.setattr(reports.db,'setting',lambda k:'')
    assert await reports.emit(force=True) is None
