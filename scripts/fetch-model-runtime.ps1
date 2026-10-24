$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$target=Join-Path $taskRoot 'runtime/local-ai/runtime-vulkan'
$archive=Join-Path $env:TEMP 'luminaria-llama-b11675-vulkan.zip'
$url='https://github.com/ggml-org/llama.cpp/releases/download/b11675/llama-b11675-bin-win-vulkan-x64.zip'
$expected='c8c8aa59b2c7a429e468457ab536192d0966c387f774d79931beb767e97fd942'
Invoke-WebRequest $url -OutFile $archive
if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower() -ne $expected){throw 'Runtime checksum mismatch; nothing extracted'}
New-Item -ItemType Directory -Force $target | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $target -Force
if(!(Test-Path (Join-Path $target 'llama-server.exe'))){throw 'Runtime archive did not contain llama-server.exe'}
Write-Output 'Verified model runtime is ready for build.ps1'
