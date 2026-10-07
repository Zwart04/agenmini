"""Opt-in real small-model functional-app evaluation; private isolated data.
Generated code is never replaced by evaluator templates. Browser interactions
must be checked separately. This script records actual failures as failures.
"""
import argparse, asyncio, hashlib, json, os, secrets, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server-exe',type=Path,required=True);p.add_argument('--gguf',type=Path,required=True)
    p.add_argument('--case',choices=['converter','editor','video','all'],default='all')
    p.add_argument('--output-dir',type=Path,help='New private directory for retaining reviewable benchmark artifacts; must not exist.')
    p.add_argument('--prompt-file',type=Path,help='Optional benchmark brief for one case; {nonce} is replaced with the run marker.')
    p.add_argument('--model-id',default='local-eval');p.add_argument('--model-label')
    args=p.parse_args();exe=args.server_exe.resolve();model=args.gguf.resolve()
    if args.prompt_file and args.case=='all':p.error('--prompt-file requires one --case')
    if args.output_dir:
        run=args.output_dir.resolve();run.mkdir(parents=True,exist_ok=False)
    else:run=Path(tempfile.mkdtemp(prefix='agenmini-apps-eval-'))
    os.environ.update(DATA_DIR=str(run/'data'),WEB_PASSWORD=secrets.token_urlsafe(24))
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    os.environ['LOCAL_API_BASE']=f'http://127.0.0.1:{port}/v1'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    log=(run/'llama.log').open('w')
    process=subprocess.Popen([str(exe),'-m',str(model),'--host','127.0.0.1','--port',str(port),'--alias',args.model_id,
        '-c','8192','-t','4','-ngl','0','--parallel','1','--jinja','--reasoning','off'],stdout=log,stderr=log,
        **({'creationflags':0x08000000} if os.name=='nt' else {}))
    async def evaluate():
        from app import main,db,config,agent,llm
        original=main.Path.is_file
        main.Path.is_file=lambda self:False if self.name=='host-integrations.py' else original(self)
        main.bootstrap(profile='blank')
        for k,v in {'harness_mode':'assisted','full_access':'1','llm_backend':'local','local_model_id':args.model_id,'tool_mode':'text','self_improve':'off','max_steps':'10'}.items():db.set_setting(k,v)
        config.WORK_DIR.mkdir(parents=True,exist_ok=True)
        bot=db.bot('orchestrator');bot.update(backend='local',model=args.model_id)
        nonce=secrets.token_hex(4)
        cases=[('converter','web',f'Buat webapp Image Mini {nonce}, bukan landing page. Aplikasi offline untuk unggah PNG/JPEG, preview gambar, pilih output PNG/JPEG/WebP, tentukan lebar resize tanpa mengubah rasio, dan download hasil canvas yang benar. Validasi file bukan gambar, ukuran tidak valid, dan tampilkan pesan error. Gunakan index.html, style.css, app.js, README.md; tanpa CDN/library/API. Beri input ID imageFile, select ID outputFormat, input widthInput, tombol convertBtn dan link downloadLink. Jangan menampilkan hasil sukses bila gambar belum dimuat.'),
               ('editor','tg',f'Buat webapp Editor Mini {nonce}, bukan landing page. Aplikasi offline untuk buka file teks .txt/.md, editor textarea, live jumlah kata/karakter, cari dan ganti semua teks, simpan file hasil UTF-8 serta reset editor. Gunakan index.html, style.css, app.js, README.md tanpa library/CDN/API. ID fileInput, editor, findText, replaceText, replaceBtn, saveBtn, resetBtn, wordCount. Masukkan teks "apel apel jeruk", ganti semua apel menjadi mangga, hasilnya "mangga mangga jeruk". Periksa empty search tidak membuat loop dan teks Unicode tidak rusak.')]
        video_brief=(Path(__file__).parent/'benchmarks'/'video-editor.txt').read_text(encoding='utf-8').replace('{nonce}',nonce)
        cases.append(('video','web',video_brief))
        rows=[]
        async def event(kind,value):
            if kind in ('status','harness'):print(kind,str(value)[:170],flush=True)
            if kind=='code':
                drafts=run/'drafts';drafts.mkdir(exist_ok=True)
                (drafts/Path(value['path']).name).write_text(value['content'],encoding='utf-8')
        try:
            for name,channel,prompt in cases:
                if args.case not in ('all',name):continue
                if args.prompt_file:prompt=args.prompt_file.read_text(encoding='utf-8').replace('{nonce}',nonce)
                started=time.monotonic()
                try:result=await asyncio.wait_for(agent.Turn(bot,channel,'apps-'+nonce+'-'+name,event).run(prompt),920)
                except Exception as exc:result={'error':str(exc),'meta':{'status':'failed'}}
                row={'case':name,'channel':channel,'prompt':prompt,'seconds':round(time.monotonic()-started,2),'result':result,
                     'behavior_verified':False,'checks':'Independently test actual import, editing, playback, conversion/export/download and responsive layout in a browser.'}
                rows.append(row)
                report={'model':args.model_label or model.name,'gguf_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
                    'core':'deepseek-adapted','nonce':nonce,'work_dir':str(config.WORK_DIR),'rows':rows,
                    'limitations':'Real CPU inference. tg uses the shared agent path, not Telegram network. Syntax/ZIP checks do not establish behavior.'}
                (run/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print('CASE RESULT',name,json.dumps(result,ensure_ascii=False)[:1400],flush=True)
        finally:await llm.session().close()
        print('REPORT',run/'results.json',flush=True)
    try:
        for _ in range(300):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=2) as r:
                    if r.status==200:break
            except OSError:time.sleep(.2)
            if process.poll() is not None:raise RuntimeError('llama-server stopped; '+str(run/'llama.log'))
        else:raise RuntimeError('Model initialization timeout')
        asyncio.run(evaluate())
    finally:process.terminate();process.wait(timeout=15);log.close()

if __name__=='__main__':main()
