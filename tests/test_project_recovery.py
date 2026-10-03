import pytest
from app import db,project_jobs,office

def test_indonesian_tes_requires_actual_project_runner():
    parent=db.bot('orchestrator')['tools']
    milestone={'bot':'backend-engineer','task':'Implementasi autentikasi seller','acceptance':'Tes autentikasi berhasil'}
    selected=project_jobs.capable_worker(milestone,parent)
    assert 'run_project_command' in db.bot(selected)['tools']
    problems,_=project_jobs.acceptance_problems(milestone,{'meta':{'trace':[]}},{},{'auth.py':'new'})
    assert any('Build/test' in p for p in problems)

def test_autonomous_retry_preserves_checkpoint_and_has_bound():
    project_jobs.init()
    pid=db.run("INSERT INTO project_jobs(brief,status,cursor,autonomous,retry_count) VALUES('Recovery','working',2,1,0)")
    try:
        for attempt in range(1,6):
            job=db.one('SELECT * FROM project_jobs WHERE id=?',(pid,))
            project_jobs.fail_checkpoint(job,'HTTP assertion failed')
            row=db.one('SELECT status,cursor,retry_count,next_run FROM project_jobs WHERE id=?',(pid,))
            assert row['cursor']==2 and row['retry_count']==attempt
            assert row['status']==('queued' if attempt<=4 else 'failed')
            assert (row['next_run']>0)==(attempt<=4)
    finally:db.run('DELETE FROM project_jobs WHERE id=?',(pid,));db.run('DELETE FROM project_events WHERE project_id=?',(pid,))

@pytest.mark.asyncio
async def test_unattended_project_keeps_global_review_mode_and_tool_scope(monkeypatch,tmp_path):
    from app import agent,llm,tools,config
    from test_agent import FakeLLM,call
    old=db.setting('full_access');db.set_setting('full_access','0')
    seen=[]
    async def command(ctx,folder='',command='',**kwargs):
        seen.append((ctx.project_folder,folder,command));return '[kode keluar 0] verified'
    monkeypatch.setattr(tools.REGISTRY['run_project_command'],'fn',command)
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    monkeypatch.setattr(llm,'chat',FakeLLM([call('run_project_command',folder='projects/assigned',command='pip install pytest'),'Selesai.']))
    turn=agent.Turn(db.bot('teknisi'),'test-project','unattended');turn.project_folder='projects/assigned';turn.project_autonomous=True
    try:
        result=await turn.run('Jalankan dependensi proyek yang ditugaskan')
        assert not result.get('approval') and seen==[('projects/assigned','projects/assigned','pip install pytest')]
        assert db.setting('full_access')=='0'
        monkeypatch.setattr(llm,'chat',FakeLLM([call('run_shell',command='rm -rf /unused')]))
        result=await turn.run('jalankan shell')
        assert result.get('approval')  # project permission never authorizes a host shell
    finally:db.set_setting('full_access',old)

@pytest.mark.asyncio
async def test_raw_unavailable_tool_is_rejected_without_execution(monkeypatch):
    from app import agent,llm,tools
    from test_agent import FakeLLM
    fake=FakeLLM(['<tool>{"name":"run_project_command","arguments":{"folder":"projects/other","command":"npm test"}}</tool>','Tidak dapat menjalankan alat ini.'])
    monkeypatch.setattr(llm,'chat',fake)
    result=await agent.Turn(db.bot('pengingat'),'test-project','raw-unavailable').run('Jalankan build/test dengan run_project_command pada folder proyek yang diberikan dan laporkan hasil galatnya secara lengkap setelah menggunakan alat. Jangan memberi saran saja; lakukan verifikasi dengan alat yang tersedia.')
    assert 'not available' in fake.seen[1]['messages'][-1]['content']
    assert result['meta']['status']=='partial' and not result['meta']['tools']

def test_owner_pause_survives_failed_checkpoint():
    project_jobs.init();pid=db.run("INSERT INTO project_jobs(brief,status,cursor,autonomous,retry_count) VALUES('Pause','paused',2,1,0)")
    try:
        assert project_jobs.fail_checkpoint(db.one('SELECT * FROM project_jobs WHERE id=?',(pid,)),'failed HTTP')=='paused'
        assert db.one('SELECT status,cursor,retry_count FROM project_jobs WHERE id=?',(pid,))=={'status':'paused','cursor':2,'retry_count':0}
    finally:db.run('DELETE FROM project_jobs WHERE id=?',(pid,))
