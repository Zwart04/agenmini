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
