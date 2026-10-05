"""Real upstream CLI installation smoke. No provider accounts or live model required."""
import asyncio,json,os,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class RuntimeTempDirectory(tempfile.TemporaryDirectory):
    def cleanup(self):
        # Windows may retain executable/scanner handles briefly after Job termination.
        # Retry only this freshly created test directory; never suppress a final failure.
        for attempt in range(16):
            try:return super().cleanup()
            except OSError:
                if os.name!='nt' or attempt==15:raise
                time.sleep(.25)

async def check(hid):
    with RuntimeTempDirectory(prefix='agenmini-runtime-check-') as tmp:
        os.environ.update(DATA_DIR=tmp,AGEN_HARNESS_DIR=str(Path(tmp)/'runtimes'),WEB_PASSWORD='ci-runtime-smoke-only',PYTHONIOENCODING='utf-8')
        if os.name!='nt':
            os.environ['KERJA_UID']=str(os.getuid());os.environ['KERJA_GID']=str(os.getgid())
        from app import main,harnesses,db
        original=main.Path.is_file
        main.Path.is_file=lambda self:False if self.name=='host-integrations.py' else original(self)
        main.bootstrap();main.Path.is_file=original
        try:
            assert not harnesses.root().exists()
            await harnesses.install(hid)
            state=harnesses.status(hid)
            print(json.dumps({'runtime':hid,'status':state},ensure_ascii=True))
            assert state['phase']=='installed',state
            assert sorted(x.name for x in harnesses.root().iterdir())==[hid]
            cwd=harnesses.owned(harnesses.location(hid)/'workspace')
            env=harnesses.environment(harnesses.location(hid),hid)
            args={'opencode':['run','--help'],'hermes':['chat','--help'],'dsh':['--profile','headless','--help']}.get(hid,['--help'])
            code,out,err=await harnesses.process(harnesses.cli(hid)+args,cwd,env,90,memory_mb=768 if hid=='omp' else 512)
            assert code==0,(out+err)[-3000:]
            expected={'pi':['--print','--mode','--model'],'omp':['--print','--mode','--model'],'opencode':['--format','--model'],'hermes':['--query','--model'],'claude':['--output-format','--bare'],'dsh':['--json'],'aider':['--message','--model'],'mini':['--exit-immediately','--model'],'gemini':['--output-format','--model']}
            plain=out+err
            for flag in expected[hid]:assert flag in plain,(flag,plain[-4000:])
            print('PASS original CLI installation / headless flags / only selected runtime: '+hid)
            if hid=='pi':await real_pi_protocol(harnesses,db,Path(tmp))
        finally:
            db._conn.close();db._conn=None
async def real_pi_protocol(harnesses,db,tmp):
    """Execute a real upstream tool loop against an explicitly simulated model endpoint."""
    from aiohttp import web
    requests=[]
    async def completion(request):
        body=await request.json();requests.append(body)
        response=web.StreamResponse(headers={'Content-Type':'text/event-stream'})
        await response.prepare(request)
        if len(requests)==1:
            assert any(t.get('function',{}).get('name')=='write' for t in body['tools'])
            delta={'role':'assistant','tool_calls':[{'index':0,'id':'call-proof','type':'function','function':{'name':'write','arguments':json.dumps({'path':'native-proof.txt','content':'real CLI tool executed'})}}]}
            finish='tool_calls'
        else:delta={'role':'assistant','content':'Berkas native-proof.txt telah dibuat.'};finish='stop'
        for d,f in ((delta,None),({},finish)):
            chunk={'id':'ci-fixture','object':'chat.completion.chunk','created':1,'model':'ci-model','choices':[{'index':0,'delta':d,'finish_reason':f}]}
            await response.write(('data: '+json.dumps(chunk)+'\n\n').encode())
        await response.write(b'data: [DONE]\n\n');await response.write_eof();return response
    app=web.Application();app.router.add_post('/v1/chat/completions',completion)
    runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    try:
        env=harnesses.environment(harnesses.location('pi'),'pi')
        models=Path(env['PI_CODING_AGENT_DIR'])/'models.json'
        models.write_text(json.dumps({'providers':{'ci-fixture':{'baseUrl':f'http://127.0.0.1:{port}/v1','api':'openai-completions','apiKey':'${OPENAI_API_KEY}','models':[{'id':'ci-model','name':'CI fixture','reasoning':False,'input':['text'],'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0},'contextWindow':8192,'maxTokens':1024}]}}}),encoding='utf-8')
        harnesses.configure('pi',{'model':'ci-model','provider':'ci-fixture','env':{'OPENAI_API_KEY':'ci-local-fixture-only'}})
        db.set_setting('full_access','1');events=[]
        async def event(kind,data):events.append((kind,data))
        result=await harnesses.run('pi','Create native-proof.txt with the requested content, then report the result.',event)
        assert len(requests)>=2 and 'native-proof.txt' in result['text'],result
        from app import config
        assert (config.WORK_DIR/'runtime-pi/native-proof.txt').read_text()=='real CLI tool executed'
        assert 'runtime-pi/native-proof.txt' in result['files'] and 'write' in result['tools'],result
        print('PASS real Pi CLI / simulated model / actual write tool / downloadable artifact / final JSON')
    finally:await runner.cleanup()

if __name__=='__main__':asyncio.run(check(sys.argv[1]))
