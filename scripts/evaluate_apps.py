"""Opt-in real small-model functional-app evaluation; private isolated data.
Generated code is never replaced by evaluator templates. Browser interactions
must be checked separately. This script records actual failures as failures.
"""
import argparse, asyncio, hashlib, json, os, secrets, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

def print_case_result(name, result):
    """Keep console summaries ASCII-safe; UTF-8 result files retain all text."""
    print('CASE RESULT',name,json.dumps(result,ensure_ascii=True)[:1400],flush=True)


def failed_source_candidates(previous, report, recipe_path, accepted):
    """Resume exact failed model text, never call it a validated implementation.

    Legacy attempts have no per-task hash. Require the exact recipe file hash
    from their report before deriving that metadata. Only complete original
    JS responses are eligible; patched/truncated text needs stronger origins.
    The normal generator checks every candidate again before using it.
    """
    from app import project_parts
    expected=report.get('generator_source_sha256',{}).get('app/project_recipes/video_editor.json')
    if expected != hashlib.sha256(recipe_path.read_bytes()).hexdigest():return {}
    recipe=json.loads(recipe_path.read_text(encoding='utf-8'));candidates={}
    for path in sorted((previous/'attempts').glob('*.json')):
        try:
            value=json.loads(path.read_text(encoding='utf-8'));index=value['index']
            if type(index) is not int or index<0 or index>=len(recipe['parts']) or index in accepted:continue
            item=recipe['parts'][index]
            if item.get('kind')!='js' or item['name']!=value.get('part') or value.get('response_kind')!='source':continue
            if value.get('repair_chain') or value.get('patch_error') or value.get('stats',{}).get('finish_reason')!='stop':continue
            source=value['source'];raw=value['raw_source'];fmt=value.get('source_format','raw')
            if not isinstance(source,str) or not source.strip() or len(source.encode())>65536:continue
            decoded=project_parts.decode_source(raw,item['file'],fmt)
            if project_parts.select_model_helper(decoded,item)!=source:continue
            item={**item,'generation_contract_revision':2}
            evidence={'task_sha256':hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                      'sha256':hashlib.sha256(source.encode()).hexdigest(),'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                      'model':value.get('stats',{}).get('served_model',''),'source_format':fmt,
                      'checkpoint_status':'failed source; requires full validation and model repair'}
            candidates[index]={'source':source,'raw_source':raw,'evidence':evidence}
        except (ValueError,KeyError,TypeError):continue
    return candidates

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server-exe',type=Path,required=True);p.add_argument('--gguf',type=Path,required=True)
    p.add_argument('--case',choices=['converter','editor','video','all'],default='all')
    p.add_argument('--output-dir',type=Path,help='New private directory for retaining reviewable benchmark artifacts; must not exist.')
    p.add_argument('--prompt-file',type=Path,help='Optional benchmark brief for one case; {nonce} is replaced with the run marker.')
    p.add_argument('--model-id',default='local-eval');p.add_argument('--model-label')
    p.add_argument('--thinking-budget',type=int,default=0,help='Opt-in bounded Qwen reasoning tokens per part (0 disables).')
    p.add_argument('--source-parts',action='store_true',help='Experimental model-written source chunks; not a production default.')
    p.add_argument('--resume-parts',type=Path,help='Previous private run: reuse only matching task/source hashes and the same GGUF.')
    p.add_argument('--resume-failed-parts',action='store_true',help='Also recheck exact complete failed JS responses from an identical recipe; never treat them as passed.')
    p.add_argument('--sampling-profile',choices=['default','qwen35-nonthinking','lfm25','greedy'],default='default')
    p.add_argument('--chat-template-file',type=Path,help='Explicit model-author chat serialization when GGUF metadata lacks it; not application source.')
    p.add_argument('--tokenizer-pre',choices=['deepseek-coder'],help='Explicit llama.cpp pre-tokenizer for legacy DeepSeek GGUF missing this metadata.')
    args=p.parse_args();exe=args.server_exe.resolve();model=args.gguf.resolve()
    if not 0<=args.thinking_budget<=512:p.error('--thinking-budget must be 0..512')
    if args.prompt_file and args.case=='all':p.error('--prompt-file requires one --case')
    if args.resume_failed_parts and not args.resume_parts:p.error('--resume-failed-parts requires --resume-parts')
    if args.output_dir:
        run=args.output_dir.resolve();run.mkdir(parents=True,exist_ok=False)
    else:run=Path(tempfile.mkdtemp(prefix='agenmini-apps-eval-'))
    # A local benchmark must not inherit live provider or Telegram credentials.
    # This only changes the evaluator process; the user's app/settings stay intact.
    for key in ('GH_TOKEN','GITHUB_TOKEN','ONLINE_API_KEY','COMPATIBLE_KEY','TELEGRAM_TOKEN','TELEGRAM_USER_IDS','OPENAI_API_KEY','ANTHROPIC_API_KEY','ROUTER_API_KEY','FREE_LLM_API_KEY'):
        os.environ.pop(key,None)
    os.environ.update(DATA_DIR=str(run/'data'),WEB_PASSWORD=secrets.token_urlsafe(24))
    repo_root=Path(__file__).resolve().parents[1]
    generator_sources={str(path.relative_to(repo_root)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in [repo_root/'scripts/evaluate_apps.py',repo_root/'app/llm.py',repo_root/'app/projects.py',repo_root/'app/project_parts.py',repo_root/'app/project_checks.py',repo_root/'app/project_dom_checks.py',repo_root/'app/project_canvas_checks.py',repo_root/'app/project_patches.py',repo_root/'app/project_recipes/video_editor.json',repo_root/'app/vendor/acorn.cjs',repo_root/'app/vendor/ACORN-PROVENANCE.json']}
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    os.environ['LOCAL_API_BASE']=f'http://127.0.0.1:{port}/v1'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    log=(run/'llama.log').open('w')
    reasoning_args=['--reasoning-format','deepseek','--reasoning-budget',str(args.thinking_budget)] if args.thinking_budget else []
    template_args=['--chat-template-file',str(args.chat_template_file.resolve())] if args.chat_template_file else []
    tokenizer_args=['--override-kv','tokenizer.ggml.pre=str:'+args.tokenizer_pre] if args.tokenizer_pre else []
    process=subprocess.Popen([str(exe),'-m',str(model),'--host','127.0.0.1','--port',str(port),'--alias',args.model_id,
        '-c','8192','-t','4','-ngl','0','--parallel','1','--jinja','--reasoning','on' if args.thinking_budget else 'off',
        *reasoning_args,*template_args,*tokenizer_args],stdout=log,stderr=log,
        **({'creationflags':0x08000000} if os.name=='nt' else {}))
    async def evaluate():
        from app import main,db,config,agent,llm,project_parts
        if args.sampling_profile!='default':llm.local_sampling.set(llm.sampling_profile(args.sampling_profile))
        if args.resume_parts:
            old=json.loads((args.resume_parts/'results.json').read_text(encoding='utf-8'))
            if old['gguf_sha256']!=hashlib.sha256(model.read_bytes()).hexdigest():raise ValueError('Resume requires the exact same model weights.')
            actual_template=hashlib.sha256(args.chat_template_file.read_bytes()).hexdigest() if args.chat_template_file else None
            if (old.get('chat_template_sha256'),old.get('tokenizer_pre'),old.get('sampling_profile','default'),old.get('thinking_budget',0)) != (actual_template,args.tokenizer_pre,args.sampling_profile,args.thinking_budget):
                raise ValueError('Resume requires matching chat serialization, pre-tokenizer and inference settings.')
            accepted={int(p.stem):json.loads(p.read_text(encoding='utf-8')) for p in (args.resume_parts/'parts').glob('*.json')}
            failed=failed_source_candidates(args.resume_parts,old,repo_root/'app/project_recipes/video_editor.json',accepted) if args.resume_failed_parts else {}
            project_parts.part_cache.set({**failed,**accepted})
            if failed:print('RECHECK FAILED MODEL CHECKPOINTS',sorted(failed),flush=True)
        llm.coding_reasoning.set(bool(args.thinking_budget))
        original=main.Path.is_file
        main.Path.is_file=lambda self:False if self.name=='host-integrations.py' else original(self)
        main.bootstrap(profile='blank')
        for k,v in {'harness_mode':'assisted','full_access':'1','llm_backend':'local','local_model_id':args.model_id,'tool_mode':'text','self_improve':'off','max_steps':'10'}.items():db.set_setting(k,v)
        db.set_setting('coding_parts_experimental','1' if args.source_parts else '0')
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
            if kind=='source_attempt':
                attemptdir=run/'attempts';attemptdir.mkdir(exist_ok=True)
                (attemptdir/(str(value['index']).zfill(2)+'-'+str(value['attempt'])+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            if kind=='source_part':
                partdir=run/'parts';partdir.mkdir(exist_ok=True)
                (partdir/(str(value['index']).zfill(2)+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            if kind=='source_check':
                checkdir=run/'checks';checkdir.mkdir(exist_ok=True)
                (checkdir/(str(value['index']).zfill(2)+'-'+str(value['attempt'])+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
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
                    'core':'deepseek-adapted','nonce':nonce,'work_dir':str(config.WORK_DIR),'rows':rows,'sampling_profile':args.sampling_profile,'thinking_budget':args.thinking_budget,'resume_failed_parts':args.resume_failed_parts,
                    'chat_template_sha256':hashlib.sha256(args.chat_template_file.read_bytes()).hexdigest() if args.chat_template_file else None,
                    'tokenizer_pre':args.tokenizer_pre,
                    'generator_source_sha256':generator_sources,
                    'limitations':'Real CPU inference. tg uses the shared agent path, not Telegram network. Syntax/ZIP checks do not establish behavior.'}
                (run/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print_case_result(name,result)
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
