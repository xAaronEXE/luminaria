param(
    [Parameter(Mandatory)][string]$DesktopExe,
    [Parameter(Mandatory)][string]$ModelFile,
    [Parameter(Mandatory)][string]$Installer,
    [string]$ReportDirectory = (Join-Path $env:LOCALAPPDATA ("Luminaria-Test-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))),
    [int]$Context = 32768,
    [int]$Port = 43210
)
$ErrorActionPreference = 'Stop'
$exe = (Resolve-Path -LiteralPath $DesktopExe).Path
$model = Get-Item -LiteralPath $ModelFile
$setup = Get-Item -LiteralPath $Installer
if ($setup.VersionInfo.ProductVersion.Trim() -ne '0.4.5') { throw 'Use the 0.4.5 candidate installer.' }
if (Get-Process LocalAIStudio,llama-swap,llama-server -ErrorAction SilentlyContinue) {
    throw 'Close Luminaria and local llama.cpp processes first so the test can own the local model ports.'
}
if (Test-Path -LiteralPath $ReportDirectory) { throw 'Choose a new report directory.' }
$data = Join-Path $ReportDirectory 'data'
$workspace = Join-Path $ReportDirectory 'workspace'
New-Item -ItemType Directory -Path $data,$workspace -Force | Out-Null
$env:STUDIO_DATA = $data
$env:STUDIO_PORT = [string]$Port
$env:PYTHONUTF8 = '1'
$profile = @{id='local'; name='Local test'; provider='local'}
@{selected='local'; require_sign_in=$false; profiles=@($profile)} |
    ConvertTo-Json -Depth 4 | Set-Content (Join-Path $data 'profiles.json') -Encoding utf8NoBOM
@{id='fixture'; name=$model.Name; model_file=$model.FullName; context=$Context} |
    ConvertTo-Json -AsArray | Set-Content (Join-Path $data 'models.json') -Encoding utf8NoBOM
@{workspace=$workspace; model='fixture'; model_file=$model.FullName; context=$Context; output_tokens=512;
  keep_model_loaded=3600; access_mode='review'} |
    ConvertTo-Json | Set-Content (Join-Path $data 'config.json') -Encoding utf8NoBOM
$sha = (Get-FileHash -LiteralPath $setup.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$revision = '43cb48d577282e971f1f68dec7ec0b785371573e'
if ($sha -ne 'e6c6de07f0c4148463b04428b9522ed58d2bad48a62ddd0acbb08f748e7f2185') {
    throw 'Installer checksum differs from the verified candidate.'
}
$base = "http://127.0.0.1:$Port"
$desktop = Start-Process -FilePath $exe -ArgumentList '--server' -PassThru
$ready = $false
for ($i=0; $i -lt 90; $i++) {
    try { $boot = Invoke-RestMethod "$base/api/bootstrap" -TimeoutSec 2 }
    catch { Start-Sleep 1; continue }
    if ($boot.version -ne '0.4.5') { throw "Expected desktop version 0.4.5, got $($boot.version)." }
    $ready = $true
    break
}
if (!$ready) { throw "Desktop startup timed out. See $data." }
python (Join-Path $PSScriptRoot 'benchmark-model-led.py') --base $base --workspace $workspace --output (Join-Path $ReportDirectory 'benchmark.json') --model $model.Name --revision $revision --sha256 $sha --desktop-pid $desktop.Id --desktop-exe $exe
if ($LASTEXITCODE) { throw "Benchmark process failed. See $ReportDirectory." }
Write-Output "Benchmark and diagnostic logs saved to $ReportDirectory. The test desktop is still running."
