import json
import time
import pytest
from app import agent, db, tools, office, project_jobs, permissions, web as pages
from test_agent import FakeLLM, call
from test_control import client

@pytest.mark.asyncio
async def test_full_access_executes_once_but_keeps_bot_tool_scope(monkeypatch):
    ran=[]
    async def execute(ctx, command='', **kwargs):
        ran.append(command)
        return '[kode keluar 0] dependency check completed'
    monkeypatch.setattr(tools.REGISTRY['run_shell'],'fn',execute)
    old=db.setting('full_access');db.set_setting('full_access','1')
    try:
        monkeypatch.setattr(agent.llm,'chat',FakeLLM([call('run_shell',command='pip install pytest'),'Selesai.']))
        result=await agent.Turn(db.bot('teknisi'),'web','full-access-test').run('Pasang pytest')
        assert not result.get('approval') and ran==['pip install pytest']
        monkeypatch.setattr(agent.llm,'chat',FakeLLM([call('run_shell',command='pip install pytest'),'Tidak tersedia.']))
        await agent.Turn(db.bot('pengingat'),'web','full-access-scope').run('Pasang pytest')
        assert len(ran)==1
    finally:db.set_setting('full_access',old)

@pytest.mark.asyncio
async def test_mode_requires_owner_and_resumes_checkpoint_without_fake_execution(monkeypatch):
    office.init();project_jobs.init();old=db.setting('full_access');db.set_setting('full_access','0')
    async def sync():pass
    monkeypatch.setattr(pages.telegram,'sync',sync)
    aid=db.run('INSERT INTO approvals(tool,args,reason,created_at) VALUES(?,?,?,?)',('run_project_command','{}','test',time.time()))
    pid=db.run("INSERT INTO project_jobs(brief,folder,status,cursor,approval_id,created_at,updated_at) VALUES(?,?,'waiting',3,?,?,?)",('Full access checkpoint regression','projects/full-access-test',aid,time.time(),time.time()))
    c=await client();headers={'Cookie':'agen_sesi='+pages.make_token()}
    try:
        assert (await c.post('/api/settings',json={'full_access':'1'})).status==401
        assert db.setting('full_access')=='0'
        assert (await c.post('/api/settings',headers=headers,json={'full_access':'yes'})).status==400
        r=await c.post('/api/settings',headers=headers,json={'full_access':'1'})
        assert r.status==200 and (await r.json())['resumed']>=1
        job=db.one('SELECT * FROM project_jobs WHERE id=?',(pid,))
        assert job['status']=='queued' and job['cursor']==3 and job['approval_id']==0
        assert db.one('SELECT status FROM approvals WHERE id=?',(aid,))['status']=='diganti'
        assert not db.one('SELECT * FROM project_stage_receipts WHERE project_id=?',(pid,))
        assert permissions.resume_waiting()==0
    finally:
        await c.close();db.set_setting('full_access',old)
        db.run('DELETE FROM project_jobs WHERE id=?',(pid,))
