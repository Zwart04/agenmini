"""Official OAuth/account adapters. Secrets never appear in connector status."""
import json,os,time,secrets,hashlib,base64,re
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from . import config,llm,db
PROVIDERS={
 'threads':{'name':'Threads','auth':'https://www.threads.net/oauth/authorize','token':'https://graph.threads.net/oauth/access_token','base':'https://graph.threads.net','read':'threads_basic','write':'threads_content_publish','docs':'https://developers.facebook.com/documentation/threads/get-started/get-access-tokens-and-permissions'},
 'instagram':{'name':'Instagram','auth':'https://www.instagram.com/oauth/authorize','token':'https://api.instagram.com/oauth/access_token','base':'https://graph.instagram.com','read':'instagram_business_basic','write':'instagram_business_content_publish','docs':'https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login'},
 'meta_ads':{'name':'Meta Ads','auth':'https://www.facebook.com/dialog/oauth','token':'https://graph.facebook.com/oauth/access_token','base':'https://graph.facebook.com','read':'ads_read','write':'ads_management','docs':'https://developers.facebook.com/docs/marketing-api/get-started/authorization/'},
 'youtube':{'name':'YouTube','auth':'https://accounts.google.com/o/oauth2/v2/auth','token':'https://oauth2.googleapis.com/token','base':'https://www.googleapis.com/youtube/v3','read':'https://www.googleapis.com/auth/youtube.readonly','write':'https://www.googleapis.com/auth/youtube.upload','docs':'https://developers.google.com/youtube/v3/guides/authentication'},
}

def load():
    path=config.DATA_DIR/'integrations/social.json'
    if not path.is_file():return {}
    return json.loads(path.read_text())

def save(rows):
    path=config.DATA_DIR/'integrations/social.json';path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(rows));temp.chmod(0o600);temp.replace(path)

def account(provider):
    if provider not in PROVIDERS:raise ValueError('Layanan belum didukung.')
    row=load().get(provider,{})
    env=os.getenv(provider.upper()+'_ACCESS_TOKEN')
    if not row.get('access_token') and env:row={**row,'access_token':env,'environment':True}
    return row

def status():
    result=[]
    for key,info in PROVIDERS.items():
        row=account(key);verified=row.get('verified_at',0)
        result.append({'id':key,'name':info['name'],'docs':info['docs'],'configured':bool(row.get('client_id')),'credential_found':bool(row.get('access_token')),'ready':bool(verified and row.get('access_token')),'account':row.get('account',''),'checked_at':verified,'write_requested':bool(row.get('write_requested')),'note':row.get('error','') or ('Akses baca telah diuji.' if verified else 'Hubungkan aplikasi developer/OAuth, lalu uji akses baca.')})
    return result

async def request(provider,path,params=None,method='GET',data=None):
    info=PROVIDERS[provider];row=account(provider)
    if not row.get('access_token'):raise ValueError(info['name']+' belum memiliki kredensial. Hubungkan akun melalui Koneksi.')
    if provider=='youtube' and row.get('expires_at',0)<time.time()+60 and row.get('refresh_token'):
        token=await exchange(provider,{'client_id':row.get('client_id'),'client_secret':row.get('client_secret'),'refresh_token':row['refresh_token'],'grant_type':'refresh_token'})
        row.update(token);row['expires_at']=time.time()+int(token.get('expires_in',3600));rows=load();rows[provider]=row;save(rows)
    async with llm.session().request(method,info['base']+'/'+path.lstrip('/'),params=params or {},data=data,headers={'Authorization':'Bearer '+row['access_token']},timeout=30) as response:
        payload=await response.json(content_type=None)
        if response.status>=400 or payload.get('error'):
            message=str(payload.get('error',payload))[:500]
            for field in ('access_token','refresh_token','client_secret'):
                if row.get(field):message=message.replace(row[field],'[rahasia]')
            if response.status==429:message='Kuota/rate limit provider tercapai. '+message
            raise ValueError(info['name']+': '+message)
        return payload

async def verify(provider):
    row=account(provider)
    try:
        if provider=='youtube':
            payload=await request(provider,'channels',{'part':'snippet','mine':'true','maxResults':1});items=payload.get('items',[]);profile=items[0] if items else {};label=profile.get('snippet',{}).get('title','OAuth valid; kanal belum ditemukan')
        elif provider=='meta_ads':
            payload=await request(provider,'me/adaccounts',{'fields':'id,name,account_status,currency','limit':20});profile={'id':'me'};label=str(len(payload.get('data',[])))+' akun iklan dapat dibaca'
        else:
            payload=await request(provider,'me',{'fields':'id,username' if provider=='threads' else 'user_id,username'});profile=payload;label=payload.get('username') or payload.get('id') or payload.get('user_id')
            if not label:raise ValueError('Provider belum mengembalikan identitas akun.')
        rows=load();rows[provider]={**row,'verified_at':time.time(),'account':str(label),'user_id':str(profile.get('id') or profile.get('user_id') or ''),'error':''};save(rows)
        return {'ok':True,'account':str(label),'data':payload}
    except Exception as exc:
        rows=load();rows[provider]={**row,'verified_at':0,'error':str(exc)[:300]};save(rows);raise

async def exchange(provider,data):
    async with llm.session().post(PROVIDERS[provider]['token'],data={k:v for k,v in data.items() if v is not None},timeout=30) as response:
        payload=await response.json(content_type=None)
        if response.status>=400 or not payload.get('access_token'):
            message=str(payload.get('error','OAuth belum mengembalikan access token.'))[:300]
            for key in ('client_secret','code','refresh_token'):
                if data.get(key):message=message.replace(str(data[key]),'[rahasia]')
            raise ValueError('Pertukaran login belum berhasil: '+message)
        return payload

def configure(provider,fields):
    if provider not in PROVIDERS:raise ValueError('Layanan belum didukung.')
    rows=load();row=rows.get(provider,{})
    for key in ('client_id','client_secret','redirect_uri','access_token'):
        if fields.get(key):row[key]=str(fields[key]).strip()
    row['write_requested']=fields.get('write_requested') is True
    row['verified_at']=0;row['error']='';rows[provider]=row;save(rows)

def start(provider):
    row=account(provider);info=PROVIDERS[provider]
    if not row.get('client_id') or (provider!='youtube' and not row.get('client_secret')):raise ValueError('Isi App/Client ID dan secret pada formulir koneksi, bukan di chat.')
    callback=urlparse(row.get('redirect_uri',''))
    loopback=callback.scheme=='http' and callback.hostname in ('localhost','127.0.0.1') and provider=='youtube'
    if callback.scheme!='https' and not loopback:raise ValueError('Daftarkan callback HTTPS pada aplikasi provider; YouTube desktop juga mendukung loopback HTTP.')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    db.run('CREATE TABLE IF NOT EXISTS social_oauth(state TEXT PRIMARY KEY,provider TEXT,expires_at REAL,verifier TEXT)');db.run('DELETE FROM social_oauth WHERE expires_at<?',(time.time(),))
    db.run('INSERT INTO social_oauth VALUES(?,?,?,?)',(state,provider,time.time()+600,verifier))
    scope=info['read']+((' '+info['write']) if row.get('write_requested') else '')
    if provider!='youtube':scope=scope.replace(' ',',')
    params={'client_id':row['client_id'],'redirect_uri':row['redirect_uri'],'response_type':'code','scope':scope,'state':state}
    if provider=='youtube':params.update({'access_type':'offline','prompt':'consent','code_challenge_method':'S256','code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')})
    if provider=='instagram':params.update({'enable_fb_login':'0','force_authentication':'1'})
    return {'url':info['auth']+'?'+urlencode(params),'callback':row['redirect_uri']}

async def finish(provider,callback_url):
    query=parse_qs(urlparse(callback_url).query);state=(query.get('state') or [''])[0];code=(query.get('code') or [''])[0]
    db.run('CREATE TABLE IF NOT EXISTS social_oauth(state TEXT PRIMARY KEY,provider TEXT,expires_at REAL,verifier TEXT)')
    flow=db.one('SELECT * FROM social_oauth WHERE state=?',(state,))
    if not flow or flow['provider']!=provider or flow['expires_at']<time.time() or not code:raise ValueError('Callback login tidak valid/kedaluwarsa. Mulai login lagi.')
    row=account(provider);actual=urlparse(callback_url);expected=urlparse(row['redirect_uri'])
    if (actual.scheme,actual.netloc,actual.path)!=(expected.scheme,expected.netloc,expected.path):raise ValueError('Alamat callback tidak sesuai konfigurasi.')
    db.run('DELETE FROM social_oauth WHERE state=?',(state,))
    args={'client_id':row['client_id'],'client_secret':row.get('client_secret'),'redirect_uri':row['redirect_uri'],'code':code,'grant_type':'authorization_code'}
    if provider=='youtube':args['code_verifier']=flow['verifier']
    token=await exchange(provider,args);row.update(token);row['expires_at']=time.time()+int(token.get('expires_in',3600));row['verified_at']=0
    rows=load();rows[provider]=row;save(rows);return await verify(provider)

async def read(provider,operation='profile',identifier=''):
    if provider not in PROVIDERS:raise ValueError('Layanan belum didukung.')
    if identifier and not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',identifier):raise ValueError('ID akun/media belum valid.')
    if operation=='profile':return (await verify(provider))['data']
    if provider=='threads' and operation=='posts':return await request(provider,'me/threads',{'fields':'id,text,timestamp,permalink','limit':10})
    if provider=='instagram' and operation=='posts':return await request(provider,'me/media',{'fields':'id,caption,media_type,permalink,timestamp','limit':10})
    if provider=='meta_ads' and operation=='campaigns' and identifier.startswith('act_'):return await request(provider,identifier+'/campaigns',{'fields':'id,name,status,objective','limit':20})
    if provider=='youtube' and operation=='videos' and identifier:return await request(provider,'playlistItems',{'part':'snippet','playlistId':identifier,'maxResults':10})
    raise ValueError('Operasi baca/ID belum didukung. Gunakan profile untuk menemukan akun terlebih dahulu.')

async def publish(provider,text='',image_url=''):
    row=account(provider)
    if not row.get('write_requested'):raise ValueError('Aktifkan permintaan izin publikasi dan login ulang dahulu. Akses saat ini hanya baca.')
    if provider=='threads':
        container=await request(provider,'me/threads',method='POST',data={'media_type':'TEXT','text':text})
        result=await request(provider,'me/threads_publish',method='POST',data={'creation_id':container['id']})
    elif provider=='instagram':
        parsed=urlparse(image_url)
        if parsed.scheme!='https' or not parsed.hostname:raise ValueError('Instagram membutuhkan gambar pada URL HTTPS publik yang dapat diambil provider.')
        container=await request(provider,'me/media',method='POST',data={'image_url':image_url,'caption':text})
        result=await request(provider,'me/media_publish',method='POST',data={'creation_id':container['id']})
    else:raise ValueError('Publikasi layanan ini memerlukan alat MCP khusus; akses baca tersedia. Tidak ada posting yang dilakukan.')
    if not result.get('id'):raise ValueError('Provider belum mengonfirmasi publikasi.')
    return result
