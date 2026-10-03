from pathlib import Path
import pytest
from app import repository,tools,config

@pytest.mark.asyncio
async def test_clone_failure_does_not_claim_repository(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    monkeypatch.setattr(repository.integrations,'token',lambda _: (_ for _ in ()).throw(ValueError('not connected')))
    async def fail(*args,**kwargs):return '[kode keluar 128]\nfatal: cannot authenticate'
    monkeypatch.setattr(tools,'_run_sandboxed',fail)
    result=await repository.clone('https://github.com/owner/private',tmp_path/'new')
    assert 'Clone gagal' in result and 'Repo terverifikasi' not in result
    assert not (tmp_path/'new').exists()

@pytest.mark.asyncio
async def test_clone_preserves_existing_files(tmp_path):
    target=tmp_path/'old';target.mkdir();(target/'work.txt').write_text('unfinished work')
    result=await repository.clone('https://github.com/owner/repo',target)
    assert result.startswith('Error: folder sudah ada')
    assert (target/'work.txt').read_text()=='unfinished work'

@pytest.mark.asyncio
@pytest.mark.parametrize('url',['https://user:secret@github.com/owner/repo','https://example.com/owner/repo','https://github.com/owner/repo?token=secret'])
async def test_clone_rejects_credential_urls(url,tmp_path):
    result=await repository.clone(url,tmp_path/'new')
    assert result.startswith('Error:') and not (tmp_path/'new').exists()

@pytest.mark.asyncio
async def test_exit_zero_requires_actual_metadata(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    monkeypatch.setattr(repository.integrations,'token',lambda _: (_ for _ in ()).throw(ValueError('not connected')))
    async def fake_success(*args,**kwargs):return '[kode keluar 0]'
    monkeypatch.setattr(tools,'_run_sandboxed',fake_success)
    assert (await repository.clone('https://github.com/owner/repo',tmp_path/'new')).startswith('Error:')

@pytest.mark.parametrize('url,blocked',[('https://github.com/example-owner/protected-app',True),('https://github.com/example-owner/protected-studio.git',True),('https://github.com/example-owner/other',False)])
def test_worker_honors_protected_repository_list(url,blocked):
    from app import project_jobs
    brief="Rapihkan semua repo.\nlist repo yang jangan di sentuh penting:\n- https://github.com/example-owner/protected-app\n- https://github.com/example-owner/protected-studio"
    assert project_jobs.repository_protected(brief,url) is blocked
