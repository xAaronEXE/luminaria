import hashlib,os,subprocess,sys,time
from pathlib import Path

SCRIPT=r'''param([int]$ParentId,[string]$ParentPath,[int]$ManagerId,[string]$ManagerName,[long]$Before,[string]$Installer,[string]$Digest,[string]$Version='',[string]$Marker='')
$ErrorActionPreference='Stop'
$log=Join-Path (Split-Path -Parent $Installer) 'handoff.log'
Set-Content -LiteralPath $log -Value ('Update handoff '+(Get-Date -Format s))
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
 # Safe update: keep a copy of the current program (not its data, models or files, which are separate) so a new
 # version that cannot start is replaced by the old one automatically.
 $app=Split-Path -Parent $ParentPath; $exe=Split-Path -Leaf $ParentPath; $backup=$app+'.previous'
 $haveBackup=$false
 if($Version -and $Marker) {
  & robocopy.exe $app $backup /MIR /XJ /XD (Join-Path $app 'data') (Join-Path $app 'models') (Join-Path $app 'Files') /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
  $haveBackup = $LASTEXITCODE -lt 8
  ('Backup of the current version: '+$(if($haveBackup){'made'}else{'failed, update continues without rollback'})) | Add-Content -LiteralPath $log
 }
 'Processes exited; opening verified installer.' | Add-Content -LiteralPath $log
 $setup=Start-Process -FilePath $Installer -ArgumentList @('/LOG="'+(Join-Path (Split-Path -Parent $Installer) 'setup.log')+'"') -PassThru
 if(!$haveBackup){exit 0}
 $setup.WaitForExit()
 if($setup.ExitCode -ne 0) {
  'Setup was cancelled or failed; the current version was not changed.' | Add-Content -LiteralPath $log
  Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue; exit 0
 }
 $ok=Join-Path $Marker ('started-'+$Version+'.ok')
 Start-Sleep -Seconds 10
 if(!(Get-Process | Where-Object { $_.Path -eq $ParentPath })){Start-Process -FilePath $ParentPath}
 $deadline=(Get-Date).AddSeconds(150)
 while((Get-Date) -lt $deadline -and !(Test-Path -LiteralPath $ok)){Start-Sleep -Seconds 3}
 if(Test-Path -LiteralPath $ok) {
  ('Version '+$Version+' started correctly.') | Add-Content -LiteralPath $log
  Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue; exit 0
 }
 ('Version '+$Version+' did not start within 150 seconds; restoring the previous version.') | Add-Content -LiteralPath $log
 Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($app,[StringComparison]::OrdinalIgnoreCase) } | Stop-Process -Force -ErrorAction SilentlyContinue
 Start-Sleep -Seconds 2
 & robocopy.exe $backup $app /MIR /XJ /XD (Join-Path $app 'data') (Join-Path $app 'models') (Join-Path $app 'Files') /R:2 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
 if($LASTEXITCODE -lt 8) {
  'Previous version restored.' | Add-Content -LiteralPath $log
  Set-Content -LiteralPath (Join-Path $Marker 'rolled-back.txt') -Value $Version
  Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
  Start-Process -FilePath $ParentPath
 } else { 'Restoring failed; the copy of the previous version is kept in '+$backup | Add-Content -LiteralPath $log }
} catch {
 $_.Exception.Message | Add-Content -LiteralPath $log
 exit 1
}
'''

def launch(target,version=''):
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
        '-Before',str(int(time.time()*1000)),'-Installer',str(target),'-Digest',digest,'-Version',str(version),'-Marker',str(Path(target).parent)],creationflags=subprocess.CREATE_NO_WINDOW)
    return True
