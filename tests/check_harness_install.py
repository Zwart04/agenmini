"""Real upstream CLI installation smoke. No provider accounts or live model required."""
import asyncio,json,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
async def check(hid):
    with tempfile.TemporaryDirectory(prefix='agenmini-runtime-check-') as tmp:
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
            code,out,err=await harnesses.process(harnesses.cli(hid)+args,cwd,env,90)
            assert code==0,(out+err)[-3000:]
            expected={'pi':['--print','--mode','--model'],'omp':['--print','--mode','--model'],'opencode':['--format','--model'],'hermes':['--query','--model'],'claude':['--output-format','--bare'],'dsh':['--json'],'aider':['--message','--model'],'mini':['--exit-immediately','--model'],'gemini':['--output-format','--model']}
            plain=out+err
            for flag in expected[hid]:assert flag in plain,(flag,plain[-4000:])
            print('PASS original CLI installation / headless flags / only selected runtime: '+hid)
        finally:
            db._conn.close();db._conn=None
if __name__=='__main__':asyncio.run(check(sys.argv[1]))
