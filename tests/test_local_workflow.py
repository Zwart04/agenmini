import os,tempfile
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='agen-local-test-')
import pytest
from app import agent,db,tools,config
from test_harnesses import isolated

@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_generated_program_requires_source_review_before_execution(isolated,monkeypatch,backend):
    db.set_setting('llm_backend',backend);db.set_setting('harness_mode','assisted');db.set_setting('full_access','0')
    bot=db.bot('orchestrator');bot.update(backend=backend,tools=['edit_project_file','run_python'])
    async def generate(ctx,folder,path,instructions):
        config.WORK_DIR.mkdir(parents=True,exist_ok=True)
        (config.WORK_DIR/path).write_text('assert 2+2==4\n')
        return 'Berkas diperbarui dan dibaca ulang'
    async def forbidden(*args,**kwargs):pytest.fail('Unreviewed generated program must not execute')
    monkeypatch.setattr(tools,'edit_project_file',generate);monkeypatch.setattr(tools,'run_python',forbidden)
    result=await agent.Turn(bot,'telegram','review-code').run('Buat berkas contoh.py dan uji hasilnya.')
    assert result['approval'] and result['meta']['status']=='paused'

@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_print_only_model_code_cannot_claim_assertions_passed(isolated,monkeypatch,backend):
    db.set_setting('llm_backend',backend);db.set_setting('harness_mode','assisted');db.set_setting('full_access','1')
    bot=db.bot('orchestrator');bot.update(backend=backend,tools=['edit_project_file','run_python'])
    async def generate(ctx,folder,path,instructions):
        config.WORK_DIR.mkdir(parents=True,exist_ok=True)
        (config.WORK_DIR/path).write_text('print("All tests passed")\n')
        return 'Berkas diperbarui dan dibaca ulang'
    async def forbidden(*args,**kwargs):pytest.fail('No assertion test was generated')
    monkeypatch.setattr(tools,'edit_project_file',generate);monkeypatch.setattr(tools,'run_python',forbidden)
    result=await agent.Turn(bot,'web','missing-tests').run('Buat berkas contoh.py dan uji hasilnya.')
    assert result['meta']['status']=='failed' and not result['meta']['files']

@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','online','router'])
async def test_nested_uncalled_assertions_are_really_executed(isolated,monkeypatch,backend):
    db.set_setting('llm_backend',backend);db.set_setting('harness_mode','assisted');db.set_setting('full_access','1')
    bot=db.bot('orchestrator');bot.update(backend=backend,tools=['edit_project_file','run_python'])
    async def generate(ctx,folder,path,instructions):
        config.WORK_DIR.mkdir(parents=True,exist_ok=True)
        (config.WORK_DIR/path).write_text('def total(n): return 1\ndef tests():\n    assert total(10)==17\n')
        return 'Berkas diperbarui dan dibaca ulang'
    async def execute(ctx,code):
        import subprocess,sys
        p=subprocess.run([sys.executable,'-c',code],cwd=config.WORK_DIR,capture_output=True,text=True)
        return '[kode keluar '+str(p.returncode)+']\n'+p.stdout+p.stderr
    monkeypatch.setattr(tools,'edit_project_file',generate);monkeypatch.setattr(tools,'run_python',execute)
    result=await agent.Turn(bot,'tg','hidden-tests').run('Buat berkas contoh.py dan uji hasilnya.')
    assert result['meta']['status']=='failed' and 'AssertionError' in result['meta']['validation']

def test_html_missing_interaction_and_native_popup_cannot_pass_brief():
    from app import coding
    errors=coding.brief_checks('<button>Tambah</button><script>alert("done")</script>','Ada tombol tambah/kurang jumlah pembelian yang memperbarui total harga 19000.')
    assert len(errors)>=3

def test_blank_setup_does_not_delegate_to_missing_template_bots(isolated):
    from app import workflow
    db.run("UPDATE bots SET active=0 WHERE id!='orchestrator'")
    assert not workflow.team_available('Buat file catatan.txt')
    assert not workflow.team_available('Buat landing page toko')
