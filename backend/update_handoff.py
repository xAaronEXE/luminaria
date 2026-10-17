import hashlib,os,subprocess,sys,time
from pathlib import Path

SCRIPT=r'''param([int]$ParentId,[string]$ParentPath,[int]$ManagerId,[string]$ManagerName,[long]$Before,[string]$Installer,[string]$Digest)
$ErrorActionPreference='Stop'
$log=Join-Path (Split-Path -Parent $Installer) 'handoff.log'
function OwnedProcess([int]$ProcessId,[string]$Name) {
 if($ProcessId -le 0){return $null}
 $p=Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
 if(!$p){return $null}
 if($p.ProcessName -ne $Name -or ([DateTimeOffset]$p.StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -gt $Before){throw 'Process identity changed; update stopped.'}
 return $p
}
try {
 $parent=OwnedProcess $ParentId ([IO.Path]::GetFileNameWithoutExtension($ParentPath))
 $manager=OwnedProcess $ManagerId $ManagerName
 if($parent -and !$parent.WaitForExit(30000)) {
  $parent=OwnedProcess $ParentId ([IO.Path]::GetFileNameWithoutExtension($ParentPath))
  if($parent){Stop-Process -InputObject $parent -Force;$parent.WaitForExit()}
 }
 $manager=OwnedProcess $ManagerId $ManagerName
 if($manager) {
  & "$env:SystemRoot\System32\taskkill.exe" /PID $ManagerId /T /F | Out-Null
  if($LASTEXITCODE -ne 0 -and (Get-Process -Id $ManagerId -ErrorAction SilentlyContinue)){throw 'Model manager did not stop.'}
  if(!$manager.WaitForExit(10000)){throw 'Model manager is still running.'}
 }
 if((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLower() -ne $Digest){throw 'Installer checksum changed; nothing opened.'}
 'Processes exited; opening verified installer.' | Set-Content -LiteralPath $log
 Start-Process -FilePath $Installer -ArgumentList @('/LOG="'+(Join-Path (Split-Path -Parent $Installer) 'setup.log')+'"')
} catch {
 $_.Exception.Message | Set-Content -LiteralPath $log
 exit 1
}
'''

def launch(target):
    if os.name!='nt' or not getattr(sys,'frozen',False):
        subprocess.Popen([str(target)])
        return False
    from . import runtime
    manager=runtime.swap_process
    manager_id=manager.pid if manager and manager.poll() is None else 0
    script=Path(target).parent/'update-handoff.ps1'
    script.write_text(SCRIPT,encoding='utf-8-sig')
    shell=Path(os.environ['SystemRoot'])/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
    with Path(target).open('rb') as handle:digest=hashlib.file_digest(handle,'sha256').hexdigest()
    subprocess.Popen([str(shell),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),
        '-ParentId',str(os.getpid()),'-ParentPath',sys.executable,'-ManagerId',str(manager_id),'-ManagerName','llama-swap',
        '-Before',str(int(time.time()*1000)),'-Installer',str(target),'-Digest',digest],creationflags=subprocess.CREATE_NO_WINDOW)
    return True
