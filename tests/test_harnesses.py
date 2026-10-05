import asyncio,json,os,sys
from pathlib import Path
import pytest
from app import config,db,harnesses,agent,main

@pytest.fixture
def isolated(monkeypatch,tmp_path):
    prior=db._conn;monkeypatch.setattr(db,'_conn',None)
    for key,path in {'DATA_DIR':tmp_path,'DB_PATH':tmp_path/'db/agen.sqlite','WORK_DIR':tmp_path/'work','BACKUP_DIR':tmp_path/'backup','CERT_DIR':tmp_path/'cert'}.items():monkeypatch.setattr(config,key,path)
    monkeypatch.setenv('AGEN_HARNESS_DIR',str(tmp_path/'runtimes'))
    original=main.Path.is_file
    monkeypatch.setattr(main.Path,'is_file',lambda self:False if self.name=='host-integrations.py' else original(self))
    main.bootstrap()
    yield tmp_path
    db._conn.close();db._conn=prior


def test_catalog_is_lazy_and_rejects_custom_install_source(isolated):
    data=harnesses.catalogue()
    assert len(data['items'])>=10 and not harnesses.root().exists()
    with pytest.raises(ValueError):harnesses.select('../../elsewhere',True)
    assert not harnesses.root().exists()


def test_none_has_no_default_prompt_or_automatic_memory(isolated,monkeypatch):
    harnesses.select('none');db.set_setting('custom_harness','stored instructions');bot=db.bot('orchestrator');chat=db.chat_for(bot['id'],'web','1')
    monkeypatch.setattr(agent,'context_block',lambda *_:pytest.fail('none must not inject context'))
    msgs,skills=agent.build_messages(bot,chat,'hello')
    assert not any(m['role']=='system' for m in msgs) and skills==[]
    assert agent.default_system_prompt(bot)==''


def test_credentials_are_isolated_masked_and_allowlisted(isolated,monkeypatch):
    monkeypatch.setenv('GH_TOKEN','office-secret');monkeypatch.setenv('ANTHROPIC_API_KEY','host-secret')
    harnesses.configure('claude',{'model':'claude-test','env':{'ANTHROPIC_API_KEY':'owner-secret'}})
    base=harnesses.owned(harnesses.location('claude'))
    env=harnesses.environment(base,'claude')
    assert 'GH_TOKEN' not in env and 'ANTHROPIC_API_KEY' not in env
    assert harnesses.environment(base,'claude',True)['ANTHROPIC_API_KEY']=='owner-secret'
    assert harnesses.status('claude')['env']['ANTHROPIC_API_KEY']=='••••'
    assert 'owner-secret' not in harnesses.redact('error owner-secret','claude')
    for bad in ({'PATH':'bad'},{'HOME':'bad'},{'OPENAI_API_KEY':'bad'}):
        with pytest.raises(ValueError):harnesses.configure('claude',{'env':bad})


def test_json_failures_cannot_be_successful_answers():
    with pytest.raises(ValueError):harnesses.answer('claude',json.dumps({'is_error':True,'result':'no key'}))
    with pytest.raises(ValueError):harnesses.answer('pi',json.dumps({'message':{'role':'assistant','stopReason':'error','errorMessage':'quota'}}))
    assert harnesses.answer('opencode',json.dumps({'type':'text','part':{'text':'actual'}}))=='actual'
    assert harnesses.answer('pi',json.dumps({'message':{'role':'assistant','content':[{'type':'text','text':'actual'}]}}))=='actual'


@pytest.mark.asyncio
async def test_original_runtime_never_falls_back_to_llm(isolated,monkeypatch):
    harnesses.select('claude');bot=db.bot('orchestrator')
    async def forbidden(*a,**kw):pytest.fail('must not silently substitute native agent')
    monkeypatch.setattr(agent.llm,'chat',forbidden)
    result=await agent.Turn(bot,'web','1').run('hello')
    assert result['meta']['status']=='failed' and 'belum terpasang' in result['text']
    assert harnesses.root().exists() is False


@pytest.mark.asyncio
async def test_runtime_requires_explicit_permission_and_does_not_expand_delegation(isolated,monkeypatch):
    harnesses.select('pi')
    monkeypatch.setattr(harnesses,'status',lambda _: {'phase':'installed'})
    with pytest.raises(ValueError,match='akses penuh'):await harnesses.run('pi','hi',lambda *a:None)
    result=await agent.Turn(db.bot('orchestrator'),'office','1').run('help')
    assert result['meta']['status']=='failed' and 'Delegasi' in result['text']


@pytest.mark.asyncio
async def test_only_selected_runtime_is_queued_and_can_be_cancelled(isolated,monkeypatch):
    called=[]
    async def fake_install(hid):called.append(hid);await asyncio.sleep(20)
    monkeypatch.setattr(harnesses,'install',fake_install)
    harnesses.select('pi',True);await asyncio.sleep(0)
    assert called==['pi']
    harnesses.select('pi',True);assert called==['pi']
    harnesses.cancel('pi');await asyncio.gather(harnesses._tasks['pi'],return_exceptions=True)
    assert harnesses.status('pi')['phase']=='interrupted'


def test_invalid_manifest_cannot_escape_runtime_cache(isolated):
    base=harnesses.owned(harnesses.location('pi'))
    (base/'ready.json').write_text(json.dumps({'slot':'../../source'}))
    with pytest.raises(ValueError):harnesses.runtime_path('pi')


@pytest.mark.asyncio
async def test_subprocess_timeout_terminates_group(tmp_path,monkeypatch):
    if os.name!='nt' and os.geteuid()==0:
        monkeypatch.setattr(config,'KERJA_UID',0);monkeypatch.setattr(config,'KERJA_GID',0)
    with pytest.raises(TimeoutError):await harnesses.process([sys.executable,'-c','import time;time.sleep(10)'],tmp_path,{'PATH':os.environ.get('PATH',''),'SYSTEMROOT':os.environ.get('SYSTEMROOT','')},timeout=.2)


def test_corrupt_manifest_is_failed_not_a_dashboard_exception(isolated):
    base=harnesses.owned(harnesses.location('pi'));(base/'ready.json').write_text('{broken')
    assert harnesses.status('pi')['phase']=='failed'
    assert len(harnesses.catalogue()['items'])>=10


def test_runtime_model_is_scoped_to_conversation_and_engine(isolated):
    harnesses.configure('pi',{'model':'base-model','env':{}})
    a=db.chat_for('orchestrator','web','one');b=db.chat_for('orchestrator','tg','two')
    harnesses.select_chat_model('pi',a,'openai/custom')
    assert harnesses.chat_model('pi',a)=='openai/custom' and harnesses.chat_model('pi',b)=='base-model'
    assert harnesses.chat_model('claude',a)==''
    with pytest.raises(ValueError):harnesses.select_chat_model('pi',a,'model; shell')


@pytest.mark.asyncio
async def test_native_telegram_model_command_stores_actual_preference(isolated,monkeypatch):
    from app.telegram import TgBot
    harnesses.select('pi');tg=TgBot('ci-token');sent=[]
    async def send(chat,text,*args,**kwargs):sent.append(text)
    monkeypatch.setattr(tg,'send',send)
    assert await tg.command('123','/model openai/test-model') is True
    bot=tg.bot_for_chat('123');chat=db.chat_for(bot['id'],'tg','123')
    assert harnesses.chat_model('pi',chat)=='openai/test-model'
    assert await tg.command('123','/model') is True
    assert 'openai/test-model' in sent[-1] and 'Pi' in sent[-1]
