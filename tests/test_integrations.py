import importlib.util,json,os
from pathlib import Path
import pytest
from app import router,db,llm,integrations,config,native_apps

def host_module():
    spec=importlib.util.spec_from_file_location('host_integrations',Path(__file__).parents[1]/'host-integrations.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

@pytest.mark.asyncio
@pytest.mark.parametrize('go',[False,True])
async def test_connected_antigravity_alias_and_go_catalog(monkeypatch,go):
    async def request(method,path,body=None):
        if path=='/api/providers':return {'connections':[{'provider':'antigravity','isActive':True,'accessToken':'secret'}]}
        if path=='/api/models':return {'models':[{'id':'ag/gemini-3-flash','owned_by':'antigravity'}]} if go else {'models':[{'provider':'ag','routedModel':'ag/gemini-3-flash','name':'Flash'},{'provider':'ag','routedModel':'ag/image-test'},{'provider':'openai','routedModel':'openai/gpt'}]}
        if path=='/api/combos':return [] if go else {'combos':[]}
        return {'key':'private-key'}
    monkeypatch.setattr(router,'request',request)
    result=await router.state();assert [m['id'] for m in result['models']]==['ag/gemini-3-flash']
    assert 'private-key' not in json.dumps(result) and 'accessToken' not in json.dumps(result)

def test_host_fresh_install_no_fake_login(tmp_path,monkeypatch):
    module=host_module()
    for k in ('GH_TOKEN','GITHUB_TOKEN','CLOUDFLARE_API_TOKEN','CF_API_TOKEN'):monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(module.shutil,'which',lambda name:None)
    module.discover(tmp_path/'home',tmp_path/'data',True)
    result=json.loads((tmp_path/'data/integrations/status.json').read_text())
    assert not any(c['ready'] for c in result['connections'])
    assert json.loads((tmp_path/'data/integrations/secrets.json').read_text())=={}
    assert (tmp_path/'data/integrations/secrets.json').stat().st_mode&0o777==0o600
    assert (tmp_path/'data/integrations').stat().st_mode&0o777==0o700

def test_host_github_login_verified_and_secret_excluded(tmp_path,monkeypatch):
    module=host_module()
    for k in ('GH_TOKEN','GITHUB_TOKEN','CLOUDFLARE_API_TOKEN','CF_API_TOKEN'):monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(module.shutil,'which',lambda name:None)
    monkeypatch.setattr(module,'check',lambda url,token:(200,{'login':'owner'}) if token=='test-secret' else (401,{}))
    home=tmp_path/'home';(home/'.config/gh').mkdir(parents=True)
    (home/'.config/gh/hosts.yml').write_text('github.com:\n    oauth_token: test-secret\n    user: owner\n')
    module.discover(home,tmp_path/'data',True)
    text=(tmp_path/'data/integrations/status.json').read_text();assert 'test-secret' not in text
    assert json.loads(text)['connections'][0]['ready']
    assert json.loads((tmp_path/'data/integrations/secrets.json').read_text())['github']=='test-secret'

@pytest.mark.asyncio
@pytest.mark.parametrize('service,path',[('github','//evil.example'),('github','/repos/a/b/actions/secrets'),('cloudflare','/accounts/abc/workers/scripts')])
async def test_integration_api_scope_rejects_writes_or_arbitrary_hosts(service,path):
    with pytest.raises(ValueError):await integrations.read(service,path)

@pytest.mark.asyncio
async def test_router_rejects_cross_provider_strategy_before_network():
    token=llm.backend_context.set('router')
    try:
        with pytest.raises(llm.LLMError,match='Pilih model 9router'):await llm._chat_online([],None,.2,None,local=True,model_override='auto:smart')
    finally:llm.backend_context.reset(token)

def test_dashboard_font_and_svelte_assets_rewritten():
    assert '/apps/router/fonts/font.woff2' in native_apps.rewrite('a{src:url("/fonts/font.woff2")}', 'router','text/css')
    assert '/apps/router/_app/file.js' in native_apps.rewrite('"/_app/file.js"','router','application/javascript')

@pytest.mark.asyncio
async def test_orchestrator_partial_summary_preserves_real_attachment(monkeypatch):
    from app import workflow,office,tools
    bot=db.bot('orchestrator');ctx=tools.Ctx(bot,db.chat_for('orchestrator','test','summary036'),'test','summary036')
    async def execute(context,target,task,on_event):
        if target=='teknisi':
            await tools.write_file(context,'summary036.txt','1000')
            return {'text':'Hasil 125*8 adalah 1000.','meta':{'files':['summary036.txt'],'tools':['write_file']}}
        return {'text':'Berkas dibaca, isinya 1000.','meta':{'tools':['read_file']}}
    async def chat(*args,**kwargs):return {'content':'Hasil perhitungan 125 x','stats':{}}
    async def event(*args):pass
    monkeypatch.setattr(office,'execute',execute);monkeypatch.setattr(llm,'chat',chat)
    result=await workflow.run(ctx,'Simpan hasil hitung ke berkas.',event)
    assert result['meta']['summary_fallback'] and '1000' in result['text'] and 'summary036.txt' in result['text']

@pytest.mark.asyncio
async def test_orchestrator_removed_delegation_permission_respected(monkeypatch):
    from app import agent,workflow
    async def denied(*args):raise AssertionError('Delegation must not run without its permission')
    async def chat(*args,**kwargs):return {'content':'Halo, saya siap.','tool_calls':[],'stats':{}}
    monkeypatch.setattr(workflow,'run',denied);monkeypatch.setattr(llm,'chat',chat)
    bot={**db.bot('orchestrator'),'tools':['read_file']}
    result=await agent.Turn(bot,'test','restricted036').run('Halo')
    assert result['text']=='Halo, saya siap.'

@pytest.mark.parametrize('docker,expected',[(True,'http://router:20128'),(False,'http://127.0.0.1:20128')])
def test_router_address_detects_docker_or_native_host(monkeypatch,docker,expected):
    monkeypatch.delenv('ROUTER_BASE',raising=False)
    monkeypatch.setattr(router.Path,'exists',lambda self:docker)
    assert router.base()==expected
    monkeypatch.setenv('ROUTER_BASE','http://custom:9999/')
    assert router.base()=='http://custom:9999'
