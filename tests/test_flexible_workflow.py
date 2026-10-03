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
