"""Windows Job Objects for commands and scripts the assistant runs.

Every process a command starts, and every process those start, belongs to one job. Closing the job ends all of
them at once. A command that is stopped or times out is ended with everything it started. Something a finished
command left running on purpose (a dev server, a watcher) keeps running until Luminaria closes or crashes; then
Windows closes the job and ends it, so nothing the assistant started outlives the app.

This controls process lifetime only. It is not a file or network sandbox.
On other systems these functions do nothing.
"""
import os

_SUPPORTED = os.name == 'nt'
if _SUPPORTED:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _JobObjectExtendedLimitInformation = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x400
    _PROCESS_SET_QUOTA, _PROCESS_TERMINATE = 0x0100, 0x0001

    class _IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                                                      'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class _Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', wintypes.DWORD), ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD)]

    class _Extended(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', _Basic), ('IoInfo', _IO), ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t), ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    _k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    _k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)


class Job:
    """One job per command. Use `with Job() as job: job.add(pid)`; leaving the block ends everything still running."""
    def __init__(self):
        self.handle = None
        if not _SUPPORTED: return
        handle = _k32.CreateJobObjectW(None, None)
        if not handle: return
        info = _Extended()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
        if not _k32.SetInformationJobObject(handle, _JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
            _k32.CloseHandle(handle); return
        self.handle = handle

    def add(self, pid):
        """Put a just-started process (and so everything it starts later) into the job. Returns False if Windows refused."""
        if not self.handle: return False
        process = _k32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, int(pid))
        if not process: return False
        try: return bool(_k32.AssignProcessToJobObject(self.handle, process))
        finally: _k32.CloseHandle(process)

    def close(self):
        """End every process still in the job."""
        if self.handle:
            _k32.CloseHandle(self.handle); self.handle = None

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


_ALIVE = []
def keep_alive(job):
    """Hold a finished command's job open until Luminaria exits, so what it left running stays up until then."""
    if getattr(job, 'handle', None): _ALIVE.append(job)
    while len(_ALIVE) > 200: _ALIVE.pop(0).close()   # the oldest are ended first if a session starts hundreds
