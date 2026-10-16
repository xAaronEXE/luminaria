$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$version=(Get-Content "$PSScriptRoot/VERSION" -Raw).Trim()
if($version -notmatch '^\d+\.\d+\.\d+$'){throw "VERSION must look like 1.2.3"}
$python=if($env:STUDIO_BUILD_PYTHON){$env:STUDIO_BUILD_PYTHON}elseif(Test-Path "$PSScriptRoot/runtime/local-ai/agent-tools/python-env/Scripts/python.exe"){"$PSScriptRoot/runtime/local-ai/agent-tools/python-env/Scripts/python.exe"}else{(Get-Command python -ErrorAction Stop).Source}
& $python -m PyInstaller --noconfirm --clean --workpath .build/work --distpath .build/dist --specpath .build --windowed --onedir --name LocalAIStudio --icon "$PSScriptRoot/web/brand/luminaria.ico" --add-data "$PSScriptRoot/VERSION;." --add-data "$PSScriptRoot/web;web" --add-data "$PSScriptRoot/skills;skills" --add-data "$PSScriptRoot/runtime/llama-swap.exe;runtime" --add-data "$PSScriptRoot/backend/research.py;backend" --collect-all webview --collect-submodules langgraph --collect-submodules mcp.client --collect-all faster_whisper --collect-all ctranslate2 --collect-all piper --collect-all onnxruntime --collect-all av --exclude-module matplotlib --exclude-module pandas --exclude-module scipy --exclude-module tkinter --exclude-module IPython desktop.py
if($LASTEXITCODE){throw 'Executable build failed'}
& "$PSScriptRoot\runtime\inno\ISCC.exe" "/DAppVersion=$version" installer.iss
if($LASTEXITCODE){throw 'Installer build failed'}
$asset=Get-Item "release/Luminaria-$version-Setup.exe"
$hash=(Get-FileHash $asset.FullName -Algorithm SHA256).Hash.ToLower()
"$hash  $($asset.Name)" | Set-Content release/SHA256SUMS.txt -Encoding ascii
