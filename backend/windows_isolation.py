"""Launch Windows commands in an AppContainer with no network capabilities."""

import asyncio
import base64
import ctypes as c
from ctypes import wintypes as w
from contextlib import ExitStack, contextmanager
import msvcrt
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import uuid

from .jobs import Job


def _api(dll, name, result, *arguments):
    call = getattr(dll, name)
    call.argtypes = arguments
    call.restype = result
    return call


kernel = c.WinDLL('kernel32', use_last_error=True)
userenv = c.WinDLL('userenv', use_last_error=True)
advapi = c.WinDLL('advapi32', use_last_error=True)
ole = c.WinDLL('ole32')
ptr, size = c.c_void_p, c.c_size_t

create_profile = _api(userenv, 'CreateAppContainerProfile', w.LONG, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, ptr, w.DWORD, c.POINTER(ptr))
delete_profile = _api(userenv, 'DeleteAppContainerProfile', w.LONG, w.LPCWSTR)
profile_path = _api(userenv, 'GetAppContainerFolderPath', w.LONG, w.LPCWSTR, c.POINTER(ptr))
sid_to_string = _api(advapi, 'ConvertSidToStringSidW', w.BOOL, ptr, c.POINTER(ptr))
free_sid = _api(advapi, 'FreeSid', ptr, ptr)
local_free = _api(kernel, 'LocalFree', ptr, ptr)
task_free = _api(ole, 'CoTaskMemFree', None, ptr)

init_attrs = _api(kernel, 'InitializeProcThreadAttributeList', w.BOOL, ptr, w.DWORD, w.DWORD, c.POINTER(size))
update_attr = _api(kernel, 'UpdateProcThreadAttribute', w.BOOL, ptr, w.DWORD, size, ptr, size, ptr, ptr)
delete_attrs = _api(kernel, 'DeleteProcThreadAttributeList', None, ptr)
create_process = _api(kernel, 'CreateProcessW', w.BOOL, w.LPCWSTR, w.LPWSTR, ptr, ptr, w.BOOL, w.DWORD, ptr, w.LPCWSTR, ptr, ptr)
drive_type = _api(kernel, 'GetDriveTypeW', w.UINT, w.LPCWSTR)
close_handle = _api(kernel, 'CloseHandle', w.BOOL, w.HANDLE)
resume_thread = _api(kernel, 'ResumeThread', w.DWORD, w.HANDLE)
wait_for_process = _api(kernel, 'WaitForSingleObject', w.DWORD, w.HANDLE, w.DWORD)
terminate_process = _api(kernel, 'TerminateProcess', w.BOOL, w.HANDLE, w.UINT)
get_exit_code = _api(kernel, 'GetExitCodeProcess', w.BOOL, w.HANDLE, c.POINTER(w.DWORD))


class SecurityCapabilities(c.Structure):
    _fields_ = [('sid', ptr), ('capabilities', ptr), ('count', w.DWORD), ('reserved', w.DWORD)]


class StartupInfo(c.Structure):
    _fields_ = [('cb', w.DWORD), ('reserved', ptr), ('desktop', ptr), ('title', ptr),
                ('x', w.DWORD), ('y', w.DWORD), ('x_size', w.DWORD), ('y_size', w.DWORD),
                ('x_chars', w.DWORD), ('y_chars', w.DWORD), ('fill', w.DWORD), ('flags', w.DWORD),
                ('show', w.WORD), ('reserved_size', w.WORD), ('reserved_data', ptr),
                ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]


class StartupInfoEx(c.Structure):
    _fields_ = [('startup', StartupInfo), ('attributes', ptr)]


class ProcessInfo(c.Structure):
    _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]


def _check(success):
    if not success:
        raise c.WinError(c.get_last_error())


def _check_hresult(result, operation):
    if result < 0:
        raise OSError(f'{operation} failed (HRESULT 0x{result & 0xffffffff:08X}).')


@contextmanager
def _profile():
    # A fresh SID has no pre-existing firewall or loopback exemptions.
    name = 'Luminaria.Command.' + uuid.uuid4().hex
    sid = ptr()
    _check_hresult(create_profile(name, 'Luminaria command', 'Isolated command execution', None, 0, c.byref(sid)),
                   'Creating the Windows command profile')
    try:
        sid_text = ptr()
        _check(sid_to_string(sid, c.byref(sid_text)))
        try:
            folder = ptr()
            _check_hresult(profile_path(c.wstring_at(sid_text), c.byref(folder)), 'Finding the command workspace')
            try:
                yield sid, Path(c.wstring_at(folder))
            finally:
                task_free(folder)
        finally:
            local_free(sid_text)
    finally:
        free_sid(sid)
        delete_profile(name)


@contextmanager
def _attributes(values):
    needed = size()
    init_attrs(None, len(values), 0, c.byref(needed))
    if not needed.value:
        raise c.WinError(c.get_last_error())
    buffer = c.create_string_buffer(needed.value)
    _check(init_attrs(buffer, len(values), 0, c.byref(needed)))
    try:
        for attribute, value in values:
            _check(update_attr(buffer, 0, attribute, c.byref(value), c.sizeof(value), None, None))
        yield c.cast(buffer, ptr)
    finally:
        delete_attrs(buffer)


def _environment(workspace, cwd, python):
    # Construct an allowlist. In particular, host credentials, model keys, user paths,
    # proxy configuration, Python overrides, and inherited tool search paths stay out.
    windows = Path(os.environ['SystemRoot'])
    system = windows / 'System32'
    temp = workspace / 'Temp'
    temp.mkdir(exist_ok=True)
    entries = {
        'SystemRoot': str(windows), 'WINDIR': str(windows), 'PATH': str(system),
        'PATHEXT': '.COM;.EXE;.BAT;.CMD',
        'COMSPEC': str(system / 'cmd.exe'), 'TEMP': str(temp), 'TMP': str(temp),
        'LOCALAPPDATA': str(workspace), 'APPDATA': str(workspace),
        'USERPROFILE': str(workspace), 'HOME': str(workspace),
        'LUMINARIA_WORKSPACE': str(cwd),
        'PYTHONIOENCODING': 'utf-8', 'PYTHONNOUSERSITE': '1',
    }
    if python: entries['LUMINARIA_PYTHON'] = str(python)
    return c.create_unicode_buffer('\0'.join(f'{k}={v}' for k, v in sorted(entries.items(), key=lambda item: item[0].casefold())) + '\0\0')


def _launch(argv, cwd, workspace, sid, streams, python):
    # Pass only the three standard handles, never a socket or token from the host.
    handles = (w.HANDLE * 3)(*(msvcrt.get_osfhandle(stream.fileno()) for stream in streams))
    capabilities = SecurityCapabilities(sid, None, 0, 0)
    attributes = [(0x20002, handles), (0x20009, capabilities)]
    environment = _environment(workspace, cwd, python)
    command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
    child = ProcessInfo()
    with _attributes(attributes) as attrs:
        start = StartupInfoEx()
        start.startup.cb = c.sizeof(start)
        start.startup.flags = 0x100  # STARTF_USESTDHANDLES
        start.startup.stdin, start.startup.stdout, start.startup.stderr = handles
        start.attributes = attrs
        for handle in handles:
            os.set_handle_inheritable(handle, True)
        try:
            # Create suspended, with a Unicode environment and extended attributes.
            flags = 0x00000004 | 0x00000400 | 0x00080000 | 0x08000000
            _check(create_process(argv[0], command, None, None, True, flags, environment,
                                  str(cwd), c.byref(start), c.byref(child)))
        finally:
            for handle in handles:
                os.set_handle_inheritable(handle, False)
    return child


def powershell_command(command):
    shell = Path(os.environ['SystemRoot']) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    # Windows PowerShell can initialize its provider at the drive root even when
    # CreateProcess receives an explicit current directory.
    prefix = (
        "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
        "New-PSDrive -Name Work -PSProvider FileSystem -Root $env:LUMINARIA_WORKSPACE | Out-Null; "
        "Set-Location Work:; "
        "if ($env:LUMINARIA_PYTHON) { function python { & $env:LUMINARIA_PYTHON @args; if ($LASTEXITCODE) { exit $LASTEXITCODE } } }; "
    )
    result = "\nif (-not $?) { if ($LASTEXITCODE) { exit $LASTEXITCODE }; exit 1 }"
    encoded = base64.b64encode((prefix + command + result).encode('utf-16-le')).decode('ascii')
    return [str(shell), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded]


def _stage_python(executable, workspace):
    source = Path(executable).parent
    versions = list(source.glob('python[0-9]*.zip'))
    if len(versions) != 1:
        raise OSError('The isolated Python tool requires Luminaria’s bundled portable Python.')
    target = workspace / 'python'
    target.mkdir()
    for path in source.iterdir():
        if path.name == 'python.exe' or path == versions[0] or path.suffix.lower() in ('.dll', '.pyd'):
            shutil.copyfile(path, target / path.name)
    (target / (versions[0].stem + '._pth')).write_text(
        versions[0].name + '\n.\n../work\n', encoding='ascii'
    )
    return target / 'python.exe'


async def execute(argv, timeout, *, script=None, inputs=(), python_bundle=None):
    """Run one offline command in an ephemeral workspace. An unavailable boundary fails closed."""
    if not Path(argv[0]).is_absolute():
        raise ValueError('The isolated executable must have an absolute path.')
    loop = asyncio.get_running_loop()
    with ExitStack() as stack:
        sid, workspace = stack.enter_context(_profile())
        argv = list(argv)
        cwd = workspace / 'work'
        cwd.mkdir()
        for relative, data in inputs:
            if relative.anchor or '..' in relative.parts:
                raise ValueError('Invalid isolated input path.')
            target = cwd / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        python = _stage_python(python_bundle, workspace) if python_bundle else None
        if python and argv[0] == python_bundle:
            argv[0] = str(python)
        if script is not None:
            suffix, source = script
            path = workspace / ('script' + suffix)
            path.write_text(source, encoding='utf-8')
            argv.append(str(path))
        stdin = stack.enter_context(open(os.devnull, 'rb'))
        stdout = stack.enter_context(tempfile.TemporaryFile())
        stderr = stack.enter_context(tempfile.TemporaryFile())
        job = stack.enter_context(Job())
        if not job.handle:
            raise OSError('Windows did not create a command Job Object.')
        child = _launch(argv, cwd, workspace, sid, (stdin, stdout, stderr), python)
        stack.callback(close_handle, child.process)
        stack.callback(close_handle, child.thread)
        try:
            if not job.add(child.pid):
                raise OSError('Windows did not assign the command to its Job Object.')
            _check(resume_thread(child.thread) != 0xFFFFFFFF)
            deadline = loop.time() + timeout
            while True:
                state = wait_for_process(child.process, 0)
                if state == 0:
                    break
                if state != 0x102:
                    raise c.WinError(c.get_last_error())
                if loop.time() >= deadline:
                    return {'exit_code': None, 'timed_out': True, 'error': 'The isolated command timed out.'}
                if any(os.fstat(stream.fileno()).st_size > 4 * 1024 * 1024 for stream in (stdout, stderr)):
                    return {'exit_code': None, 'error': 'The isolated command exceeded its output limit.'}
                await asyncio.sleep(0.05)
            code = w.DWORD()
            _check(get_exit_code(child.process, c.byref(code)))
        finally:
            # Also handles a suspended child for which job assignment failed.
            job.close()
            if wait_for_process(child.process, 0) == 0x102:
                terminate_process(child.process, 1)
            wait_for_process(child.process, 5000)
        stdout.seek(0)
        stderr.seek(0)
        return {'exit_code': code.value, 'stdout': stdout.read(4 * 1024 * 1024).decode('utf-8', 'replace'),
                'stderr': stderr.read(4 * 1024 * 1024).decode('utf-8', 'replace')}


async def check():
    """Verify that an isolated command can read its inputs and cannot reach loopback."""
    staged = await execute(powershell_command('Get-Content -Raw probe.txt'), 10, inputs=[
        (Path('probe.txt'), b'Luminaria sandbox probe'),
    ])
    if staged['exit_code'] != 0 or staged.get('stdout', '').strip() != 'Luminaria sandbox probe':
        return False

    accepted = asyncio.Event()

    def on_connection(_reader, writer):
        accepted.set()
        writer.close()

    server = await asyncio.start_server(on_connection, '127.0.0.1', 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        curl = Path(os.environ['SystemRoot']) / 'System32' / 'curl.exe'
        result = await execute(
            [str(curl), '--noproxy', '*', '--max-time', '3', f'http://127.0.0.1:{port}/'], 10
        )
        return result['exit_code'] in (7, 28) and not accepted.is_set()
