$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$version=(Get-Content "$PSScriptRoot/VERSION" -Raw).Trim()
if($version -notmatch '^\d+\.\d+\.\d+$'){throw "VERSION must look like 1.2.3"}
$python=if($env:STUDIO_BUILD_PYTHON){$env:STUDIO_BUILD_PYTHON}elseif(Test-Path "$PSScriptRoot/runtime/local-ai/agent-tools/python-env/Scripts/python.exe"){"$PSScriptRoot/runtime/local-ai/agent-tools/python-env/Scripts/python.exe"}else{(Get-Command python -ErrorAction Stop).Source}
if(!(Test-Path "$PSScriptRoot/runtime/local-ai/runtime-vulkan/llama-server.exe")){throw 'Bundled model runtime is missing'}
# Windows file details (Properties > Details, Task Manager): publisher, product name and version.
$publisher='Desselle Solution Software'
$parts=($version.Split('.')|ForEach-Object{[int]$_})+@(0)
$tuple=($parts[0..3] -join ', ')
New-Item -ItemType Directory -Force -Path .build | Out-Null
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($tuple), prodvers=($tuple), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '$publisher'),
      StringStruct('FileDescription', 'Luminaria'),
      StringStruct('FileVersion', '$version'),
      StringStruct('InternalName', 'LocalAIStudio'),
      StringStruct('LegalCopyright', 'Copyright (C) 2026 $publisher'),
      StringStruct('OriginalFilename', 'LocalAIStudio.exe'),
      StringStruct('ProductName', 'Luminaria'),
      StringStruct('ProductVersion', '$version')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content .build/version-info.txt -Encoding ascii
& $python -m PyInstaller --noconfirm --clean --workpath .build/work --distpath .build/dist --specpath .build --windowed --onedir --name LocalAIStudio --icon "$PSScriptRoot/web/brand/luminaria.ico" --version-file "$PSScriptRoot/.build/version-info.txt" --add-data "$PSScriptRoot/VERSION;." --add-data "$PSScriptRoot/web;web" --add-data "$PSScriptRoot/skills;skills" --add-data "$PSScriptRoot/runtime/llama-swap.exe;runtime" --add-data "$PSScriptRoot/runtime/local-ai/runtime-vulkan;runtime/local-ai/runtime-vulkan" --collect-all webview --collect-submodules langgraph --collect-submodules mcp.client --collect-submodules ddgs --collect-all primp --hidden-import bs4 --hidden-import pypdf --collect-all faster_whisper --collect-all ctranslate2 --collect-all piper --collect-all onnxruntime --collect-all av --exclude-module matplotlib --exclude-module pandas --exclude-module scipy --exclude-module IPython desktop.py
if($LASTEXITCODE){throw 'Executable build failed'}
& "$PSScriptRoot\runtime\inno\ISCC.exe" "/DAppVersion=$version" installer.iss
if($LASTEXITCODE){throw 'Installer build failed'}
$asset=Get-Item "release/Luminaria-$version-Setup.exe"
$hash=(Get-FileHash $asset.FullName -Algorithm SHA256).Hash.ToLower()
"$hash  $($asset.Name)" | Set-Content release/SHA256SUMS.txt -Encoding ascii
