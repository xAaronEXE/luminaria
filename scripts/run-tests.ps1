# Runs Luminaria's whole test suite with the build Python (which has every app dependency) and the
# built-in Node.js. Writes a short report; exits non-zero if anything failed.
param([string]$Report="$PSScriptRoot/../data/test-report.txt")
$ErrorActionPreference='Continue'
$root=Split-Path $PSScriptRoot -Parent
Set-Location $root
$python=if($env:STUDIO_BUILD_PYTHON){$env:STUDIO_BUILD_PYTHON}elseif(Test-Path "$root/runtime/local-ai/agent-tools/python-env/Scripts/python.exe"){"$root/runtime/local-ai/agent-tools/python-env/Scripts/python.exe"}else{(Get-Command python).Source}
$node=if(Test-Path "$root/runtime/agent-tools/node/node.exe"){"$root/runtime/agent-tools/node/node.exe"}else{(Get-Command node -ErrorAction SilentlyContinue).Source}
$env:PYTHONIOENCODING='utf-8'
$lines=@("Luminaria tests  $(Get-Date -Format 'yyyy-MM-dd HH:mm')  commit $(git rev-parse --short HEAD 2>$null)",'')
$failed=@(); $passed=0
# Only tests tracked in the repository, each judged by unittest's own verdict (warnings on stderr are not failures).
$env:STUDIO_DATA=Join-Path ([IO.Path]::GetTempPath()) ("luminaria-tests-"+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $env:STUDIO_DATA | Out-Null
foreach($rel in (git ls-files 'tests/*.py' | Sort-Object)){
  $name=[IO.Path]::GetFileNameWithoutExtension($rel)
  $out=(& $python -W ignore -m unittest "tests.$name" 2>&1 | ForEach-Object {"$_"}) -join "`n"
  $verdict=($out -split "`n" | Where-Object {$_ -match '^(OK|FAILED)'} | Select-Object -Last 1)
  $verdict=if($verdict){"$verdict".Trim()}else{'no result'}
  if($verdict -like 'OK*'){$passed++;$lines+="ok    $name  $verdict"}
  else{$failed+=$name;$lines+="FAIL  $name  $verdict";$lines+=($out -split "`n" | Where-Object {$_ -match 'Error|assert|File "'} | Select-Object -First 14 | ForEach-Object {"        $_".TrimEnd()})}
}
Remove-Item -Recurse -Force $env:STUDIO_DATA -ErrorAction SilentlyContinue
if($node){
  foreach($rel in (git ls-files 'tests/*.cjs' | Sort-Object)){
    $file=Get-Item $rel
    $out=(& $node $file.FullName 2>&1 | ForEach-Object {"$_"}) -join "`n"
    if($LASTEXITCODE -eq 0){$passed++;$lines+="ok    $($file.Name)"}else{$failed+=$file.Name;$lines+="FAIL  $($file.Name)";$lines+=($out -split "`n" | Select-Object -First 8 | ForEach-Object {"        $_".TrimEnd()})}
  }
}
$lines+='';$lines+="$passed passed, $($failed.Count) failed"
$lines | Set-Content -LiteralPath $Report -Encoding utf8
$lines | Select-Object -Last 1 | Write-Host
if($failed.Count){exit 1}
