"""Installed desktop launcher; data lives outside the install directory."""
import os,sys,json,secrets,subprocess,time,webbrowser,ctypes,hashlib
from pathlib import Path

def main():
    install=Path(__file__).resolve().parent;data=Path(os.environ.get('AGENMINI_DATA_DIR',Path(os.environ['LOCALAPPDATA'])/'AgenMini'/'data'))
    data.mkdir(parents=True,exist_ok=True);url='http://127.0.0.1:'+os.environ.get('AGENMINI_PORT','8765')
    pidfile=data/'desktop.pid';python=install/'runtime/python.exe'
    if '--backup' in sys.argv:
        import sqlite3,shutil
        backup=data/'backup'/('windows-update-'+time.strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True,exist_ok=True)
        database=data/'db/agen.sqlite'
        if database.is_file():
            with sqlite3.connect(database) as source,sqlite3.connect(backup/'agen.sqlite') as target:source.backup(target)
        if (data/'integrations').is_dir():shutil.copytree(data/'integrations',backup/'integrations',dirs_exist_ok=True)
        return
    if '--stop' in sys.argv:
        if pidfile.is_file():
            try:
                pid=int(pidfile.read_text());kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p;handle=kernel.OpenProcess(0x1000,False,pid)
                if handle:
                    buffer=ctypes.create_unicode_buffer(32768);size=ctypes.c_ulong(32768);kernel.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
                    if kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)) and Path(buffer.value).resolve()==python.resolve():subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True)
                    kernel.CloseHandle(handle)
            except (ValueError,OSError):pass
        return
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];kernel.CreateMutexW.restype=ctypes.c_void_p
    mutex=kernel.CreateMutexW(None,False,'Local\\AgenMini-'+hashlib.sha256(str(data).encode()).hexdigest()[:20])
    if ctypes.get_last_error()==183:
        if '--no-browser' not in sys.argv:webbrowser.open(url)
        return
    passwordfile=data/'initial-password.txt';first=not passwordfile.exists()
    if first:passwordfile.write_text(secrets.token_urlsafe(18));passwordfile.chmod(0o600)
    env=os.environ.copy();env.update({'DATA_DIR':str(data),'WEB_HOST':'127.0.0.1','WEB_PORT_INTERNAL':url.rsplit(':',1)[1],'WEB_TLS':'0','WEB_PASSWORD':passwordfile.read_text().strip(),'LLM_BACKEND':'online','PATH':str(install/'bin')+';'+str(install/'runtime')+';'+str(install/'git/cmd')+';'+str(install/'git/mingw64/bin')+';'+env.get('PATH','')})
    log=data/'desktop.log'
    if log.exists() and log.stat().st_size>2_000_000:log.replace(data/'desktop-previous.log')
    with log.open('ab') as output:
        process=subprocess.Popen([str(python),'-m','app.main'],cwd=install/'server',env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=0x08000000)
        pidfile.write_text(str(process.pid))
        if first and '--no-browser' not in sys.argv:ctypes.windll.user32.MessageBoxW(None,'Kata sandi awal Agen Mini:\n\n'+passwordfile.read_text()+'\n\nSimpan kata sandi ini. Pengaturan akun dapat dilakukan di web.','Agen Mini — Setup awal',0)
        if '--no-browser' not in sys.argv:
            import urllib.request
            for _ in range(60):
                try:urllib.request.urlopen(url+'/sehat',timeout=1);break
                except Exception:
                    if process.poll() is not None:break
                    time.sleep(1)
            webbrowser.open(url)
        process.wait()
    kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(mutex)
if __name__=='__main__':main()
