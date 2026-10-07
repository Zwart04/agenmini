"""Evidence, permission and checkpoint regressions for coordinated projects."""
import json
import pytest
from app import db,main,tools,config,project_jobs,projects,workflow,llm,office,auto_router
main.bootstrap(profile='template')


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
    problems,changed=project_jobs.acceptance_problems(milestone,{'meta':{'trace':[{'alat':'run_project_command','arg':'python -c assert_calculator_test','hasil':'[kode keluar 0]\nassert lulus'}]}},{},{'calculator.py':'actualhash'})
    assert problems==[] and changed==['calculator.py']


def test_inline_touch_control_is_validated():
    content={'index.html':'<html><script>document.querySelectorAll("[data-direction]");</script></html>','game.js':''}
    assert not projects.project_errors(content,'Buat game dengan kontrol HP')

def test_generated_html_rejects_multifile_dump_and_missing_requested_controls():
    html='<!doctype html><html><head><title>Editor</title><meta name="viewport" content="width=device-width"></head><body><textarea id="editor"></textarea></body></html>'
    assert projects.inspect_html(html,{'editor'},strict=True)['ok']
    assert not projects.inspect_html(html,{'editor','saveBtn'},strict=True)['ok']
    assert not projects.inspect_html('index.html\n```html\n'+html+'\n```\napp.js\nalert(1)',strict=True)['ok']
    assert not projects.inspect_html(html.replace('</body>','<input id="editor"></body>'))['ok']
    assert projects.inspect_html(html.replace('</body>','<video><source src="missing.mp4"></video></body>'))['resources']==['missing.mp4']

def test_control_contract_does_not_mistake_control_types_for_ids():
    assert projects.requested_controls('ID fileInput, timeline. Pastikan semua ID sesuai HTML. Each ID occurs once.')=={'fileInput','timeline'}
    assert projects.requested_controls('input ID imageFile, select ID outputFormat, input widthInput, tombol convertBtn dan link downloadLink.')=={'imageFile','outputFormat','widthInput','convertBtn','downloadLink'}
    assert projects.requested_controls('ID fileInput, editor, findText, replaceText, replaceBtn, saveBtn, resetBtn, wordCount.')=={'fileInput','editor','findText','replaceText','replaceBtn','saveBtn','resetBtn','wordCount'}


def test_explicit_media_controls_cannot_be_replaced_by_buttons():
    types=projects.typed_controls('input type=file ID fileInput, video ID preview, link downloadLink, input type=number ID endInput.')
    assert types=={'fileInput':{'tag':'input','type':'file'},'preview':{'tag':'video'},'downloadLink':{'tag':'a'},'endInput':{'tag':'input','type':'number'}}
    html='<html><head><title>Editor</title><meta name="viewport"></head><body><button id="fileInput">Import</button></body></html>'
    assert not projects.inspect_html(html,required_controls={'fileInput':types['fileInput']})['ok']
    assert projects.inspect_html(html.replace('</body>','<a id="downloadLink" href="#" download>Download</a></body>'))['ok']


@pytest.mark.asyncio
async def test_local_styles_receive_actual_markup_and_design_before_generation(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    plan={'name':'Video editor','files':[{'path':p,'purpose':'actual UI'} for p in ('style.css','index.html','app.js','README.md')],'instructions':'Open index.html',
          'interface':{'layout':'Mint sidebar and preview panel','controls':{'playBtn':{'tag':'button','type':'none','label':'Play'}}}}
    async def request(*a,**kw):
        controls=kw['schema']['properties']['interface']['properties']['controls']
        assert controls['required']==['playBtn'] and controls['additionalProperties'] is False
        return plan,{}
    monkeypatch.setattr(projects.structured,'request',request)
    sources=[
        '<!doctype html><html><head><title>Vidéo 日本語</title><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="style.css"></head><body><main class="preview-panel"><button id="playBtn">Play</button></main><script src="app.js" defer></script></body></html>',
        '.preview-panel{display:grid;gap:16px}button{background:#0fc;color:#111}',
        'document.getElementById("playBtn").onclick=()=>{};',
        '# Open index.html'
    ];seen=[]
    async def chat(messages,**kw):
        seen.append((messages[-1]['content'],kw['max_tokens']))
        return {'content':sources[len(seen)-1],'stats':{'finish_reason':'stop'}}
    async def checked(*a,**kw):return '[kode keluar 0]'
    monkeypatch.setattr(llm,'chat',chat);monkeypatch.setattr(tools,'_run_sandboxed',checked)
    token=llm.backend_context.set('local')
    try:await projects.generate('Buat web app video editor dengan aksen mint. ID playBtn.',context())
    finally:llm.backend_context.reset(token)
    assert 'CURRENT FILE: index.html' in seen[0][0] or 'HTML user interface' in seen[0][0]
    assert 'Mint sidebar and preview panel' in seen[0][0] and '"tag": "button"' in seen[0][0]
    assert 'class="preview-panel"' in seen[1][0] and 'aksen mint' in seen[1][0]
    assert 'Existing classes: preview-panel' in seen[1][0] and seen[1][1]>=1600
    assert any(tmp_path.glob('project-*/project.zip'))


def test_video_app_not_a_landing_page_cannot_use_copy_template():
    from app import coding
    prompt='Build a web app video editor, not a landing page or mockup.'
    assert coding.functional_request(prompt) and projects.project_request(prompt)
    assert not coding.website_request(prompt)
    assert coding.website_request('Build a landing page for a web app video editor.')

def test_fenced_file_recovery_never_includes_neighbor_module():
    response='index.html\n```html\n<html>model source</html>\n```\napp.js\n```javascript\nthrow new Error("different file")\n```'
    assert projects.unwrap_file(response,'index.html')=='<html>model source</html>'
    assert projects.unwrap_file('```javascript\nconst incomplete =','app.js')=='```javascript\nconst incomplete ='


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

@pytest.mark.asyncio
async def test_windows_project_path_is_not_prefixed_twice(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    ctx=context();ctx.project_folder='projects/active'
    await tools.write_file(ctx,r'projects\active\result.txt','actual source')
    assert (tmp_path/'projects/active/result.txt').read_text()=='actual source'
    assert not (tmp_path/'projects/active/projects').exists()
    assert await tools.read_file(ctx,r'projects\active\result.txt')=='actual source'


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
async def test_browser_scripts_cannot_redeclare_state_or_use_node_exports():
    contents={'index.html':'<script src="media.js" defer></script><script src="export.js" defer></script>',
              'media.js':'const media={}; module.exports=media;', 'export.js':'const media={};'}
    errors=await projects.inspect_browser_js(contents)
    assert any('CommonJS' in error for error in errors) and any('duplicate declarations' in error for error in errors)
    contents['media.js']='const media={};';contents['export.js']='media.busy=false;'
    assert not await projects.inspect_browser_js(contents)
    contents['index.html']=contents['index.html'].replace(' defer',' type="module"')
    contents['export.js']='const media={};'
    assert not await projects.inspect_browser_js(contents)


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

@pytest.mark.parametrize('allowed,result,state',[(True,'[kode keluar 0]\nVerified','queued'),(True,'[kode keluar 1]\nFailed','failed'),(True,'(dihentikan: lebih dari 30 detik)','failed'),(False,'Denied','paused')])
def test_shared_approval_callback_keeps_checkpoint(allowed,result,state):
    project_jobs.init();pid=db.run('INSERT INTO project_jobs(brief,status,cursor,approval_id) VALUES(?,?,?,?)',('callback','waiting',2,999999))
    try:
        project_jobs.approval_completed(999999,allowed,{'text':result})
        row=db.one('SELECT status,cursor,approval_id FROM project_jobs WHERE id=?',(pid,))
        assert row=={'status':state,'cursor':2,'approval_id':0}
    finally:
        db.run('DELETE FROM project_jobs WHERE id=?',(pid,));db.run('DELETE FROM project_events WHERE project_id=?',(pid,))


def test_old_allowed_approval_recovers_without_advancing():
    project_jobs.init();aid=db.run('INSERT INTO approvals(status) VALUES(?)',('diizinkan',));pid=db.run('INSERT INTO project_jobs(brief,status,cursor,approval_id) VALUES(?,?,?,?)',('legacy','waiting',3,aid))
    try:
        project_jobs.recover_consumed_approvals()
        assert db.one('SELECT status,cursor,approval_id FROM project_jobs WHERE id=?',(pid,))=={'status':'queued','cursor':3,'approval_id':0}
    finally:
        db.run('DELETE FROM project_jobs WHERE id=?',(pid,));db.run('DELETE FROM project_events WHERE project_id=?',(pid,));db.run('DELETE FROM approvals WHERE id=?',(aid,))


def test_milestone_retry_keeps_first_snapshot_and_still_requires_tests(tmp_path):
    project_jobs.init();pid=999987
    try:
        before=project_jobs.stage_baseline(pid,0,tmp_path)
        (tmp_path/'app.py').write_text('print("actual source")')
        (tmp_path/'test.sqlite').write_text('runtime data')
        retry=project_jobs.stage_baseline(pid,0,tmp_path)
        assert retry==before=={} and 'test.sqlite' not in project_jobs.snapshot(tmp_path)
        stage={'task':'Buat backend','acceptance':'Jalankan test HTTP'}
        problems,changed=project_jobs.acceptance_problems(stage,{'meta':{}},retry,project_jobs.snapshot(tmp_path))
        assert changed==['app.py'] and len(problems)==1 and 'exit code 0' in problems[0]
    finally:db.run('DELETE FROM project_stage_snapshots WHERE project_id=?',(pid,))


def test_approval_receipt_reused_only_until_source_changes(tmp_path,monkeypatch):
    project_jobs.init();pid=999986
    monkeypatch.setattr(tools,'_workpath',lambda p:tmp_path)
    db.run('INSERT INTO project_jobs(id,brief,folder,status,cursor,approval_id) VALUES(?,?,?,?,?,?)',(pid,'proof','fixture','waiting',0,888886))
    (tmp_path/'app.py').write_text('real_source=1')
    receipt={'text':'[kode keluar 0]\nPASS HTTP','meta':{'tools':['run_project_command'],'trace':[{'alat':'run_project_command','arg':'python tests/test_http.py','hasil':'[kode keluar 0]\nPASS HTTP'}]}}
    try:
        project_jobs.approval_completed(888886,True,receipt)
        assert project_jobs.receipt_for_stage(pid,0,tmp_path)==receipt
        stage={'task':'Buat backend','acceptance':'test HTTP'}
        assert not project_jobs.acceptance_problems(stage,receipt,{},project_jobs.snapshot(tmp_path))[0]
        (tmp_path/'app.py').write_text('changed_source=2')
        assert project_jobs.receipt_for_stage(pid,0,tmp_path) is None
        assert project_jobs.receipt_for_stage(pid,1,tmp_path) is None
    finally:
        for table in ('project_jobs','project_events','project_stage_receipts'):db.run('DELETE FROM '+table+' WHERE '+('id' if table=='project_jobs' else 'project_id')+'=?',(pid,))

@pytest.mark.parametrize('command,verified',[('pip install pytest',False),('python -m pip install pytest',False),('echo test complete',False),('pip install pytest && python -m pytest tests/test_auth.py',True),('npm ci && npm run build',True)])
def test_installing_runner_is_not_proof_of_api_tests(command,verified):
    milestone={'task':'Implementasi API otentikasi seller','acceptance':'Cookie HttpOnly dan isolasi data'}
    response={'meta':{'trace':[{'alat':'run_project_command','arg':json.dumps({'command':command}),'hasil':'[kode keluar 0]'}]}}
    problems,_=project_jobs.acceptance_problems(milestone,response,{}, {'auth.py':'source'})
    assert bool(problems) is (not verified)

@pytest.mark.asyncio
async def test_file_editor_supplies_actual_sql_contract(monkeypatch,tmp_path):
    backend=tmp_path/'backend/app';backend.mkdir(parents=True)
    (backend/'db.py').write_text('SCHEMA="CREATE TABLE sellers(email TEXT,password_hash TEXT)"')
    (backend/'auth.py').write_text('def old(): pass')
    monkeypatch.setattr(config,'WORK_DIR',tmp_path.parent)
    seen=[]
    async def chat(messages,**kw):seen.append(json.loads(messages[-1]['content']));return {'content':'def fixed(): return True'}
    monkeypatch.setattr(llm,'chat',chat)
    ctx=context('teknisi')
    result=await tools.edit_project_file(ctx,folder=tmp_path.name,path='backend/app/auth.py',instructions='Fix authentication')
    assert 'dibaca ulang' in result
    assert 'password_hash' in seen[0]['project']['related_source']['backend/app/db.py']

@pytest.mark.asyncio
async def test_javascript_editor_reads_actual_html_control_contract(monkeypatch,tmp_path):
    (tmp_path/'index.html').write_text('<button id="downloadLink">Download</button>')
    (tmp_path/'app.js').write_text('const old = 1;')
    monkeypatch.setattr(config,'WORK_DIR',tmp_path.parent)
    seen=[]
    async def chat(messages,**kw):
        seen.append(json.loads(messages[-1]['content']));return {'content':'const fixed = 2;'}
    monkeypatch.setattr(llm,'chat',chat)
    ctx=context('teknisi');ctx.user_text='Download must use the converted blob with MIME image/png, not the original file.'
    await tools.edit_project_file(ctx,folder=tmp_path.name,path='app.js',instructions='Fix actual button handler')
    assert '<button id="downloadLink">' in seen[0]['project']['related_source']['index.html']
    assert 'converted blob with MIME image/png' in seen[0]['owner_request']

@pytest.mark.asyncio
async def test_python_semantic_syntax_error_cannot_replace_existing_file(monkeypatch,tmp_path):
    (tmp_path/'safe.py').write_text('def original(): return 42')
    monkeypatch.setattr(config,'WORK_DIR',tmp_path.parent)
    async def chat(*a,**kw):return {'content':'def invalid():\n    await something()'}
    monkeypatch.setattr(llm,'chat',chat)
    with pytest.raises(SyntaxError):await tools.edit_project_file(context('teknisi'),folder=tmp_path.name,path='safe.py',instructions='Change function')
    assert (tmp_path/'safe.py').read_text()=='def original(): return 42'


@pytest.mark.asyncio
async def test_router_retries_other_models_and_preserves_other_providers(monkeypatch):
    async def discover(*a,**kw):
        return [{'backend':'router','model':m,'ready':True} for m in ('ag/claude-opus','ag/claude-sonnet','ag/gpt','opencode/free-one','opencode/free-two')]
    monkeypatch.setattr(auto_router,'discover',discover)
    monkeypatch.setattr(auto_router,'_cooldown',{})
    routes=await auto_router.candidates([{'role':'user','content':'Implement coding project'}])
    assert len(routes)==4
    assert {r['model'].split('/')[0] for r in routes}=={'ag','opencode'}
    auto_router.failed(routes[0])
    remaining=await auto_router.candidates([{'role':'user','content':'Implement coding project'}])
    assert routes[0]['model'] not in {r['model'] for r in remaining}
    assert any(r['model'].startswith('ag/') for r in remaining)


@pytest.mark.asyncio
async def test_truncated_source_preserves_original_even_when_syntax_valid(monkeypatch,tmp_path):
    (tmp_path/'safe.py').write_text('def original(): return 42')
    monkeypatch.setattr(config,'WORK_DIR',tmp_path.parent)
    async def chat(*a,**kw):return {'content':'def partial(): return 0','stats':{'finish_reason':'length'}}
    monkeypatch.setattr(llm,'chat',chat)
    result=await tools.edit_project_file(context('teknisi'),folder=tmp_path.name,path='safe.py',instructions='Change function')
    assert result.startswith('Error:')
    assert (tmp_path/'safe.py').read_text()=='def original(): return 42'


def test_tool_aliases_respect_actual_schema_and_do_not_resolve_ambiguity():
    schema=[tools.REGISTRY['write_file'].schema()]
    parsed,_=llm.extract_tool_calls('{"name":"default.write_file","arguments":{"file_path":"safe.txt","content":"actual"}}',{'write_file'})
    assert parsed and parsed[0]['name']=='write_file'
    calls=llm.normalize_tool_calls([{'name':'default.write_file','arguments':{'file_path':'safe.txt','content':'actual'}}],schema)
    assert calls==[{'name':'write_file','arguments':{'path':'safe.txt','content':'actual'}}]
    ambiguous=llm.normalize_tool_calls([{'name':'write_file','arguments':{'file_path':'a','filename':'b','content':'actual'}}],schema)
    assert 'path' not in ambiguous[0]['arguments']
    forbidden=llm.normalize_tool_calls([{'name':'default.run_shell','arguments':{'command':'do not execute'}}],schema)
    assert forbidden[0]['name']=='default.run_shell'
