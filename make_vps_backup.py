"""Private, consistent migration backup. Run on host; never publish this archive."""
import json,os,sqlite3,subprocess,tarfile,tempfile,time,shutil
from pathlib import Path

def sqlite_backup(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    a=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True);b=sqlite3.connect(target)
    try:a.backup(b);assert b.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:a.close();b.close()

def build(root):
    root=Path(root);dest=root/'data/backup/vps-migration.tar.gz';dest.parent.mkdir(mode=0o700,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='agenmini-export-') as tmp:
        stage=Path(tmp)
        shutil.copy2(root/'.env',stage/'env')
        for source in (root/'data').rglob('*'):
            rel=source.relative_to(root/'data')
            if rel.parts[0] in ('models','backup','integrations','cert') or source.is_symlink() or not source.is_file():continue
            if source.name.endswith(('.sqlite-wal','.sqlite-shm','.db-wal','.db-shm','.lock','.log','.tmp','.part')) or source.name in ('model-busy','task-busy','maintenance','runtime-request','runtime-processing','update-request'):continue
            target=stage/'data'/rel;target.parent.mkdir(parents=True,exist_ok=True)
            if source.suffix in ('.sqlite','.db'):sqlite_backup(source,target)
            else:shutil.copy2(source,target)
        for volume,folder,dbpath in [('agenmini_router-data','router-data','db/data.sqlite'),('agenmini_freellmapi-data','freellmapi-data','freeapi.db')]:
            r=subprocess.run(['docker','volume','inspect',volume],capture_output=True,text=True)
            if r.returncode:continue
            source=Path(json.loads(r.stdout)[0]['Mountpoint'])/dbpath
            if source.exists():sqlite_backup(source,stage/folder/dbpath)
        (stage/'RESTORE.txt').write_text('Backup privat Agen Mini. Berisi sandi/token/riwayat; jangan unggah ke GitHub.\nPada VPS baru: pasang versi yang sama, hentikan container Agen Mini dan timer supervisor, pulihkan env menjadi /opt/agenmini/.env (mode600), pulihkan data/ ke /opt/agenmini/data, pulihkan router-data/ dan freellmapi-data/ ke volume Docker dengan nama agenmini_router-data dan agenmini_freellmapi-data. Jangan menimpa data aplikasi lain. Jalankan pemasang lagi. Sertifikat dan model dibuat/diunduh ulang; login akun host GitHub/Cloudflare ulang.\n')
        temporary=dest.with_suffix('.tmp')
        with tarfile.open(temporary,'w:gz') as tar:
            for entry in stage.iterdir():tar.add(entry,arcname=entry.name)
        temporary.replace(dest);os.chmod(dest,0o600)
    (dest.parent/'vps-migration.sha256').write_text(__import__('hashlib').sha256(dest.read_bytes()).hexdigest()+'  vps-migration.tar.gz\n')
    print('Private migration backup ready:',dest, dest.stat().st_size)
if __name__=='__main__':
    import sys
    build(sys.argv[1] if len(sys.argv)>1 else '/opt/agenmini')
