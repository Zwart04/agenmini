"""Windows current-user execution with a Job Object and bounded lifetime."""
import asyncio,ctypes,os,sys
from ctypes import wintypes
from pathlib import Path

class IO_COUNTERS(ctypes.Structure):
    _fields_=[(name,ctypes.c_ulonglong) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class BASIC_LIMITS(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
class EXTENDED_LIMITS(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BASIC_LIMITS),('IoInfo',IO_COUNTERS),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]

class Job:
    def __init__(self,pid,memory_mb):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);self.kernel=kernel
        kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.handle=kernel.CreateJobObjectW(None,None)
        limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x2000|0x200|0x8;limits.BasicLimitInformation.ActiveProcessLimit=64;limits.JobMemoryLimit=memory_mb*1024*1024
        if not kernel.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):self.close();raise OSError(ctypes.get_last_error(),'Job memory limit failed')
        process=kernel.OpenProcess(0x100|0x1,False,pid)
        try:
            if not process or not kernel.AssignProcessToJobObject(self.handle,process):self.close();raise OSError(ctypes.get_last_error(),'Job assignment failed')
        finally:
            if process:kernel.CloseHandle(process)
    def close(self):
        if getattr(self,'handle',None):self.kernel.CloseHandle(self.handle);self.handle=None

async def run(argv,cwd,timeout,stdin=None,project=False):
    cwd=Path(cwd);cwd.mkdir(parents=True,exist_ok=True);argv=list(argv)
    if argv[0] in ('python3','python'):argv[0]=sys.executable
    if argv[0]=='bash':argv=[os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',argv[-1]]
    env={key:value for key,value in os.environ.items() if key.upper() in ('PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP')}
    env.update({'HOME':str(cwd),'USERPROFILE':str(cwd),'PYTHONIOENCODING':'utf-8','MPLBACKEND':'Agg','NODE_OPTIONS':'--max-old-space-size='+str(384 if project else 192),'GIT_TERMINAL_PROMPT':'0'})
    proc=await asyncio.create_subprocess_exec(*argv,cwd=cwd,env=env,stdin=asyncio.subprocess.PIPE if stdin else asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,creationflags=0x08000000)
    job=None
    try:
        job=Job(proc.pid,640 if project else 384)
        output,_=await asyncio.wait_for(proc.communicate(stdin),timeout)
        text=output.decode('utf-8',errors='replace').strip()
        if len(text)>4000:text=text[:2000]+'\n…(dipotong)…\n'+text[-1500:]
        return f'[kode keluar {proc.returncode}]\n'+(text or '(tanpa keluaran)')
    except asyncio.TimeoutError:return f'(dihentikan: lebih dari {timeout} detik)'
    finally:
        if job:job.close()
        elif proc.returncode is None:proc.kill()
        if proc.returncode is None:
            try:await asyncio.wait_for(proc.wait(),5)
            except asyncio.TimeoutError:proc.kill()
