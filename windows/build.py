"""Build an installed Windows app on Windows CI; never collect user data."""
import hashlib,json,os,re,shutil,subprocess,sys,urllib.request,urllib.parse,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def get(url):
    headers={'User-Agent':'AgenMini-Windows-Builder'}
    token=os.environ.get('GH_TOKEN','') if urllib.parse.urlsplit(url).hostname=='api.github.com' else ''
    if token:
        headers['Authorization']='Bearer '+token
    request=urllib.request.Request(url,headers=headers)
    # Never forward the CI token to dependency/CDN hosts through redirects.
    opener=urllib.request.build_opener(NoRedirect()).open if token else urllib.request.urlopen
    with opener(request,timeout=120) as response:return response.read()
def unzip(data,target):
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip():raise ValueError('Dependency ZIP CRC failed')
        for name in archive.namelist():
            if not (target/Path(name)).resolve().is_relative_to(target.resolve()):raise ValueError('Dependency ZIP traversal')
        archive.extractall(target)
def build():
    if os.name!='nt':raise SystemExit('Windows build requires Windows')
    version=re.search(r'VERSION\s*=\s*"([^"]+)"',(ROOT/'app/__init__.py').read_text())[1]
    payload=ROOT/'windows/payload';shutil.rmtree(payload,ignore_errors=True);payload.mkdir(parents=True)
    python_root=Path(sys.base_prefix)
    shutil.copytree(python_root,payload/'runtime',ignore=shutil.ignore_patterns('__pycache__','*.pyc','test','tests','cache','pip-selfcheck.json'))
    shutil.copytree(ROOT/'app',payload/'server/app',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('requirements.lock','README.md','CARA-PASANG-WINDOWS.txt','LICENSE'):
        if (ROOT/name).is_file():shutil.copy2(ROOT/name,payload/name)
    shutil.copy2(ROOT/'host-integrations.py',payload/'server/host-integrations.py')
    shutil.copy2(ROOT/'windows/launcher.py',payload/'launcher.py')
    node_version='v24.21.0';node_zip='node-'+node_version+'-win-x64.zip';base='https://nodejs.org/dist/'+node_version+'/'
    checks=get(base+'SHASUMS256.txt').decode();expected=next(line.split()[0] for line in checks.splitlines() if line.endswith(node_zip));data=get(base+node_zip)
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Node SHA256 failed')
    scratch=ROOT/'windows/node-download';scratch.mkdir(exist_ok=True);unzip(data,scratch);node_root=scratch/node_zip.removesuffix('.zip')
    shutil.copytree(node_root,payload/'bin');shutil.rmtree(scratch)
    release=json.loads(get('https://api.github.com/repos/git-for-windows/git/releases/latest'))
    asset=next(a for a in release['assets'] if re.fullmatch(r'MinGit-[\d.]+-64-bit.zip',a['name']))
    digest=asset.get('digest','')
    if not digest.startswith('sha256:'):raise ValueError('MinGit release has no official SHA256 digest')
    data=get(asset['browser_download_url'])
    if hashlib.sha256(data).hexdigest()!=digest[7:]:raise ValueError('MinGit SHA256 failed')
    (payload/'git').mkdir();unzip(data,payload/'git')
    manifest={'python':sys.version,'node':{'version':node_version,'sha256':expected},'git':{'version':release['tag_name'],'asset':asset['name'],'sha256':digest[7:]}}
    (payload/'DEPENDENCIES.json').write_text(json.dumps(manifest,indent=2))
    compiler=shutil.which('iscc') or str(Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Inno Setup 6/ISCC.exe')
    subprocess.run([compiler,'/DAppVersion='+version,str(ROOT/'windows/installer.iss')],check=True)
    exe=ROOT/'dist'/('agenmini-setup-'+version+'-windows-x64.exe');checksum=hashlib.sha256(exe.read_bytes()).hexdigest()
    if exe.read_bytes()[:2]!=b'MZ':raise ValueError('Installer is not a Windows executable')
    exe.with_suffix('.exe.sha256').write_text(checksum+'  '+exe.name+'\n')
    print('Windows installer built and SHA256 verified:',exe.name)
if __name__=='__main__':build()
