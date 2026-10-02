#!/usr/bin/env python3
"""Owner-only host credential discovery. Only allowlisted read APIs; secrets never enter reports."""
import json,os,re,shutil,time,urllib.request,urllib.error,subprocess
from pathlib import Path
try:import tomllib
except ImportError:tomllib=None

def atomic(path,data):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(path.parent,0o700)
    tmp=path.with_suffix('.tmp');fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(data,f)
    tmp.replace(path);os.chmod(path,0o600)

def check(url,token):
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json','User-Agent':'AgenMini-host-discovery'})
    try:
        with urllib.request.urlopen(req,timeout=8) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as exc:return exc.code,{}
    except Exception:return 0,{}

def discover(home,directory,force=False):
    home=Path(home);directory=Path(directory);report=directory/'integrations/status.json'
    if not force and report.exists() and time.time()-report.stat().st_mtime<300:return
    secrets={};rows=[]
    gh_token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN','');source='environment' if gh_token else ''
    ghfile=home/'.config/gh/hosts.yml'
    if not gh_token and ghfile.is_file():
        # Only github.com host, not another enterprise host or arbitrary YAML tags.
        part=re.search(r'^github\.com:\s*\n((?:[ \t].*\n?)*)',ghfile.read_text(),re.M)
        match=re.search(r'^\s+oauth_token:\s*[\"\']?([^\s\"\']+)',part.group(1),re.M) if part else None
        if match:gh_token=match.group(1);source='gh auth login'
    if not gh_token and shutil.which('gh'):
        try:
            found=subprocess.run(['gh','auth','token','--hostname','github.com'],capture_output=True,text=True,timeout=8,env={**os.environ,'GH_CONFIG_DIR':str(home/'.config/gh')})
            if found.returncode==0:gh_token=found.stdout.strip();source='gh auth login (keyring)'
        except (OSError,subprocess.TimeoutExpired):pass
    status,data=check('https://api.github.com/user',gh_token) if gh_token else (0,{})
    if status==200:secrets['github']=gh_token
    rows.append({'id':'github','name':'GitHub','installed':bool(shutil.which('gh')),'credential_found':bool(gh_token),'ready':status==200,'source':source,'account':data.get('login','') if status==200 else '', 'message':'Login valid; alat baca repositori tersedia.' if status==200 else 'Kredensial ditolak/koneksi gagal.' if gh_token else 'Belum login. Jalankan gh auth login di host, lalu deteksi ulang.'})
    cf=os.environ.get('CLOUDFLARE_API_TOKEN') or os.environ.get('CF_API_TOKEN','');cfsource='environment' if cf else '';oauth=False
    for file in [home/'.config/.wrangler/config/default.toml',home/'.wrangler/config/default.toml']:
        if not cf and file.is_file() and tomllib:
            try:cf=tomllib.loads(file.read_text()).get('oauth_token','');oauth=bool(cf);cfsource='wrangler login' if cf else ''
            except (ValueError,OSError):pass
    status,data=check('https://api.cloudflare.com/client/v4/accounts?per_page=5',cf) if cf else (0,{})
    valid=status==200 and data.get('success') is True
    if valid:secrets['cloudflare']=cf
    rows.append({'id':'cloudflare','name':'Cloudflare API','installed':bool(shutil.which('wrangler')),'credential_found':bool(cf),'ready':valid,'source':cfsource,'message':'Akses baca akun terverifikasi.' if valid else 'Kredensial ditemukan; akses akun ditolak, kedaluwarsa, atau jaringan gagal.' if cf else 'Login wrangler atau sediakan CLOUDFLARE_API_TOKEN pada host.'})
    rows.append({'id':'cloudflared','name':'Cloudflare Tunnel','installed':bool(shutil.which('cloudflared')),'credential_found':(home/'.cloudflared/cert.pem').is_file(),'ready':False,'message':'Sertifikat tunnel tidak dianggap sebagai API token. Tunnel tidak dibuat otomatis.'})
    commands=['git','gh','docker','node','npm','python3','cloudflared','wrangler','aws','gcloud','az','vercel','netlify','terraform','kubectl']
    atomic(directory/'integrations/secrets.json',secrets)
    atomic(report,{'checked_at':time.time(),'connections':rows,'commands':[{'name':name,'installed':bool(shutil.which(name))} for name in commands],'note':'Deteksi akun pengguna pemasang/supervisor. Token disimpan privat, hanya digunakan server untuk API baca; login host baru tidak dipindahkan otomatis dari VPS lama.'})
if __name__=='__main__':
    import sys
    discover(os.environ.get('AGEN_HOST_HOME',str(Path.home())),sys.argv[1] if len(sys.argv)>1 else '/opt/agenmini/data','--force' in sys.argv)
