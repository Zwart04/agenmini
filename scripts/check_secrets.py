"""Scan all Git refs with a verified Gitleaks binary, without runtime dependencies."""
import argparse,hashlib,io,json,subprocess,sys,tempfile,urllib.request,zipfile,tarfile
from pathlib import Path
VERSION='8.30.1'
ROOT=Path(__file__).resolve().parents[1]

def download(name):
    req=urllib.request.Request(f'https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/'+name,headers={'User-Agent':'AgenMini-Security'})
    with urllib.request.urlopen(req,timeout=120) as r:return r.read()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scanner',type=Path);args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='agenmini-secret-audit-') as temp:
        folder=Path(temp);scanner=args.scanner
        if scanner is None:
            windows=sys.platform=='win32'
            name=f'gitleaks_{VERSION}_'+('windows_x64.zip' if windows else 'linux_x64.tar.gz')
            raw=download(name);checks=download(f'gitleaks_{VERSION}_checksums.txt').decode()
            expected=next(line.split()[0] for line in checks.splitlines() if line.endswith(name))
            if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Scanner checksum mismatch')
            scanner=folder/('gitleaks.exe' if windows else 'gitleaks')
            if windows:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:scanner.write_bytes(z.read('gitleaks.exe'))
            else:
                with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as t:scanner.write_bytes(t.extractfile('gitleaks').read())
                scanner.chmod(0o700)
        report=folder/'report.json'
        result=subprocess.run([str(scanner.resolve()),'git',str(ROOT),'--log-opts=--all','--redact=100','--no-banner','--report-format=json','--report-path='+str(report)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        rows=json.loads(report.read_text()) if report.exists() else []
        print('Secret scan findings:',len(rows))
        for row in rows:print(row['RuleID'],row['File'],row['StartLine'],row.get('Commit','')[:8])
        if result.returncode not in (0,1):print('Scanner could not complete',file=sys.stderr)
        return result.returncode

if __name__=='__main__':sys.exit(main())
