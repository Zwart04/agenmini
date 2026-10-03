import pytest
from app import coding,llm,projects,agent,db,workflow

@pytest.mark.asyncio
@pytest.mark.parametrize('backend',['local','router'])
async def test_website_preserves_original_model_design_without_mandatory_form(monkeypatch,backend):
    original='<!doctype html><html><head><title>Editorial Orbit</title><meta name="viewport" content="width=device-width"></head><body><main class="original-editorial">A distinct visual direction</main></body></html>'
    async def chat(*a,**kw):return {'content':original,'stats':{'served_model':'test-model'}}
    async def check(*a):return []
    monkeypatch.setattr(llm,'active_backend',lambda:backend);monkeypatch.setattr(llm,'chat',chat)
    monkeypatch.setattr(projects,'inspect_inline_js',check)
    html,_=await coding.generate('Buat website editorial tanpa form')
    assert html==original and 'original-editorial' in html

@pytest.mark.asyncio
async def test_failed_website_is_repaired_without_switching_to_template(monkeypatch):
    complete='<!doctype html><html><head><title>Custom Art</title><meta name="viewport" content="width=device-width"></head><body><svg id="custom-art"></svg></body></html>'
    calls=[]
    async def chat(*a,**kw):calls.append(a);return {'content':'<!doctype html><html>' if len(calls)==1 else complete}
    async def check(*a):return []
    monkeypatch.setattr(llm,'active_backend',lambda:'router');monkeypatch.setattr(llm,'chat',chat);monkeypatch.setattr(projects,'inspect_inline_js',check)
    async def forbidden(*a,**k):raise AssertionError('template fallback must not run')
    monkeypatch.setattr(coding,'generate_compact',forbidden)
    html,_=await coding.generate('Buat website seni')
    assert html==complete and len(calls)==2

@pytest.mark.asyncio
async def test_greeting_bypasses_specialist_and_reviewer(monkeypatch):
    async def forbidden(*a,**k):raise AssertionError('greeting must not delegate')
    async def chat(*a,**k):return {'content':'Hai! Saya Orchestrator Agen Mini. Apa yang ingin Anda kerjakan?','tool_calls':[],'stats':{}}
    monkeypatch.setattr(workflow,'run',forbidden);monkeypatch.setattr(llm,'chat',chat)
    async def learn(*a,**k):pass
    monkeypatch.setattr(agent.Turn,'_learn',learn)
    result=await agent.Turn(db.bot('orchestrator'),'web','hello-test').run('hai siapa kamu?')
    assert 'Orchestrator' in result['text'] and 'reviewer' not in result['text']
    assert result['meta']['tools']==[]


def test_project_chooses_a_bot_that_can_edit_and_compile():
    from app import project_jobs
    selected=project_jobs.capable_worker({'bot':'asisten','task':'Buat struktur direktori dan utilitas','acceptance':'Dapat dikompilasi tanpa error'},db.bot('orchestrator')['tools'])
    assert selected=='teknisi'
    assert 'run_project_command' in db.bot(selected)['tools']

def test_project_compile_acceptance_requires_real_exit_zero():
    from app import project_jobs
    milestone={'task':'Buat utilitas','acceptance':'Dapat dikompilasi tanpa error'}
    problems,_=project_jobs.acceptance_problems(milestone,{'meta':{'trace':[]}}, {}, {'file.ts':'new'})
    assert problems


def test_whatsapp_store_is_an_application_not_landing_page():
    brief='buatkan saya website toko online wa yang bisa dipakai banyak seller, upload produk dan autobalas pembeli'
    assert coding.functional_request(brief)
    assert not coding.website_request(brief)
    assert projects.project_request(brief)

def test_product_landing_page_is_not_confused_with_building_its_backend():
    brief='Buatkan landing page Seller Studio, aplikasi web konten AI untuk seller Indonesia'
    assert coding.website_request(brief) and not coding.functional_request(brief)


def test_install_is_not_test_evidence_and_failure_scopes_are_separate():
    from app import project_jobs
    trace=[{'alat':'run_project_command','arg':'{"command":"npm install","folder":"p"}','hasil':'[kode keluar 0]'}]
    problems,_=project_jobs.acceptance_problems({'task':'Buat unit test','acceptance':'test passes'}, {'meta':{'trace':trace}}, {}, {'test.js':'new'})
    assert problems
    assert agent.tool_failure_scope('run_project_command',{'folder':'p','command':'npm install'}) != agent.tool_failure_scope('run_project_command',{'folder':'p','command':'npm test'})
    assert agent.tool_failure_scope('run_project_command',{'folder':'p','command':'npx jest --runInBand'}) == agent.tool_failure_scope('run_project_command',{'folder':'p','command':'node tests/run.js'})

@pytest.mark.asyncio
async def test_project_pipeline_reports_failure_before_tail(monkeypatch,tmp_path):
    from app import tools,config
    monkeypatch.setattr(config,'WORK_DIR',tmp_path)
    folder=tmp_path/'p';folder.mkdir()
    ctx=tools.Ctx(db.bot('orchestrator'),{'id':1},'web','pipeline-test')
    result=await tools.run_project_command(ctx,'p','false | tail -5',10)
    assert result.startswith('[kode keluar 1]'),result


def test_stage_hints_ignore_reference_url_in_whole_brief(monkeypatch):
    from app import memory
    seen=[]
    monkeypatch.setattr(agent,'task_hints',lambda text,tools:seen.append(text) or [])
    monkeypatch.setattr(memory,'search_memories',lambda *a,**kw:[])
    monkeypatch.setattr(memory,'profile_memories',lambda *a:[])
    monkeypatch.setattr(memory,'search_skills',lambda *a:[])
    agent.context_block(db.bot('teknisi'),'Whole brief https://example.com plus compile',hint_text='Compile backend and run unit tests')
    assert seen==['Compile backend and run unit tests']


def test_project_messages_ignore_stale_approval_chat_but_preserve_history():
    bot=db.bot('teknisi');chat=db.chat_for(bot['id'],'web','isolated-project-history-test')
    old=db.add_message(chat['id'],'assistant','Saya perlu izin untuk stale command')
    try:
        messages,_=agent.build_messages(bot,chat,'Run current tests',hint_text='Run current tests',include_history=False)
        assert not any('stale command' in m['content'] for m in messages)
        assert db.one('SELECT id FROM messages WHERE id=?',(old,))
    finally:
        db.run('DELETE FROM messages WHERE chat_id=?',(chat['id'],));db.run('DELETE FROM chats WHERE id=?',(chat['id'],))


def test_server_timeout_recovery_requires_runtime_probe():
    assert agent.tool_failure_scope('run_project_command',{'folder':'p','command':'python -m app.main'})==agent.tool_failure_scope('run_project_command',{'folder':'p','command':'python tests/test_server.py'})
    assert agent.tool_failure_scope('run_project_command',{'folder':'p','command':'python tests/test_server.py'})!=agent.tool_failure_scope('run_project_command',{'folder':'p','command':'pip install aiohttp'})
