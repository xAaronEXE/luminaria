"""The admin helper: a short, fixed list of jobs that need administrator rights, and nothing else.

The assistant never gets an administrator shell. It asks for one of these operations by name with plain
arguments; the helper checks the arguments against strict patterns and builds the command itself, so nothing
the model writes is ever run with administrator rights. Every use asks for approval (in every mode, unless the
user has granted that operation type in Settings), shows Windows' own UAC prompt, and is logged.
"""
import asyncio, json, os, re, subprocess, time
from pathlib import Path

PACKAGE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.+_-]{1,99}$')            # winget ids like Git.Git, Python.Python.3.12
FEATURE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{1,79}$')               # Windows optional feature names
SERVICE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
RULE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _.-]{2,59}$')

OPERATIONS = {
    'install_program': 'Install a program with winget (Windows Package Manager)',
    'uninstall_program': 'Uninstall a program with winget',
    'enable_windows_feature': 'Turn on a Windows optional feature',
    'service_start': 'Start a Windows service',
    'service_stop': 'Stop a Windows service',
    'service_startup': 'Set how a Windows service starts (automatic, manual or disabled)',
    'firewall_allow_port': 'Allow incoming connections on a port through Windows Firewall',
    'firewall_remove_rule': 'Remove a firewall rule that Luminaria added',
}
# Services that keep Windows running or secure are never touched.
PROTECTED_SERVICES = {'windefend', 'mpssvc', 'wuauserv', 'eventlog', 'rpcss', 'lsm', 'samss', 'winmgmt', 'bfe', 'cryptsvc', 'dhcp',
                      'dnscache', 'lanmanserver', 'lanmanworkstation', 'schedule', 'sense', 'securityhealthservice', 'wscsvc', 'trustedinstaller'}
RULE_PREFIX = 'Luminaria - '


def _q(text):
    """Quote for PowerShell; arguments are already restricted to safe characters."""
    return "'" + str(text).replace("'", "''") + "'"


def build(operation, args):
    """Validate the request and return (description, PowerShell command). Raises ValueError for anything off the list."""
    args = args or {}
    if operation not in OPERATIONS: raise ValueError('The admin helper only does: ' + ', '.join(OPERATIONS))
    if operation in ('install_program', 'uninstall_program'):
        pkg = str(args.get('package', ''))
        if not PACKAGE.match(pkg): raise ValueError('Give the exact winget package id, for example Git.Git')
        if operation == 'install_program':
            return f'Install {pkg}', f'winget install --id {_q(pkg)} --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity'
        return f'Uninstall {pkg}', f'winget uninstall --id {_q(pkg)} --exact --silent --disable-interactivity'
    if operation == 'enable_windows_feature':
        name = str(args.get('feature', ''))
        if not FEATURE.match(name): raise ValueError('Give the Windows feature name, for example Microsoft-Windows-Subsystem-Linux')
        return f'Turn on the Windows feature {name}', f'Enable-WindowsOptionalFeature -Online -FeatureName {_q(name)} -All -NoRestart'
    if operation.startswith('service_'):
        name = str(args.get('service', ''))
        if not SERVICE.match(name): raise ValueError('Give the service name')
        if name.lower() in PROTECTED_SERVICES: raise ValueError(f'{name} keeps Windows running or secure, so Luminaria never changes it')
        if operation == 'service_start': return f'Start the service {name}', f'Start-Service -Name {_q(name)}'
        if operation == 'service_stop': return f'Stop the service {name}', f'Stop-Service -Name {_q(name)}'
        mode = str(args.get('startup', '')).capitalize()
        if mode not in ('Automatic', 'Manual', 'Disabled'): raise ValueError('startup must be automatic, manual or disabled')
        return f'Set {name} to start {mode.lower()}', f'Set-Service -Name {_q(name)} -StartupType {mode}'
    if operation == 'firewall_allow_port':
        try: port = int(args.get('port'))
        except (TypeError, ValueError): raise ValueError('Give a port number') from None
        if not 1024 <= port <= 65535: raise ValueError('Only ports 1024 to 65535 can be opened')
        proto = str(args.get('protocol', 'TCP')).upper()
        if proto not in ('TCP', 'UDP'): raise ValueError('protocol must be TCP or UDP')
        name = str(args.get('name', '') or f'port {port}')
        if not RULE.match(name): raise ValueError('Rule name: letters, numbers, spaces, dots, dashes')
        rule = RULE_PREFIX + name
        # Private networks only: never opens the PC to public Wi-Fi.
        return (f'Allow incoming {proto} port {port} on private networks', f'New-NetFirewallRule -DisplayName {_q(rule)} -Direction Inbound -Action Allow '
                f'-Protocol {proto} -LocalPort {port} -Profile Private')
    name = str(args.get('name', ''))
    if not RULE.match(name): raise ValueError('Give the rule name Luminaria used when adding it')
    return f'Remove the firewall rule {RULE_PREFIX}{name}', f'Remove-NetFirewallRule -DisplayName {_q(RULE_PREFIX + name)}'


async def run(operation, args, log_folder, timeout=600):
    """Run one approved operation elevated. Windows shows its UAC prompt; output comes back through a log file."""
    description, command = build(operation, args)
    if os.name != 'nt': return {'status': 'error', 'message': 'The admin helper only works on Windows.'}
    folder = Path(log_folder); folder.mkdir(parents=True, exist_ok=True)
    out = folder / f'admin-{int(time.time() * 1000)}.log'
    inner = f'try {{ {command} *>&1 | Out-File -FilePath {_q(out)} -Encoding utf8; exit $LASTEXITCODE }} catch {{ $_ | Out-File -FilePath {_q(out)} -Encoding utf8 -Append; exit 1 }}'
    launcher = (f"$p = Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru "
                f"-ArgumentList @('-NoProfile','-NonInteractive','-Command',{_q(inner)}); exit $p.ExitCode")
    proc = await asyncio.create_subprocess_exec('powershell.exe', '-NoProfile', '-NonInteractive', '-Command', launcher,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    try: _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill(); return {'status': 'error', 'operation': operation, 'message': f'{description} did not finish within {timeout} seconds.'}
    text = out.read_text(encoding='utf-8', errors='replace')[-6000:] if out.exists() else ''
    if proc.returncode != 0 and not text and b'canceled by the user' in (err or b'').lower():
        return {'status': 'error', 'operation': operation, 'message': 'The Windows administrator prompt was declined, so nothing was changed.'}
    return {'status': 'done' if proc.returncode == 0 else 'error', 'operation': operation, 'description': description,
            'exit_code': proc.returncode, 'output': text or (err or b'').decode('utf-8', 'replace')[-2000:]}
