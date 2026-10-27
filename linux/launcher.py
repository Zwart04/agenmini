# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-user Linux desktop/CLI entry. Never installs packages or runs as root."""
import fcntl
import html
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / 'runtime/bin/python3'
SERVER = ROOT / 'server'


def private_dir():
    root = Path(os.environ.get('AGENMINI_DATA_DIR') or Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'agenmini')
    root = root.expanduser().absolute()
    if root.is_symlink():raise ValueError('Direktori data tidak boleh berupa symlink.')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != os.getuid():raise ValueError('Direktori data bukan milik pengguna ini.')
    root.chmod(0o700)
    return root


def secret(root, name):
    path = root/name
    if path.is_symlink():raise ValueError('Berkas secret tidak boleh berupa symlink.')
    try:
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    except FileExistsError:
        if path.stat().st_uid != os.getuid():raise ValueError('Pemilik secret tidak sesuai.')
        path.chmod(0o600)
        value=path.read_text().strip()
        if len(value)<24:raise ValueError('Secret tersimpan tidak valid: '+name)
        return value
    with os.fdopen(fd, 'w') as output:output.write(secrets.token_urlsafe(32))
    return path.read_text().strip()


def environment(data):
    port = int(os.environ.get('AGENMINI_PORT', '8765'))
    gateway_port = int(os.environ.get('AGENMINI_GATEWAY_PORT', '20128'))
    if not 1024 <= port <= 65535 or not 1024 <= gateway_port <= 65535 or port == gateway_port:
        raise ValueError('Port desktop/gateway tidak valid.')
    env = os.environ.copy()
    for name in ('PYTHONPATH','PYTHONHOME'):env.pop(name, None)
    env.update(DATA_DIR=str(data), WEB_HOST='127.0.0.1', WEB_PORT_INTERNAL=str(port),
               WEB_TLS='0', WEB_PASSWORD=secret(data, 'initial-password.txt'),
               ROUTER_JWT_SECRET=secret(data, 'gateway-secret.txt'),
               ROUTER_BASE=f'http://127.0.0.1:{gateway_port}',
               LOCAL_API_BASE=os.environ.get('LOCAL_API_BASE','http://127.0.0.1:8080/v1'),
               LLM_BACKEND='online', AGENMINI_DESKTOP='1',
               PATH=str(ROOT/'bin')+os.pathsep+str(ROOT/'runtime/bin')+os.pathsep+env.get('PATH',''))
    return env, f'http://127.0.0.1:{port}'


def identity(pid):
    try:
        proc = Path('/proc')/str(pid)
        if proc.stat().st_uid != os.getuid():return None
        args = (proc/'cmdline').read_bytes().split(b'\0')
        if str(Path(__file__).resolve()).encode() not in args or b'serve' not in args:return None
        if (proc/'exe').resolve() != PYTHON.resolve():return None
        return (proc/'stat').read_text().rsplit(')',1)[1].split()[19]
    except (OSError,ValueError):return None


def running(data):
    try:
        row=json.loads((data/'desktop.pid').read_text())
        return row['pid'] if identity(row['pid']) == row['start'] else None
    except (OSError,ValueError,KeyError,TypeError):return None


def healthy(url):
    try:
        with urllib.request.urlopen(url+'/sehat', timeout=1) as response:
            return response.status == 200 and json.load(response).get('ok') is True
    except (OSError,ValueError):return False


def serve(data, env):
    with (data/'desktop.lock').open('a') as lock:
        try:fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 0
        (data/'desktop.pid').write_text(json.dumps({'pid':os.getpid(),'start':identity(os.getpid())}))
        children=[]
        def terminate(*_):raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM, terminate)
        try:
            gateway=ROOT/'bin/agenmini-gateway'
            if not gateway.is_file():raise ValueError('Binary gateway tidak ada; pasang kembali paket resmi.')
            gateway_env={**env,'DATA_DIR':str(data/'gateway'),'HOST':'127.0.0.1',
                         'PORT':env['ROUTER_BASE'].rsplit(':',1)[1],
                         'JWT_SECRET':env['ROUTER_JWT_SECRET'],'INITIAL_PASSWORD':env['WEB_PASSWORD'],
                         'API_KEY_SECRET':secret(data,'gateway-api-secret.txt'),
                         'MACHINE_ID_SALT':secret(data,'gateway-salt.txt')}
            children.append(subprocess.Popen([str(gateway)], cwd=SERVER, env=gateway_env))
            children.append(subprocess.Popen([str(PYTHON),'-s','-m','app.main'], cwd=SERVER, env=env))
            while all(child.poll() is None for child in children):time.sleep(.3)
            return 1
        except KeyboardInterrupt:return 0
        finally:
            for child in children:
                if child.poll() is None:child.terminate()
            for child in children:
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait()
            (data/'desktop.pid').unlink(missing_ok=True)


def welcome(data, env, url):
    path=data/'welcome.html'
    text=(ROOT/'welcome.html').read_text(encoding='utf-8')
    text=text.replace('{{PASSWORD}}',html.escape(env['WEB_PASSWORD'])).replace('{{URL}}',html.escape(url,quote=True))
    path.write_text(text,encoding='utf-8');path.chmod(0o600)
    return path.as_uri()


def main():
    args=sys.argv[1:];command=args[0] if args else 'open'
    if command in ('--help','help','-h'):
        print('Agen Mini · app + CLI\nagenmini open | start | stop | status | password | model [ID] | provider [online|router|auto|local] | coffee | license\nData: ~/.local/share/agenmini (atau AGENMINI_DATA_DIR). Update lewat package manager/paket rilis resmi.');return 0
    if command in ('--version','version'):
        sys.path.insert(0,str(SERVER));from app import VERSION
        print('Agen Mini '+VERSION);return 0
    if command in ('coffee','support','dukung'):
        print('Buy me a coffee ☕ https://tako.id/Zwart04/gift');return 0
    if command in ('license','lisensi'):
        print('Agen Mini · Copyright (C) 2026 Zwart04 · GPL-3.0-or-later\nTanpa jaminan. Source: https://github.com/Zwart04/agenmini');return 0
    if os.getuid() == 0:raise ValueError('Jalankan Agen Mini desktop sebagai pengguna biasa, bukan root.')
    data=private_dir();first=not (data/'initial-password.txt').exists();env,url=environment(data)
    if command=='serve':return serve(data,env)
    if command=='stop':
        pid=running(data)
        if pid:
            os.kill(pid,signal.SIGTERM)
            for _ in range(100):
                if not running(data):break
                time.sleep(.1)
            if running(data):raise ValueError('Proses belum berhenti; periksa desktop.log.')
        print('Agen Mini berhenti; data tetap tersimpan.');return 0
    if command in ('open','start'):
        if not running(data):
            if healthy(url):raise ValueError('Port dipakai aplikasi lain; atur AGENMINI_PORT.')
            log=data/'desktop.log'
            if log.exists() and log.stat().st_size>2_000_000:log.replace(data/'desktop-previous.log')
            with log.open('ab') as output:
                child=subprocess.Popen([str(PYTHON),'-s',str(Path(__file__).resolve()),'serve'],
                    env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            for _ in range(100):
                if healthy(url):break
                if child.poll() is not None:raise ValueError('Aplikasi berhenti; periksa '+str(log))
                time.sleep(.2)
            else:raise ValueError('Startup belum siap; periksa '+str(log))
        print(url)
        if command=='open' and '--no-browser' not in args:
            webbrowser.open(welcome(data,env,url) if first else url)
        elif first:print('Sandi awal tersimpan privat. Lihat dengan: agenmini password')
        return 0
    if command=='status':
        print(json.dumps({'running':bool(running(data)),'ready':bool(running(data)) and healthy(url),'url':url,'data_dir':str(data)}));return 0
    if command=='password' and len(args)==1:
        print(env['WEB_PASSWORD']);return 0
    return subprocess.call([str(PYTHON),'-s','-m','app.cli',*args],cwd=SERVER,env=env)


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError) as error:print('Agen Mini: '+str(error),file=sys.stderr);raise SystemExit(1)
