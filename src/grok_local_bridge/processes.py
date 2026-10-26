"""Own-process lifecycle: lock and Windows job, never stop a PID from a state file."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import uuid

class OwnerLock:
    def __init__(self,path): self.path=Path(path);self.file=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open("a+b")
        if self.file.seek(0,2)==0: self.file.write(b"0");self.file.flush()
        self.file.seek(0)
        try:
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();self.file=None;raise RuntimeError("manager_already_running") from None
        return self
    def __exit__(self,*args):
        if self.file: self.file.close();self.file=None

def manager_alive(home):
    if not (Path(home)/"manager.lock").exists(): return False
    try:
        with OwnerLock(Path(home)/"manager.lock"): return False
    except RuntimeError: return True


def _kernel():
    k=ctypes.WinDLL("kernel32",use_last_error=True)
    k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];k.CreateJobObjectW.restype=wintypes.HANDLE
    k.OpenJobObjectW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR];k.OpenJobObjectW.restype=wintypes.HANDLE
    k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];k.AssignProcessToJobObject.restype=wintypes.BOOL
    k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];k.SetInformationJobObject.restype=wintypes.BOOL
    k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
    k.GetCurrentProcess.restype=wintypes.HANDLE
    return k

class WindowsJob:
    def __init__(self):
        if os.name!="nt": raise RuntimeError("Windows is required")
        self.name="Local\\GrokLocalBridge-"+uuid.uuid4().hex
        self.kernel=_kernel();self.handle=self.kernel.CreateJobObjectW(None,self.name)
        if not self.handle: raise OSError("job_create_failed")
        class Basic(ctypes.Structure):
            _fields_=[("process_time",ctypes.c_int64),("job_time",ctypes.c_int64),("flags",wintypes.DWORD),
                      ("min_ws",ctypes.c_size_t),("max_ws",ctypes.c_size_t),("active",wintypes.DWORD),
                      ("affinity",ctypes.c_size_t),("priority",wintypes.DWORD),("scheduling",wintypes.DWORD)]
        class IO(ctypes.Structure): _fields_=[(n,ctypes.c_uint64) for n in ("r","w","o","rb","wb","ob")]
        class Limits(ctypes.Structure):
            _fields_=[("basic",Basic),("io",IO),("process_mem",ctypes.c_size_t),("job_mem",ctypes.c_size_t),
                      ("peak_process",ctypes.c_size_t),("peak_job",ctypes.c_size_t)]
        limits=Limits();limits.basic.flags=0x2000
        if not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            self.close();raise OSError("job_limits_failed")
    def close(self):
        if self.handle: self.kernel.CloseHandle(self.handle);self.handle=None


def join_job(name):
    k=_kernel();handle=k.OpenJobObjectW(0x0001|0x0010,False,name)
    if not handle: raise OSError(ctypes.get_last_error(),"owner_job_missing")
    try:
        if not k.AssignProcessToJobObject(handle,k.GetCurrentProcess()): raise OSError(ctypes.get_last_error(),"job_join_failed")
    finally: k.CloseHandle(handle)
