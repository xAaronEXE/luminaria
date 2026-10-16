$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$python=if($env:STUDIO_BUILD_PYTHON){$env:STUDIO_BUILD_PYTHON}else{(Get-Command python -ErrorAction Stop).Source}
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name LocalAIStudio --icon runtime/mint.ico --add-data 'web;web' --add-data 'skills;skills' --add-data 'runtime/llama-swap.exe;runtime' --add-data 'backend/research.py;backend' --collect-all webview --collect-submodules langgraph --collect-submodules mcp.client --collect-all faster_whisper --collect-all ctranslate2 --collect-all piper --collect-all onnxruntime --collect-all av --exclude-module matplotlib --exclude-module pandas --exclude-module scipy --exclude-module tkinter --exclude-module IPython desktop.py
if($LASTEXITCODE){throw 'Executable build failed'}
& "$PSScriptRoot\runtime\inno\ISCC.exe" installer.iss
if($LASTEXITCODE){throw 'Installer build failed'}
$asset=Get-Item release/Luminaria-0.2.0-Setup.exe
$hash=(Get-FileHash $asset.FullName -Algorithm SHA256).Hash.ToLower()
"$hash  $($asset.Name)" | Set-Content release/SHA256SUMS.txt -Encoding ascii
