"""Real gateway lifecycle and connection contracts in a disposable data directory."""
import hashlib,json,os,pathlib,socket,subprocess,sys,tempfile,time,urllib.request,urllib.error
import jwt

exe=str(pathlib.Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='agenmini-gateway-') as folder:
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PATH','TEMP','TMP')}
    secret='disposable-gateway-contract-secret-32-bytes'
    env.update(DATA_DIR=folder,HOME=folder,APPDATA=folder,USERPROFILE=folder,PORT=str(port),HOST='127.0.0.1',JWT_SECRET=secret,INITIAL_PASSWORD='disposable-password')
    log=open(pathlib.Path(folder)/'gateway.log','w')
    p=subprocess.Popen([exe],env=env,stdout=log,stderr=log,**({'creationflags':0x08000000} if os.name=='nt' else {}))
    def call(path,method='GET',body=None,headers=None):
        req=urllib.request.Request('http://127.0.0.1:'+str(port)+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            try:data=json.load(e)
            except ValueError:data={}
            return e.code,data
    try:
        for _ in range(60):
            try:
                if call('/health')[0]==200:break
            except OSError:pass
            if p.poll() is not None:raise AssertionError(pathlib.Path(folder,'gateway.log').read_text())
            time.sleep(.2)
        admin={'Cookie':'auth_token='+jwt.encode({'authenticated':True,'iat':int(time.time()),'exp':int(time.time())+60},secret,algorithm='HS256')}
        assert call('/api/settings','PATCH',{'requireLogin':True,'requireApiKey':True},admin)[0]==200
        unauthorized=call('/v1/models');assert unauthorized[0]==401,unauthorized
        assert call('/api/providers')[0]==401
        status,key=call('/api/keys','POST',{'name':'Contract test'},admin);assert status==200,(status,key)
        assert key.get('key'),key
        auth={'Authorization':'Bearer '+key['key']}
        assert call('/api/models?connected=1',headers=admin)[0]==200
        status,connection=call('/api/connections','POST',{'provider':'openai','authType':'apikey','name':'Fixture','apiKey':'PRIVATE_DISPOSABLE_KEY'},admin)
        assert status in (200,201),(status,connection)
        status,data=call('/api/connections',headers=admin);assert status==200
        assert len(data)==1 and 'PRIVATE_DISPOSABLE_KEY' not in json.dumps(data)
        status,flow=call('/api/oauth/pkce/authorize?provider=codex',headers=admin);assert status==200 and flow.get('state') and flow.get('codeVerifier')
        for path in ('/dashboard','/api/version/update','/api/usage/stats','/v1/images/generations','/api/proxy-pools/vercel-deploy'):
            assert call(path,'POST' if path.endswith(('update','generations','deploy')) else 'GET',headers=admin)[0]==404,path
        print('PASS real gateway: authentication, key, secret-safe connection CRUD, model listing, PKCE and removed feature routes.')
    finally:
        p.terminate();p.wait(timeout=15);log.close()
