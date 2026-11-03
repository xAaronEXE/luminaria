# Builds runtime/agent-tools: a portable Python and Node.js with the browser, Windows and
# document tools, so the installed app needs nothing else on the user's PC.
# Run once before build.ps1 (build.ps1 runs it automatically when the folder is missing).
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$root=Split-Path $PSScriptRoot -Parent
$spec=Join-Path $PSScriptRoot 'agent-tools'
$out=Join-Path $root 'runtime/agent-tools'
$work=Join-Path $root 'runtime/agent-tools.partial'
$cache=Join-Path $root 'runtime/downloads'
$prereqs=Join-Path $root 'runtime/prereqs'

$pythonVersion='3.14.10'
$pythonZip="python-$pythonVersion-embed-amd64.zip"
$pythonSha='90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
$nodeVersion='v24.22.2'
$nodeZip="node-$nodeVersion-win-x64.zip"

function Get-Verified($url,$file,$sha){
  $path=Join-Path $cache $file
  if(!(Test-Path $path)){Write-Host "Downloading $file";Invoke-WebRequest $url -OutFile "$path.part";Move-Item -Force "$path.part" $path}
  $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
  if($actual -ne $sha.ToLower()){Remove-Item -Force $path;throw "Checksum mismatch for $file; download removed"}
  return $path
}
function Assert-Signed($path,$publisher){
  $sig=Get-AuthenticodeSignature -LiteralPath $path
  if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch $publisher){throw "$path is not validly signed by $publisher"}
}

New-Item -ItemType Directory -Force $cache,$prereqs | Out-Null
if(Test-Path $work){Remove-Item -Recurse -Force $work}
New-Item -ItemType Directory -Force $work | Out-Null

# Python (official embeddable build, pinned checksum)
$py=Get-Verified "https://www.python.org/ftp/python/$pythonVersion/$pythonZip" $pythonZip $pythonSha
Expand-Archive -LiteralPath $py -DestinationPath "$work/python" -Force
Assert-Signed "$work/python/python.exe" 'Python Software Foundation'
$pth=Get-ChildItem "$work/python" -Filter 'python*._pth' | Select-Object -First 1
$lines=(Get-Content $pth.FullName) -replace '^#\s*import site','import site'
if($lines -notcontains 'Lib\site-packages'){$lines=@($lines[0],'Lib\site-packages')+$lines[1..($lines.Count-1)]}
if($lines -notcontains 'import site'){$lines+='import site'}
Set-Content -LiteralPath $pth.FullName -Value $lines -Encoding ascii
$site="$work/python/Lib/site-packages"; New-Item -ItemType Directory -Force $site | Out-Null

# Install packages with a matching Python 3.14 on the build PC (same version as the embedded one)
$builder=$null
foreach($candidate in @(,@('py','-3.14')) + @(,@('python')) + @(,@("$root/runtime/local-ai/agent-tools/python-env/Scripts/python.exe"))){
  $exe=$candidate[0]; $pre=@($candidate | Select-Object -Skip 1)
  if(!(Get-Command $exe -ErrorAction SilentlyContinue)){continue}
  $v=(& $exe @pre -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null)
  if("$v".Trim() -eq '3.14'){$builder=$candidate;break}
}
if(!$builder){throw 'Python 3.14 is needed on the build PC to prepare the built-in Python packages'}
$bexe=$builder[0]; $bargs=@($builder|Select-Object -Skip 1)
& $bexe @bargs -m pip install --disable-pip-version-check --no-warn-script-location --target $site -r "$spec/requirements.txt"
if($LASTEXITCODE){throw 'Installing Python packages failed'}
# Command-line tools from packages (uv, uvx, pip) go where Windows expects them
New-Item -ItemType Directory -Force "$work/python/Scripts" | Out-Null
if(Test-Path "$site/bin"){Get-ChildItem "$site/bin" -File | Move-Item -Destination "$work/python/Scripts" -Force; Remove-Item -Recurse -Force "$site/bin"}
if(!(Test-Path "$work/python/Scripts/uvx.exe")){throw 'uv was not installed; Python connectors would not start'}
# pip's launchers point at the build PC's Python; Luminaria runs pip as `python -m pip` with the built-in Python instead.
Get-ChildItem "$work/python/Scripts" -Filter 'pip*.exe' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $site -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

# Node.js (official build, checked against nodejs.org checksums and its Authenticode signature)
$sums=(Invoke-WebRequest "https://nodejs.org/dist/$nodeVersion/SHASUMS256.txt" -UseBasicParsing).Content
$line=($sums -split "`n" | ForEach-Object {$_.Trim()} | Where-Object {$_ -match "\s$([regex]::Escape($nodeZip))$"} | Select-Object -First 1)
if(!$line){throw "No published checksum for $nodeZip"}
$node=Get-Verified "https://nodejs.org/dist/$nodeVersion/$nodeZip" $nodeZip (($line -split '\s+')[0])
Expand-Archive -LiteralPath $node -DestinationPath $work -Force
Rename-Item (Join-Path $work ($nodeZip -replace '\.zip$','')) 'node'
Assert-Signed "$work/node/node.exe" 'OpenJS Foundation'

# Browser connector (exact versions from package-lock.json, no install scripts)
Copy-Item "$spec/package.json","$spec/package-lock.json" $work
Push-Location $work
try{& "$work/node/node.exe" "$work/node/node_modules/npm/bin/npm-cli.js" ci --ignore-scripts --no-audit --no-fund --omit=dev; if($LASTEXITCODE){throw 'Installing the browser connector failed'}}
finally{Pop-Location}

# Self-test with the portable copies only
$env:PATH="$work/python;$work/node;$env:SystemRoot\System32;$env:SystemRoot"
& "$work/python/python.exe" -c "import docx,pptx,openpyxl,xlsxwriter,reportlab,pypdf,fitz,matplotlib,pandas,PIL,bs4,requests,win32api,windows_mcp;print('python ok')"
if($LASTEXITCODE){throw 'Built-in Python self-test failed'}
& "$work/node/node.exe" "$work/node_modules/@playwright/mcp/cli.js" --help | Out-Null
if($LASTEXITCODE){throw 'Browser connector self-test failed'}
& "$work/python/Scripts/uv.exe" --version
if($LASTEXITCODE){throw 'uv self-test failed'}

if(Test-Path $out){Remove-Item -Recurse -Force $out}
Move-Item $work $out

# WebView2 (draws the app window). Windows 11 has it; some Windows 10 PCs do not.
$wv="$prereqs/MicrosoftEdgeWebview2Setup.exe"
Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $wv
Assert-Signed $wv 'Microsoft Corporation'

$size=[math]::Round(((Get-ChildItem $out -Recurse -File | Measure-Object Length -Sum).Sum)/1MB)
Write-Host "Built-in tools ready: Python $pythonVersion, Node $nodeVersion, $size MB"
