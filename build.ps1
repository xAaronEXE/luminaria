$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$version=(Get-Content "$PSScriptRoot/VERSION" -Raw).Trim()
if($version -notmatch '^\d+\.\d+\.\d+$'){throw "VERSION must look like 1.2.3"}
# Code signing is optional. Without a certificate the build stays unsigned and Windows SmartScreen will warn.
#   PFX file:                set LUMINARIA_SIGN_PFX (path) and LUMINARIA_SIGN_PASSWORD
#   Trusted Signing / other: set LUMINARIA_SIGN_ARGS to the signtool arguments before the file name
$signtool=$env:LUMINARIA_SIGNTOOL
if(!$signtool){$signtool=(Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue|Sort-Object FullName -Descending|Select-Object -First 1).FullName}
function Sign-File($path){
  $signing=$env:LUMINARIA_SIGN_PFX -or $env:LUMINARIA_SIGN_ARGS
  if(!$signing){Write-Host "Not signing $(Split-Path $path -Leaf): no certificate configured."; return}
  if(!$signtool -or !(Test-Path $signtool)){throw 'A signing certificate is configured but signtool.exe was not found. Install the Windows SDK or set LUMINARIA_SIGNTOOL.'}
  if($env:LUMINARIA_SIGN_PFX){& $signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f $env:LUMINARIA_SIGN_PFX /p $env:LUMINARIA_SIGN_PASSWORD /d 'Luminaria' $path}
  else{& $signtool sign ($env:LUMINARIA_SIGN_ARGS -split ' ') $path}
  if($LASTEXITCODE){throw "Signing failed for $path"}
  & $signtool verify /pa $path | Out-Null
  if($LASTEXITCODE){throw "Signature on $path did not verify"}
  Write-Host "Signed $(Split-Path $path -Leaf)"
}
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
Sign-File "$PSScriptRoot/.build/dist/LocalAIStudio/LocalAIStudio.exe"
& "$PSScriptRoot\runtime\inno\ISCC.exe" "/DAppVersion=$version" installer.iss
if($LASTEXITCODE){throw 'Installer build failed'}
Sign-File "$PSScriptRoot/release/Luminaria-$version-Setup.exe"
$asset=Get-Item "release/Luminaria-$version-Setup.exe"
$hash=(Get-FileHash $asset.FullName -Algorithm SHA256).Hash.ToLower()
"$hash  $($asset.Name)" | Set-Content release/SHA256SUMS.txt -Encoding ascii
