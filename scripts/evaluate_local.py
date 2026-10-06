"""Opt-in real CPU model evaluation. Never reads the user's application data.

python scripts/evaluate_local.py --server-exe /path/llama-server --gguf /path/model.gguf --model local-test
Requires the ordinary Agen Mini Python dependencies and an existing llama.cpp binary.
No provider accounts, downloads, fine-tuning or network Telegram messages are used.
"""
import argparse,asyncio,json,os,secrets,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-exe',type=Path,required=True)
    parser.add_argument('--gguf',type=Path,required=True)
    parser.add_argument('--model',default='local-test')
    parser.add_argument('--case',choices=['all','python','note','html'],default='all')
    args=parser.parse_args()
    exe=args.server_exe.resolve();gguf=args.gguf.resolve()
    if not exe.is_file() or not gguf.is_file():parser.error('Binary/model file not found')
    run=Path(tempfile.mkdtemp(prefix='agenmini-real-eval-'))
    os.environ.update(DATA_DIR=str(run/'data'),WEB_PASSWORD=secrets.token_urlsafe(24))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    os.environ['LOCAL_API_BASE']=f'http://127.0.0.1:{port}/v1'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    log=(run/'llama.log').open('w')
    process=subprocess.Popen([str(exe),'-m',str(gguf),'--host','127.0.0.1','--port',str(port),'--alias',args.model,
                              '-c','8192','-t','4','-ngl','0','--parallel','1','--jinja','--reasoning','off'],
                             stdout=log,stderr=log,**({'creationflags':0x08000000} if os.name=='nt' else {}))
    async def evaluate():
        from app import main,db,agent,llm,config
        main.bootstrap(profile='blank')
        for key,value in {'harness_mode':'assisted','full_access':'1','llm_backend':'local','local_model_id':args.model,
                          'tool_mode':'text','self_improve':'off','max_steps':'5'}.items():db.set_setting(key,value)
        config.WORK_DIR.mkdir(parents=True,exist_ok=True)
        bot=db.bot('orchestrator');bot.update(backend='local',model=args.model)
        nonce=secrets.token_hex(4)
        cases=[('note','web',f'Buat file catatan_{nonce}.txt berisi persis "uji asli {nonce}". Baca ulang dengan alat untuk memastikan isi yang sama.'),
               ('python','tg',f'Buat berkas total_{nonce}.py berisi fungsi total_prima(n) yang menjumlahkan nilai bilangan prima sampai n inklusif. Uji n=1 hasil 0, n=10 hasil 17, n=20 hasil 77. Jalankan tes dan lampirkan berkas.'),
               ('html','web',f'Buat landing page HTML untuk Toko Awan {nonce}. Warna hijau, 3 paket Langit, Hujan, Pelangi dengan harga 19000, 39000, 79000. Ada tombol tambah/kurang jumlah pembelian yang memperbarui total harga. Tanpa library atau CDN.')]
        rows=[]
        async def event(kind,value):
            if kind=='status':print(value,flush=True)
        try:
            for name,channel,prompt in cases:
                if args.case not in ('all',name):continue
                started=time.monotonic()
                try:result=await asyncio.wait_for(agent.Turn(bot,channel,'real-'+name,event).run(prompt),420)
                except Exception as exc:result={'error':str(exc),'meta':{'status':'failed'}}
                checks={}
                if name=='note':
                    target=config.WORK_DIR/f'catatan_{nonce}.txt'
                    checks['exact_content']=target.is_file() and target.read_text(encoding='utf-8')==f'uji asli {nonce}'
                if name=='python':
                    # Assertions below are authored by the evaluator, not the model.
                    import ast
                    target=config.WORK_DIR/f'total_{nonce}.py'
                    checks['source_created']=target.is_file()
                    if target.is_file():
                        source=target.read_text(encoding='utf-8');tree=ast.parse(source)
                        checks['function_present']=any(isinstance(n,ast.FunctionDef) and n.name=='total_prima' for n in tree.body)
                        checks['assertions_present']=any(isinstance(n,ast.Assert) for n in ast.walk(tree))
                        checks['actual_tests_passed']=result.get('meta',{}).get('status')=='done'
                        from app import tools
                        ctx=tools.Ctx(bot,db.chat_for(bot['id'],channel,'real-'+name),channel,'real-'+name)
                        check=await tools.run_python(ctx,code='import runpy\nns=runpy.run_path('+repr(target.name)+')\nf=ns["total_prima"]\nfor n, expected in [(1,0),(2,2),(3,5),(10,17),(20,77),(50,328)]:\n    assert f(n)==expected,(n,f(n),expected)\nprint("six independent cases passed")')
                        checks['independent_tests_passed']=check.startswith('[kode keluar 0]')
                        checks['independent_test_output']=check
                if name=='html':checks['browser_behavior']='pending manual browser clicks; syntax is insufficient'
                rows.append({'case':name,'channel':channel,'prompt':prompt,'seconds':round(time.monotonic()-started,2),'checks':checks,'result':result})
                report={'model':args.model,'gguf_bytes':gguf.stat().st_size,'nonce':nonce,'rows':rows,
                        'work_dir':str(config.WORK_DIR),'limitations':'No Telegram network delivery or model weight training. HTML behavior requires browser testing.'}
                (run/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print(name,checks,result.get('meta',{}).get('status','unknown'),flush=True)
        finally:await llm.session().close()
        print('Report:',run/'results.json',flush=True)
    try:
        for _ in range(300):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=2) as response:
                    if response.status==200:break
            except OSError:time.sleep(.2)
            if process.poll() is not None:raise RuntimeError('llama-server exited; inspect '+str(run/'llama.log'))
        else:raise RuntimeError('Model initialization timed out')
        asyncio.run(evaluate())
    finally:process.terminate();process.wait(timeout=15);log.close()

if __name__=='__main__':main()
