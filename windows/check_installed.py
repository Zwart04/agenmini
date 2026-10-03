"""Actual install, native tools, authenticated API, update and uninstall checks."""
import asyncio,json,os,subprocess,sys,time,urllib.request,http.cookiejar
from pathlib import Path
install=Path(sys.argv[1]);exe=Path(sys.argv[2]);data=Path(os.environ['AGENMINI_DATA_DIR']);data.mkdir(parents=True,exist_ok=True)
server=None
try:
    python=install/'runtime/python.exe';env=os.environ.copy()
    server=subprocess.Popen([str(python),str(install/'launcher.py'),'--no-browser'],env=env)
    base='http://127.0.0.1:8765'
    for _ in range(90):
        try:urllib.request.urlopen(base+'/sehat',timeout=1);break
        except Exception:
            if server.poll() is not None:raise RuntimeError('Installed launcher exited')
            time.sleep(1)
    else:raise RuntimeError('Installed app not healthy')
    jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    def request(path,body=None):
        req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
        with client.open(req,timeout=60) as response:return json.load(response)
    password=(data/'initial-password.txt').read_text().strip();assert request('/api/login',{'password':password})['ok']
    assert request('/api/mode',{'mode':'online'})['ok']
    assert not (data/'runtime-request').exists()
    assert request('/api/office')['bots'];assert request('/api/social')['connections'];assert 'learning' in request('/api/office/learning')
    script="""import asyncio,json\nfrom app import tools,config\nasync def go():\n a=await tools._run_sandboxed(['python3','-I','-c','print(125*8)'],timeout=10)\n assert a.strip()=='[kode keluar 0]\\n1000',a\n b=await tools._run_sandboxed(['node','-e','console.log(40+2)'],timeout=10)\n assert b.strip()=='[kode keluar 0]\\n42',b\n c=await tools._run_sandboxed(['python3','-I','-c','import time;time.sleep(10)'],timeout=1)\n assert 'dihentikan' in c,c\n print('PASS installed Python, Node, and timeout Job Object')\nasyncio.run(go())\n"""
    toolenv=env.copy();toolenv['DATA_DIR']=str(data);toolenv['PATH']=str(install/'bin')+';'+str(install/'runtime')+';'+env['PATH']
    subprocess.run([str(python),'-c',script],cwd=install/'server',env=toolenv,check=True,timeout=60)
    marker=data/'keep-private.txt';marker.write_text('test-data-preserved')
    subprocess.run([str(python),str(install/'launcher.py'),'--stop'],env=env,check=True,timeout=30);server.wait(timeout=30)
    result=subprocess.run([str(exe),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/DIR='+str(install)],timeout=240);assert result.returncode==0
    assert marker.read_text()=='test-data-preserved' and (data/'db/agen.sqlite').exists() and list((data/'backup').glob('windows-update-*'))
    uninstaller=next(install.glob('unins*.exe'));result=subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],timeout=120);assert result.returncode==0
    assert marker.read_text()=='test-data-preserved' and (data/'db/agen.sqlite').exists()
    print('PASS installed health/auth/connectors, update backup/data preservation, uninstall retains data')
finally:
    if server and server.poll() is None:
        try:subprocess.run([str(install/'runtime/python.exe'),str(install/'launcher.py'),'--stop'],timeout=20)
        except Exception:server.kill()
