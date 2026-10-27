"""Exercise an installed desktop and CLI with disposable per-user data."""
import http.cookiejar
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import tempfile
import urllib.request


def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def check():
    with tempfile.TemporaryDirectory(prefix='agenmini-native-check-') as folder:
        data=Path(folder)/'data'
        env={**os.environ,'AGENMINI_DATA_DIR':str(data),'AGENMINI_PORT':str(free_port()),'AGENMINI_GATEWAY_PORT':str(free_port())}
        def cli(*args):return subprocess.check_output(['agenmini',*args],env=env,text=True,timeout=60)
        expected=re.search(r'VERSION = "([^"]+)"',Path('/opt/agenmini/server/app/__init__.py').read_text())[1]
        assert expected in cli('--version')
        assert 'tako.id/Zwart04/gift' in cli('coffee')
        assert 'GPL-3.0-or-later' in cli('license')
        try:
            url=cli('start','--no-browser').splitlines()[0]
            state=json.loads(cli('status'));assert state['running'] and state['ready']
            assert data.stat().st_mode&0o777==0o700
            for name in ('initial-password.txt','gateway-secret.txt'):assert (data/name).stat().st_mode&0o777==0o600
            cookies=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
            payload=json.dumps({'password':(data/'initial-password.txt').read_text()}).encode()
            login=urllib.request.Request(url+'/api/login',data=payload,headers={'Content-Type':'application/json','Origin':url})
            assert client.open(login,timeout=20).status==200
            assert 'model' in cli('model','native-smoke-model')
            settings=json.load(client.open(url+'/api/settings',timeout=20))
            assert settings.get('online_model')=='native-smoke-model',settings.keys()
            assert 'Provider' in cli('provider','router')
            assert 'native-router-model' in cli('model','native-router-model')
            assert 'native-router-model' in cli('model')
            assert client.open(url,timeout=20).status==200
            runtime='/opt/agenmini/runtime/bin/python3'
            check="import asyncio; from app import tools; result=asyncio.run(tools._run_sandboxed(['python','-I','-c','import matplotlib.pyplot as plt; plt.figure(); plt.close(); print(42)'])); assert result.strip()=='[kode keluar 0]\\n42',result; print('PASS bundled Python and plotting tools')"
            subprocess.run([runtime,'-c',check],cwd='/opt/agenmini/server',env={**env,'DATA_DIR':str(data),'AGENMINI_DESKTOP':'1'},check=True,timeout=60)
            print('PASS installed app, loopback health, login, CLI model/provider persistence, private data permissions')
        finally:
            cli('stop')
            assert json.loads(cli('status'))['running'] is False
            assert (data/'db/agen.sqlite').is_file(),'Stop must preserve data'
        print('PASS clean stop and data preservation')


if __name__=='__main__':check()
