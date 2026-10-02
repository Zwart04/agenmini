"""SQLite online backup before switching managed router engines; fail closed."""
import json,subprocess,sys,sqlite3,time,os
from pathlib import Path

def backup(destination):
    result=subprocess.run(['docker','volume','inspect','agenmini_router-data'],capture_output=True,text=True)
    if result.returncode:
        # A genuinely absent optional volume means there is nothing to migrate.
        listing=subprocess.run(['docker','volume','ls','--format','{{.Name}}'],capture_output=True,text=True,check=True)
        if 'agenmini_router-data' not in listing.stdout.splitlines():return
        raise RuntimeError('Volume router tidak dapat diperiksa.')
    source=Path(json.loads(result.stdout)[0]['Mountpoint'])/'db/data.sqlite'
    if not source.exists():return
    target=Path(destination)/('router-before-lite-'+time.strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True,mode=0o700);os.chmod(target,0o700)
    original=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True);copy=sqlite3.connect(target/'data.sqlite')
    try:
        original.backup(copy);assert copy.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:original.close();copy.close()
    os.chmod(target/'data.sqlite',0o600)
    print('Backup router tersimpan:',target)
if __name__=='__main__':backup(sys.argv[1])
