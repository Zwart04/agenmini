"""Evidence, permission and checkpoint regressions for coordinated projects."""
import json
import pytest
from app import db,main,tools,config,project_jobs,projects,workflow,llm,office,auto_router
main.bootstrap()


def context(bid='orchestrator'):
    bot=db.bot(bid)
    return tools.Ctx(bot,db.chat_for(bid,'test-project','isolated'),'test-project','isolated')


@pytest.mark.asyncio
async def test_specialist_permissions_identity_and_delegation(monkeypatch,tmp_path):
    ctx=context();ctx.bot={**ctx.bot,'tools':['create_specialist','read_file','write_file','delegate_task']}
    count=len(db.bots())
    denied=await tools.create_specialist(ctx,name='Escalation regression',persona='Expert',tools='run_shell')
    assert denied.startswith('Error:') and len(db.bots())==count
    actual=json.loads(await tools.create_specialist(ctx,name='Test custom domain',persona='Review a domain precisely.',tools='read_file,write_file,create_specialist'))
    bot=db.bot(actual['bot'])
    try:
        assert set(bot['tools'])=={'read_file','write_file'}
        assert (await tools.create_specialist(ctx,name=bot['name'],persona='replacement',tools='read_file')).startswith('Error:')
        assert (await tools.create_specialist(context('asisten'),name='Denied',persona='x',tools='read_file')).startswith('Error:')
        monkeypatch.setattr(config,'WORK_DIR',tmp_path)
        async def execute(self,text,**kw):
            assert self.bot['id']==bot['id'] and 'run_shell' not in self.bot['tools']
            p=tmp_path/'custom.txt';p.write_text('real result')
            return {'text':'Actual result','meta':{'files':['custom.txt'],'tools':['write_file']}}
        from app import agent
        monkeypatch.setattr(agent.Turn,'run',execute)
        result=await office.execute(ctx,bot['id'],'Write output')
        assert result['text']=='Actual result' and ctx.attachments==['custom.txt']
    finally:db.run('DELETE FROM bots WHERE id=?',(bot['id'],))


@pytest.mark.asyncio
async def test_failed_milestone_never_advances(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    ctx=context();pid=project_jobs.create(ctx,'Test checkpoint failure')
    plan={'milestones':[{'bot':'teknisi','task':'Fix','acceptance':'test exits zero'}]}
    db.run('UPDATE project_jobs SET plan=? WHERE id=?',(json.dumps(plan),pid))
    async def failed(*a,**kw):return {'text':'Error: build exit 1','meta':{'tools':['run_project_command']}}
    monkeypatch.setattr(office,'execute',failed)
    try:
        assert await project_jobs.step()
        row=db.one('SELECT status,cursor FROM project_jobs WHERE id=?',(pid,))
        assert row=={'status':'failed','cursor':0}
    finally:
        db.run('DELETE FROM project_jobs WHERE id=?',(pid,));db.run('DELETE FROM project_events WHERE project_id=?',(pid,))


def test_rich_local_layout_and_incomplete_links():
    from app import coding
    html=coding.compact_page({'title':'Seller Studio','headline':'Konten jelas','description':'Untuk seller Indonesia','features':[{'title':'Caption','description':'Buat draf.'}]})
    check=projects.inspect_html(html)
    assert check['ok'] and check['bytes']>10000 and check['sections']>=4 and check['scripts']
    assert not projects.inspect_html(html.replace('id="demo"','id="missing-demo"'))['ok']
    for path in ('../secret.py','.env','/etc/passwd','x/../test.js'):
        with pytest.raises(ValueError):projects.safe_name(path)


@pytest.mark.asyncio
async def test_auto_routing_fallback_is_serial(monkeypatch):
    routes=[{'backend':'online','model':'first','reason':'test'},{'backend':'freellmapi','model':'second','reason':'test'}]
    async def choices(_):return routes
    monkeypatch.setattr(auto_router,'candidates',choices)
    calls=[]
    # Capture the adapter below routing; each failed request completes before fallback.
    original=llm.chat
    async def adapter(*args,**kwargs):
        if llm.active_backend()=='auto':return await original(*args,**kwargs)
        calls.append(llm.active_backend())
        if len(calls)==1:raise llm.LLMError('quota exhausted')
        return {'content':'real response','tool_calls':[],'stats':{'served_model':'second'}}
    monkeypatch.setattr(llm,'chat',adapter)
    token=llm.backend_context.set('auto')
    try:
        result=await llm.chat([{'role':'user','content':'test'}])
        assert calls==['online','freellmapi']
        assert result['content']=='real response' and result['stats']['routing']['backend']=='freellmapi'
    finally:llm.backend_context.reset(token)


def test_game_contract_rejects_missing_touch_and_dom():
    errors=projects.project_errors({'index.html':'<html><body><canvas id="board"></canvas></body></html>','game.js':"document.getElementById('missing');"},'Buat game 2D dengan kontrol HP')
    assert len(errors)==2
    assert not projects.project_errors({'index.html':'<html><body><canvas id="board"></canvas></body></html>','game.js':"document.getElementById('board'); document.querySelectorAll('[data-direction]');"},'Buat game 2D dengan kontrol HP')


def test_partial_tools_not_treated_as_completed_milestone():
    assert office.outcome({'text':'Selesai','meta':{'status':'partial','tool_failures':['build exit 1']}})=='failed'


def test_checkpoint_requires_changed_source_and_real_test():
    milestone={'task':'Buat calculator.py dan uji assert','acceptance':'assert lulus'}
    problems,_=project_jobs.acceptance_problems(milestone,{'meta':{'tools':['list_files']}},{},{})
    assert len(problems)==2
    problems,changed=project_jobs.acceptance_problems(milestone,{'meta':{'trace':[{'alat':'run_project_command','hasil':'[kode keluar 0]\nassert lulus'}]}},{},{'calculator.py':'actualhash'})
    assert problems==[] and changed==['calculator.py']


def test_inline_touch_control_is_validated():
    content={'index.html':'<html><script>document.querySelectorAll("[data-direction]");</script></html>','game.js':''}
    assert not projects.project_errors(content,'Buat game dengan kontrol HP')


@pytest.mark.asyncio
async def test_project_paths_stay_in_assigned_folder(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    root=tmp_path/'projects'/'active';root.mkdir(parents=True)
    ctx=context();ctx.project_folder='projects/active'
    await tools.write_file(ctx,'calculator.py','def add(a,b): return a+b')
    assert (root/'calculator.py').is_file() and not (tmp_path/'calculator.py').exists()
    assert 'return a+b' in await tools.read_file(ctx,'calculator.py')
    for path in ('../../outside.txt','projects/active/../../outside.txt'):
        with pytest.raises(ValueError):tools._ctx_workpath(ctx,path)


def test_template_js_keeps_literal_newline_escapes():
    from app.site_layout import render
    import re
    js=re.search(r'<script>(.*?)</script>',render('x','x','x',[]),re.S).group(1)
    assert r'\n\nCeritakan' in js
    assert '\n\nCeritakan' not in js



@pytest.mark.asyncio
async def test_inline_script_syntax_is_checked():
    assert not await projects.inspect_inline_js('<script>const x="hello\\nworld";</script>')
    assert await projects.inspect_inline_js('<script>const x="hello\nworld";</script>')


@pytest.mark.asyncio
async def test_delegate_inherits_selected_model(monkeypatch):
    from app import agent
    ctx=context();ctx.bot={**ctx.bot,'backend':'online','model':'chosen-owner-model'}
    seen=[]
    async def fake(self,*a,**kw):
        seen.append((self.bot['backend'],self.bot['model']))
        return {'text':'Actual answer','meta':{'files':[]}}
    monkeypatch.setattr(agent.Turn,'run',fake)
    await office.execute(ctx,'copywriter','Draft from owner brief')
    assert seen==[('online','chosen-owner-model')]


@pytest.mark.asyncio
async def test_auto_runtime_reports_actual_candidates(monkeypatch,tmp_path):
    from app import control
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    async def available(*a,**kw):return [{'backend':'freellmapi','model':'actual','ready':True}]
    monkeypatch.setattr(auto_router,'discover',available)
    original=db.setting('llm_backend');db.set_setting('llm_backend','auto')
    try:
        response=await control.engine_runtime(None)
        assert json.loads(response.text)['ready'] is True
    finally:db.set_setting('llm_backend',original)
