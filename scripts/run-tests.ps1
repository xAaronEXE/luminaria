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
foreach($file in Get-ChildItem tests -Filter *.py | Sort-Object Name){
  $name=$file.BaseName
  $out=& $python -W ignore -m unittest "tests.$name" 2>&1 | Out-String
  $summary=($out -split "`n" | Where-Object {$_ -match '^(OK|FAILED)'} | Select-Object -Last 1).Trim()
  if($LASTEXITCODE -eq 0){$passed++;$lines+="ok    $name  $summary"}
  else{$failed+=$name;$lines+="FAIL  $name  $summary";$lines+=($out -split "`n" | Where-Object {$_ -match 'Error|assert|File "'} | Select-Object -First 12 | ForEach-Object {"        $_".TrimEnd()})}
}
if($node){
  foreach($file in Get-ChildItem tests -Filter *.cjs | Sort-Object Name){
    $out=& $node $file.FullName 2>&1 | Out-String
    if($LASTEXITCODE -eq 0){$passed++;$lines+="ok    $($file.Name)"}else{$failed+=$file.Name;$lines+="FAIL  $($file.Name)";$lines+=($out -split "`n" | Select-Object -First 8 | ForEach-Object {"        $_".TrimEnd()})}
  }
}
$lines+='';$lines+="$passed passed, $($failed.Count) failed"
$lines | Set-Content -LiteralPath $Report -Encoding utf8
$lines | Select-Object -Last 1 | Write-Host
if($failed.Count){exit 1}
