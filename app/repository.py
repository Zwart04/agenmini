"""GitHub clone broker: credentials stay in the privileged fetch process only."""
import asyncio
import base64
import os
import re
import shutil
import tempfile
from pathlib import Path
from . import config, integrations

_lock = asyncio.Lock()

async def clone(url, target):
    from . import tools
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?', url):
        return 'Error: gunakan URL GitHub tanpa token atau parameter.'
    async with _lock:
        if target.exists():
            return 'Error: folder sudah ada; berkas sebelumnya tidak ditimpa.'
        target.parent.mkdir(parents=True, exist_ok=True)
        try: os.chown(target.parent, config.KERJA_UID, config.KERJA_GID)
        except (OSError, AttributeError): pass
        try: token = integrations.token('github')
        except ValueError: token = ''
        if not token:
            result = await tools._run_sandboxed(['git','-c','core.hooksPath=/dev/null','clone','--depth','1','--',url,str(target)],timeout=120)
            if not result.startswith('[kode keluar 0]'):
                return result+'\nClone gagal. Untuk repo privat, hubungkan akun GitHub di Koneksi > Akun terhubung.'
            if not (target/'.git'/'HEAD').is_file():return 'Error: Git melaporkan selesai tetapi metadata repo tidak ditemukan.'
            return result+'\nRepo terverifikasi di '+str(target.relative_to(config.WORK_DIR))+'. Baca AGENTS.md/README dan manifest sebelum mengubah kode.'
        # No checkout, hooks, submodules or user-controlled Git configuration in this process.
        private = config.DATA_DIR/'integrations'
        stage = Path(tempfile.mkdtemp(prefix='clone-',dir=private))
        checkout = stage/'repo'
        env = {'PATH':os.environ.get('PATH','') if os.name=='nt' else '/usr/local/bin:/usr/bin:/bin','HOME':str(stage),'LANG':'C.UTF-8',
               'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,
               'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'http.https://github.com/.extraheader',
               'GIT_CONFIG_VALUE_0':'Authorization: Basic '+base64.b64encode(('x-access-token:'+token).encode()).decode()}
        if os.name=='nt':
            env.update({k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP')})
        try:
            proc = await asyncio.create_subprocess_exec('git','-c','core.hooksPath=/dev/null','-c','init.templateDir=',
                '-c','http.followRedirects=false','-c','protocol.file.allow=never','clone','--no-checkout','--depth','1','--',url,str(checkout),
                env=env,stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,start_new_session=True)
            try: output,_ = await asyncio.wait_for(proc.communicate(),120)
            except asyncio.TimeoutError:

                if os.name=='posix':os.killpg(proc.pid,9)
                else:proc.kill()
                await proc.communicate()
                return 'Error: clone GitHub melewati batas 120 detik. Repo sumber dan folder lama tetap dipertahankan.'
            if proc.returncode:
                message=output.decode(errors='replace').replace(token,'[rahasia]').replace(env['GIT_CONFIG_VALUE_0'],'[rahasia]')
                return '[kode keluar '+str(proc.returncode)+']\n'+message[-2000:]+'\nClone gagal; periksa akses akun ke repositori.'
            if target.exists():return 'Error: folder dibuat oleh proses lain; tidak ditimpa.'
            if os.name=='posix' and os.geteuid()==0:
                for directory,dirs,files in os.walk(checkout):
                    os.chown(directory,config.KERJA_UID,config.KERJA_GID)
                    for name in dirs+files:os.chown(Path(directory)/name,config.KERJA_UID,config.KERJA_GID,follow_symlinks=False)
            os.rename(checkout,target)
            result=await tools._run_sandboxed(['git','-c','core.hooksPath=/dev/null','-c','filter.lfs.required=false','-c','filter.lfs.smudge=','-c','filter.lfs.process=','-C',str(target),'checkout','HEAD','--','.'],timeout=120,project=True)
            if not result.startswith('[kode keluar 0]'):
                return result+'\nGit sudah diunduh; checkout gagal. Folder dipertahankan di '+str(target.relative_to(config.WORK_DIR))+'.'
            return '[kode keluar 0]\nRepo terverifikasi di '+str(target.relative_to(config.WORK_DIR))+'. Clone memakai login GitHub host; token tidak disimpan dalam repo atau diberikan ke sandbox. Baca AGENTS.md/README dan manifest sebelum mengubah kode. Push tidak dilakukan.'
        finally:
            shutil.rmtree(stage)
