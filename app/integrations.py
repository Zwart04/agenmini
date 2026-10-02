"""Allowlisted read APIs with private host-discovered credentials."""
import json,re
import aiohttp
from . import config,llm

def status():
    path=config.DATA_DIR/'integrations/status.json'
    if not path.exists():return {'connections':[],'commands':[],'note':'Deteksi host belum berjalan. Supervisor VPS akan memeriksa login host; instalasi mandiri dapat menjalankan host-integrations.py.'}
    return json.loads(path.read_text())

def token(name):
    path=config.DATA_DIR/'integrations/secrets.json'
    keys=json.loads(path.read_text()) if path.exists() else {}
    value=keys.get(name)
    if not value:raise ValueError('Koneksi '+name+' belum terverifikasi. Periksa Koneksi > Akun host.')
    return value

async def read(service,path):
    if service=='github':
        if not re.fullmatch(r'/user(?:/repos\?per_page=30)?|/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/(?:readme|languages|issues\?per_page=10))?',path):raise ValueError('Path GitHub tidak diizinkan. Alat ini hanya baca akun/repositori/README/issues.')
        base='https://api.github.com'
    elif service=='cloudflare':
        if path not in ('/accounts?per_page=20','/zones?per_page=20'):raise ValueError('Path Cloudflare tidak diizinkan; hanya baca akun/zona.')
        base='https://api.cloudflare.com/client/v4'
    else:raise ValueError('Layanan tidak dikenal.')
    async with llm.session().get(base+path,headers={'Authorization':'Bearer '+token(service),'Accept':'application/json','User-Agent':'AgenMini'},timeout=aiohttp.ClientTimeout(total=15),allow_redirects=False) as response:
        if response.status!=200:return 'Error: '+service+' HTTP '+str(response.status)+'. Periksa izin akun/kuota.'
        data=await response.json();return json.dumps(data,ensure_ascii=False)[:28000]
