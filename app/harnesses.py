"""Original CLI runtimes: explicit, lazy installation; never prompt emulation."""
import asyncio, json, os, re, shutil, signal, sys, time, uuid, venv
from pathlib import Path
from . import config, db

# Fixed distributions only. A request cannot choose a URL, executable or install arguments.
CATALOG = [
 dict(id='none', name='Kosong', description='Tanpa prompt, panduan tugas atau konteks otomatis Agen Mini.', version='builtin'),
 dict(id='assisted', name='Agen Mini', description='Alat, tim bot, skill dan ingatan dalam satu aplikasi ringan.', version='builtin'),
 dict(id='hermes', name='Hermes Agent', description='Runtime Nous asli dengan alat, skill dan pembelajaran Hermes.', kind='pip', package='https://codeload.github.com/nousresearch/hermes-agent/zip/7157422022ff06f3e632d1dd394ee1253b17ad37', version='7157422022ff', bin='hermes', source='https://github.com/nousresearch/hermes-agent', keys=['OPENROUTER_API_KEY','OPENAI_API_KEY','OPENAI_BASE_URL','ANTHROPIC_API_KEY'], provider='openrouter'),
 dict(id='opencode', name='OpenCode', description='Agen coding asli, banyak provider; model memakai provider/id.', kind='npm', package='opencode-ai', version='1.18.34', bin='opencode', source='https://github.com/anomalyco/opencode', keys=['ANTHROPIC_API_KEY','OPENAI_API_KEY','OPENROUTER_API_KEY']),
 dict(id='claude', name='Claude Code', description='CLI resmi Anthropic. Mode integrasi memakai API key Anthropic.', kind='npm', package='@anthropic-ai/claude-code', version='2.1.289', bin='claude', source='https://code.claude.com/docs/en/headless', keys=['ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL']),
 dict(id='dsh', name='DeepSeek Harness', description='Runtime plugin DeepSeek asli; preview, API key DeepSeek.', kind='npm', package='@deepseek-ai/dsh', version='0.2.0-rc.2', bin='dsh', source='https://github.com/deepseek-ai/deepseek-harness', keys=['DEEPSEEK_API_KEY']),
 dict(id='omp', name='oh-my-pi', description='Agen coding asli dengan edit dan alat; Bun dipasang hanya saat diperlukan.', kind='npm', package='@oh-my-pi/pi-coding-agent', version='18.6.1', bin='omp', source='https://github.com/can1357/oh-my-pi', keys=['ANTHROPIC_API_KEY','OPENAI_API_KEY','OPENROUTER_API_KEY']),
 dict(id='pi', name='Pi', description='CLI coding asli yang ringkas, banyak model dan provider.', kind='npm', package='@earendil-works/pi-coding-agent', version='1.0.3', bin='pi', source='https://github.com/earendil-works/pi', keys=['ANTHROPIC_API_KEY','OPENAI_API_KEY','OPENROUTER_API_KEY']),
 dict(id='aider', name='Aider', description='Pair programming asli berbasis berkas dan Git; dependensi Python terpisah.', kind='pip', package='aider-chat==0.86.2', version='0.86.2', bin='aider', source='https://github.com/Aider-AI/aider', keys=['OPENAI_API_KEY','OPENAI_API_BASE','ANTHROPIC_API_KEY','OPENROUTER_API_KEY']),
 dict(id='mini', name='mini-SWE-agent', description='Loop coding Bash asli yang kecil; paket model tetap memakai dependensi Python.', kind='pip', package='mini-swe-agent==2.4.6', version='2.4.6', bin='mini', source='https://github.com/SWE-agent/mini-swe-agent', keys=['OPENAI_API_KEY','OPENAI_API_BASE','ANTHROPIC_API_KEY','OPENROUTER_API_KEY']),
 dict(id='gemini', name='Gemini CLI', description='CLI resmi Google, model Gemini melalui API key.', kind='npm', package='@google/gemini-cli', version='0.62.0', bin='gemini', source='https://github.com/google-gemini/gemini-cli', keys=['GEMINI_API_KEY']),
]
_tasks = {}
_run_lock = asyncio.Lock()
_install_lock = asyncio.Lock()


def entry(hid):
    if hid == 'minimal': return CATALOG[0]  # accepted legacy setting, never re-seed data
    row = next((x for x in CATALOG if x['id'] == hid), None)
    if row is None: raise ValueError('Harness tidak ada dalam katalog.')
    return row


def external(hid=None):
    return bool(entry(hid or db.setting('harness_mode')).get('kind'))


def root():
    return Path(os.environ.get('AGEN_HARNESS_DIR', str(config.DATA_DIR / 'harness-runtime'))).resolve()


def location(hid):
    row = entry(hid)
    path=root() / row['id']
    if path.is_symlink() or not path.resolve().is_relative_to(root()):raise ValueError('Direktori runtime bukan cache yang aman.')
    return path


def owned(path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt' and os.geteuid() == 0:
        os.chown(path, config.KERJA_UID, config.KERJA_GID)
    return path


def settings(hid):
    return json.loads(db.setting('runtime_config_'+entry(hid)['id']) or '{}')


def redact(text, hid):
    for key,value in settings(hid).get('env',{}).items():
        if value and ('KEY' in key or 'TOKEN' in key): text=text.replace(value,'[dirahasiakan]')
    return re.sub(r'(?i)(authorization:|bearer )\s*[^\s]+', r'\1 [dirahasiakan]', text)


def write_state(hid, phase, message):
    value={'phase':phase,'message':redact(message,hid)[-3000:],'updated':time.time()}
    db.set_setting('runtime_status_'+hid,json.dumps(value)); return value


def status(hid):
    row=entry(hid)
    if not row.get('kind'):return {'phase':'builtin','message':'Tersedia tanpa pemasangan tambahan.'}
    state=json.loads(db.setting('runtime_status_'+hid) or '{}')
    marker=location(hid)/'ready.json'
    if marker.is_file():
        manifest=json.loads(marker.read_text(encoding='utf-8'))
        if manifest.get('version') == row['version'] and manifest.get('package') == row['package'] and runtime_path(hid).is_dir():
            state={'phase':'installed','message':'Runtime asli terpasang. Provider belum tentu terhubung.'}
    elif state.get('phase') in ('queued','installing') and not (_tasks.get(hid) and not _tasks[hid].done()):
        state={'phase':'interrupted','message':'Pemasangan terhenti. Pilih Pasang ulang untuk mencoba lagi.'}
    cfg=settings(hid)
    return {**({'phase':'absent','message':'Belum diunduh.'}),**state,'model':cfg.get('model',''),'provider':cfg.get('provider',row.get('provider','')),'env':{k:('••••' if 'KEY' in k else v) for k,v in cfg.get('env',{}).items()},'credential_saved':any(v for k,v in cfg.get('env',{}).items() if 'KEY' in k)}


def catalogue():
    return {'active':db.setting('harness_mode'), 'items':[{**{k:v for k,v in x.items() if k not in ('package','bin')},'runtime':status(x['id'])} for x in CATALOG], 'busy':_run_lock.locked(), 'notice':'Runtime eksternal memiliki alat, izin, skill dan ingatan sendiri. Tidak mewarisi akun host atau koneksi Agen Mini. API key tidak membuktikan koneksi berhasil.'}


def configure(hid, data):
    row=entry(hid)
    if not row.get('kind'):raise ValueError('Harness bawaan tidak memerlukan konfigurasi CLI.')
    old=settings(hid);env=dict(old.get('env',{}))
    incoming=data.get('env',{})
    if not isinstance(incoming,dict) or any(k not in row['keys'] for k in incoming):raise ValueError('Variabel runtime tidak diizinkan.')
    for key,value in incoming.items():
        if not isinstance(value,str) or len(value)>4000 or '\x00' in value or '\n' in value:raise ValueError('Nilai konfigurasi tidak valid.')
        if value!='••••':env[key]=value.strip()
    cfg={'env':env}
    for key in ('model','provider'):
        value=data.get(key,old.get(key,row.get(key,'')))
        if not isinstance(value,str) or len(value)>200 or not re.fullmatch(r'[A-Za-z0-9_./:@+\-]*',value):raise ValueError('ID model/provider tidak valid.')
        cfg[key]=value
    db.set_setting('runtime_config_'+hid,json.dumps(cfg));return status(hid)


def environment(base, hid, credentials=False, dependencies=None):
    home=owned(base/'home')
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP')}
    # Only executable search path is inherited, never host login/API environment.
    env['PATH']=os.environ.get('PATH','/usr/local/bin:/usr/bin:/bin')
    dependencies=dependencies or runtime_path(hid)
    node=dependencies/'node_modules/node/bin'
    bun=dependencies/'node_modules/bun/bin'
    env['PATH']=os.pathsep.join((str(node),str(bun),env['PATH']))
    env.update(HOME=str(home),USERPROFILE=str(home),XDG_CONFIG_HOME=str(owned(home/'config')),XDG_DATA_HOME=str(owned(home/'data')),XDG_CACHE_HOME=str(owned(home/'cache')),HERMES_HOME=str(owned(home/'hermes')),PI_CODING_AGENT_DIR=str(owned(home/'pi')),DSH_HOME=str(owned(home/'dsh')),GIT_CONFIG_GLOBAL=str(home/'gitconfig'),GIT_CONFIG_NOSYSTEM='1',GIT_TERMINAL_PROMPT='0',MSWEA_GLOBAL_CONFIG_DIR=str(owned(home/'mini')),MSWEA_SILENT_STARTUP='1',APPDATA=str(owned(home/'appdata')),LOCALAPPDATA=str(owned(home/'localappdata')),PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1',NODE_OPTIONS='--max-old-space-size=384',NO_COLOR='1',CI='1',npm_config_cache=str(owned(home/'npm-cache')),npm_config_userconfig=str(home/'npmrc'),PIP_CACHE_DIR=str(owned(home/'pip-cache')),DSH_TELEMETRY_MODE='OFF',DISABLE_TELEMETRY='1',OTEL_SDK_DISABLED='true')
    if credentials:env.update(settings(hid).get('env',{}))
    return env


async def process(argv, cwd, env, timeout=900, pulse=None, memory_mb=512):
    """No shell; bounded output/lifetime. All Unix third-party code runs unprivileged."""
    options={};job=None
    if os.name=='nt':options['creationflags']=0x08000000
    else:
        def child():
            os.setsid()
            import resource
            resource.setrlimit(resource.RLIMIT_NOFILE,(2048,2048))
            resource.setrlimit(resource.RLIMIT_CORE,(0,0))
            if os.geteuid()==0:
                os.setgroups([]);os.setgid(config.KERJA_GID);os.setuid(config.KERJA_UID)
        options['preexec_fn']=child
    proc=await asyncio.create_subprocess_exec(*map(str,argv),cwd=cwd,env=env,stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,**options)
    if os.name=='nt':
        from .windows_execution import Job
        try:job=Job(proc.pid,memory_mb)
        except Exception:proc.kill();await proc.wait();raise
    async def read(stream):
        result=bytearray()
        while chunk:=await stream.read(4096):
            result.extend(chunk)
            if len(result)>1024*1024:raise ValueError('Keluaran runtime melebihi 1 MB.')
        return bytes(result).decode('utf-8','replace')
    exhausted=[]
    async def notify():
        while proc.returncode is None:
            if os.name!='nt' and Path('/proc').exists():
                rss=0
                for path in Path('/proc').iterdir():
                    if not path.name.isdigit():continue
                    try:
                        stat=(path/'stat').read_text().rsplit(') ',1)[1].split()
                        if int(stat[2])==proc.pid:rss+=int(stat[21])*os.sysconf('SC_PAGE_SIZE')
                    except (OSError,ValueError,IndexError):pass
                if rss>memory_mb*1024*1024:
                    exhausted.append(True)
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    return
            if pulse:await pulse()
            await asyncio.sleep(5)
    ticker=asyncio.create_task(notify())
    readers=[asyncio.create_task(read(proc.stdout)),asyncio.create_task(read(proc.stderr))]
    try:
        async with asyncio.timeout(timeout):
            out,err=await asyncio.gather(*readers);await proc.wait()
            if exhausted:raise ValueError('Runtime dihentikan: pemakaian RAM proses melebihi '+str(memory_mb)+' MB.')
            return proc.returncode,out,err
    finally:
        ticker.cancel()
        if proc.returncode is None:
            if os.name=='nt':proc.kill()
            else:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        if job:job.close()
        for reader in readers:reader.cancel()
        await asyncio.gather(ticker,*readers,return_exceptions=True)
        if proc.returncode is None:await proc.wait()


def runtime_path(hid):
    base=location(hid);marker=base/'ready.json'
    if not marker.is_file():return base
    slot=json.loads(marker.read_text(encoding='utf-8')).get('slot','')
    if not re.fullmatch(r'releases/[a-f0-9]{16}',slot):raise ValueError('Manifest runtime tidak valid.')
    path=(base/slot).resolve()
    if not path.is_relative_to(base.resolve()):raise ValueError('Runtime keluar direktori.')
    return path


def cli(hid, base=None):
    row=entry(hid);base=base or runtime_path(hid)
    if row['kind']=='pip':
        if hid=='mini' and os.name=='nt':return [str(base/'venv/Scripts/python.exe'),str(Path(__file__).with_name('harness_stdio.py'))]
        return [str(base/'venv'/('Scripts' if os.name=='nt' else 'bin')/(row['bin']+('.exe' if os.name=='nt' else '')))]
    pkg=base/'node_modules'/row['package'];manifest=json.loads((pkg/'package.json').read_text(encoding='utf-8'))
    bins=manifest['bin'];rel=bins.get(row['bin']) if isinstance(bins,dict) else bins
    if not rel and isinstance(bins,dict):rel=next(iter(bins.values()))
    executable=(pkg/rel).resolve()
    if not executable.is_relative_to(pkg.resolve()):raise ValueError('Entry point paket keluar direktori.')
    with executable.open('rb') as handle:magic=handle.read(64)
    if magic.startswith((b'\x7fELF',b'MZ')):return [str(executable)]
    runner=base/'node_modules'/'bun/bin/bun.exe' if hid=='omp' else base/'node_modules'/('node/bin/node.exe' if os.name=='nt' else 'node/bin/node')
    return [str(runner),str(executable)]


async def install(hid):
    row=entry(hid);base=owned(location(hid));stage=base/'releases'/uuid.uuid4().hex[:16];success=False
    async with _install_lock:
        try:
            limit=Path('/sys/fs/cgroup/memory.max')
            if limit.is_file():
                value=limit.read_text().strip()
                if value.isdigit() and int(value)<1536*1024*1024:raise ValueError('Container terlalu kecil untuk pemasangan runtime asli. Atur AGEN_MEM_LIMIT=2g di .env, buat ulang container agen dengan docker compose up -d agen. Agen Mini bawaan tetap bisa dipakai.')
            if stage.parent.is_symlink() or not stage.resolve().is_relative_to(base.resolve()):raise ValueError('Direktori pemasangan keluar cache.')
            write_state(hid,'installing','Mengunduh dependensi runtime terpilih; ini dapat memerlukan beberapa menit.')
            if stage.exists():shutil.rmtree(stage)
            owned(stage);env=environment(base,hid,dependencies=stage)
            async def checked(argv,timeout=900):
                code,out,err=await process(argv,stage,env,timeout,memory_mb=1024)
                if code:
                    text=err or out
                    raise ValueError((text[:800]+'\n…\n'+text[-1200:]) if len(text)>2000 else (text or 'Pemasang gagal dengan kode '+str(code)))
            if row['kind']=='pip':
                if hid=='aider' and sys.version_info>=(3,13):raise ValueError('Aider memerlukan Python 3.10–3.12.')
                # Standard-library venv is created before untrusted packaging code runs.
                await asyncio.to_thread(venv.EnvBuilder(with_pip=True).create,stage/'venv')
                if os.name!='nt' and os.geteuid()==0:
                    for path in (stage/'venv').rglob('*'):
                        if not path.is_symlink():os.chown(path,config.KERJA_UID,config.KERJA_GID)
                    os.chown(stage/'venv',config.KERJA_UID,config.KERJA_GID)
                py=stage/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
                if hid=='hermes':
                    git=shutil.which('git')
                    if not git:raise ValueError('Git belum tersedia dalam runtime aplikasi.')
                    source=stage/'source'
                    await checked([git,'init',str(source)])
                    await checked([git,'-C',str(source),'remote','add','origin','https://github.com/nousresearch/hermes-agent.git'])
                    await checked([git,'-C',str(source),'fetch','--depth','1','origin','7157422022ff06f3e632d1dd394ee1253b17ad37'])
                    await checked([git,'-C',str(source),'checkout','--detach','FETCH_HEAD'])
                    await checked([py,'-m','pip','install','--disable-pip-version-check','-e',str(source)])
                else:await checked([py,'-m','pip','install','--disable-pip-version-check',row['package']])
            else:
                npm=shutil.which('npm')
                if not npm:raise ValueError('npm belum tersedia. Gunakan installer resmi Agen Mini yang menyertakan Node/npm.')
                # npm.cmd is a command script on Windows; invoke its JS entry without a shell.
                npm_cli=Path(npm).parent/'node_modules/npm/bin/npm-cli.js'
                launcher=[shutil.which('node'),str(npm_cli)] if os.name=='nt' else [npm]
                await checked(launcher+['install','--prefix',str(stage),'--no-audit','--no-fund','--registry=https://registry.npmjs.org','node@24.21.0'])
                if hid=='omp':await checked(launcher+['install','--prefix',str(stage),'--no-audit','--no-fund','--registry=https://registry.npmjs.org','bun@1.3.14'])
                await checked(launcher+['install','--prefix',str(stage),'--no-audit','--no-fund','--registry=https://registry.npmjs.org',row['package']+'@'+row['version']])
            code,out,err=await process(cli(hid,stage)+['--help'],stage,env,90)
            if code or not (out or err).strip():raise ValueError('Runtime tidak lulus pemeriksaan CLI: '+(err or out)[-2000:])
            # Keep the validated slot in place: Python/Windows launchers contain absolute paths.
            (base/'ready.json').write_text(json.dumps({'version':row['version'],'package':row['package'],'slot':stage.relative_to(base).as_posix()}),encoding='utf-8')
            success=True
            write_state(hid,'installed','Runtime asli terpasang; isi model/provider dan kunci sendiri.')
        except asyncio.CancelledError:
            write_state(hid,'interrupted','Pemasangan dibatalkan. Dependensi yang belum lengkap tidak akan dijalankan.');raise
        except Exception as exc:write_state(hid,'failed',str(exc))
        finally:
            if not success and stage.exists() and not stage.parent.is_symlink() and stage.resolve().is_relative_to(base.resolve()):shutil.rmtree(stage)


def select(hid, install_requested=False):
    row=entry(hid)
    if _run_lock.locked():raise ValueError('Tunggu tugas runtime selesai sebelum mengganti harness.')
    db.set_setting('harness_mode',hid)
    if row.get('kind') and install_requested and status(hid)['phase']!='installed':
        if not (_tasks.get(hid) and not _tasks[hid].done()):
            write_state(hid,'queued','Menunggu giliran pemasangan.');_tasks[hid]=asyncio.create_task(install(hid))
    return catalogue()


def cancel(hid):
    entry(hid)
    task=_tasks.get(hid)
    if task and not task.done():task.cancel()
    return status(hid)


def arguments(hid, prompt, cfg):
    model=cfg.get('model','');provider=cfg.get('provider','')
    if hid=='claude':return ['--bare','-p',prompt,'--output-format','json','--allowedTools','Read,Edit,Write,Bash','--model',model]
    if hid=='opencode':return ['run','--format','json','--model',model,prompt]
    if hid in ('pi','omp'):
        return ['--print','--mode','json','--no-session','--model',model]+(['--provider',provider] if provider else [])+[prompt]
    if hid=='hermes':return ['--oneshot',prompt,'--model',model]+(['--provider',provider] if provider else [])
    if hid=='dsh':return ['--profile','headless',prompt]
    if hid=='aider':return ['--message',prompt,'--model',model,'--yes-always','--no-auto-commits','--no-check-update','--no-gitignore','--no-show-model-warnings']
    if hid=='mini':return ['--task',prompt,'--model',model,'--yolo','--exit-immediately']
    if hid=='gemini':return ['--prompt',prompt,'--model',model,'--output-format','json','--approval-mode','default']
    raise ValueError('Adapter belum tersedia.')


def answer(hid, output):
    if hid in ('claude','gemini'):
        result=json.loads(output)
        if result.get('is_error') or result.get('error'):raise ValueError(str(result.get('error') or result.get('result','Runtime gagal.')))
        return result.get('result') or result.get('response') or ''
    if hid in ('pi','omp','opencode'):
        final=[]
        for line in output.splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type')=='error':raise ValueError(str(event.get('error',event)))
            msg=event.get('message',{})
            if msg.get('role')=='assistant':
                if msg.get('stopReason') in ('error','aborted'):raise ValueError(msg.get('errorMessage','Model gagal.'))
                texts=[x.get('text','') for x in msg.get('content',[]) if x.get('type')=='text']
                if texts:final=[''.join(texts)]
            if event.get('type')=='text':final.append(event.get('part',{}).get('text',''))
        return ''.join(final)
    return output.strip()


async def run(hid, prompt, on_event):
    row=entry(hid)
    if status(hid)['phase']!='installed':raise ValueError('Runtime belum terpasang. Buka Pengaturan → Harness.')
    if db.setting('full_access')!='1':raise ValueError('Runtime asli mempunyai alat sendiri. Aktifkan akses penuh secara sadar pada Pengaturan sebelum menjalankannya; izin alat Agen Mini tidak berlaku pada CLI eksternal.')
    cfg=settings(hid)
    if not cfg.get('model') and hid!='dsh':raise ValueError('Isi ID model runtime di Pengaturan → Harness.')
    if not any(v for k,v in cfg.get('env',{}).items() if 'KEY' in k):raise ValueError('Simpan API key runtime di Pengaturan → Harness. Login host tidak diwariskan.')
    if _run_lock.locked() or any(not task.done() for task in _tasks.values()):raise ValueError('Runtime sedang mengerjakan atau memasang tugas lain. Coba setelah selesai.')
    async with _run_lock:
        base=location(hid);work=owned(base/'workspace');env=environment(base,hid,True)
        await on_event('status','Menjalankan '+row['name']+' asli…')
        async def pulse():await on_event('status',row['name']+' masih mengerjakan tugas…')
        args=arguments(hid,prompt,cfg)
        if hid=='dsh' and cfg.get('model'):
            patch=base/'model.patch.yml'
            patch.write_text('- id: agent-default-model\n  config:\n    provider: deepseek-official\n    model: '+json.dumps(cfg['model'])+'\n',encoding='utf-8')
            args=['--profile','headless','--patch',str(patch),prompt]
        code,out,err=await process(cli(hid)+args,work,env,300,pulse)
        if code:raise ValueError(redact(err or out,hid)[-1800:] or 'Runtime keluar dengan kode '+str(code))
        result=answer(hid,out).strip()
        if not result:raise ValueError('Runtime selesai tanpa jawaban akhir yang bisa diverifikasi. '+redact(err,hid)[-500:])
        return redact(result,hid)
