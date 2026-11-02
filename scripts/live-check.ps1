# Live checks against the running Luminaria app and the public catalogs it uses.
# Open Luminaria first. Writes a PASS/FAIL report next to this script's caller (data\live-check-report.txt).
param([string]$Report="$PSScriptRoot\..\data\live-check-report.txt",[int]$Port=3210)
$ErrorActionPreference='Continue'
$lines=New-Object System.Collections.Generic.List[string]
function Log($status,$name,$detail=''){ $lines.Add(("{0,-5} {1}  {2}" -f $status,$name,$detail)); Write-Host ("{0,-5} {1}  {2}" -f $status,$name,$detail) }
function Http($method,$url,$headers=@{},$body=$null){
  try{
    $p=@{Uri=$url;Method=$method;Headers=$headers;UseBasicParsing=$true;TimeoutSec=40}
    if($body -ne $null){$p.Body=($body|ConvertTo-Json -Compress);$p.ContentType='application/json'}
    $r=Invoke-WebRequest @p
    return @{status=[int]$r.StatusCode;text=$r.Content}
  }catch{
    $code=0;$text=$_.Exception.Message
    if($_.Exception.Response){$code=[int]$_.Exception.Response.StatusCode;try{$sr=New-Object IO.StreamReader($_.Exception.Response.GetResponseStream());$text=$sr.ReadToEnd()}catch{}}
    return @{status=$code;text=$text}
  }
}
function Json($r){ try{$r.text|ConvertFrom-Json}catch{$null} }
$base="http://127.0.0.1:$Port"
$lines.Add("Luminaria live check  $(Get-Date -Format s)")

# 1. App is running
$b=Http GET "$base/api/bootstrap"
if($b.status -ne 200){ Log FAIL 'app reachable' "Open Luminaria first ($($b.text))"; $lines|Set-Content $Report -Encoding utf8; exit 1 }
$boot=Json $b; $h=@{'X-Studio-Token'=$boot.token}
Log PASS 'app reachable' "version $($boot.version)"

# 2. Guards
$r=Http GET "$base/api/settings"
if($r.status -eq 403){Log PASS 'token required' 'request without token refused'}else{Log FAIL 'token required' "status $($r.status)"}
$s=Json (Http GET "$base/api/settings" $h)
if($s){ Log PASS 'settings load' "access=$($s.access_status.active) workspace_problem=[$($s.workspace_problem)]" } else { Log FAIL 'settings load' '' }
$r=Http POST "$base/api/open-external" $h @{url='http://127.0.0.1:3210/'}
if($r.status -eq 400){Log PASS 'open-external refuses loopback'}else{Log FAIL 'open-external refuses loopback' "status $($r.status)"}
$r=Http POST "$base/api/open-external" $h @{url='file:///C:/Windows/win.ini'}
if($r.status -eq 400){Log PASS 'open-external refuses file://'}else{Log FAIL 'open-external refuses file://' "status $($r.status)"}
$r=Http GET "$base/api/file?path=C%3A%5CWindows%5Cwin.ini" $h
if($r.status -ne 200 -or $r.text -notmatch 'fonts|extensions|files'){Log PASS 'file preview refuses Windows folder'}else{Log FAIL 'file preview refuses Windows folder' 'read win.ini'}
$r=Http POST "$base/api/marketplace/mcp/install" $h @{id='io.github.example/none'}
if($r.status -eq 400){Log PASS 'connector install needs confirmation'}else{Log FAIL 'connector install needs confirmation' "status $($r.status)"}

# 3. Public catalogs, reached from this PC
$r=Http GET 'https://registry.modelcontextprotocol.io/v0/servers?limit=3'
if($r.status -eq 200){Log PASS 'MCP Registry reachable' (($r.text).Substring(0,[Math]::Min(120,$r.text.Length)))}else{Log FAIL 'MCP Registry reachable' "status $($r.status)"}
$r=Http GET 'https://api.github.com/repos/anthropics/skills/git/trees/HEAD?recursive=1' @{'User-Agent'='Luminaria'}
if($r.status -eq 200){Log PASS 'GitHub skills tree reachable' "$((Json $r).tree.Count) entries"}else{Log FAIL 'GitHub skills tree reachable' "status $($r.status) $($r.text.Substring(0,[Math]::Min(120,$r.text.Length)))"}

# 4. Marketplace through the app
$m=Http GET "$base/api/marketplace/skills?q=" $h
$mj=Json $m
if($m.status -eq 200 -and $mj.items.Count -gt 0){Log PASS 'marketplace skills' "$($mj.total) skills; errors=[$($mj.errors -join '; ')]"}else{Log FAIL 'marketplace skills' "status $($m.status) $($m.text.Substring(0,[Math]::Min(200,$m.text.Length)))"}
$m=Http GET "$base/api/marketplace/mcp?q=" $h
$mj=Json $m
if($m.status -eq 200 -and $mj.items.Count -gt 0){
  $ok=($mj.items|Where-Object installable).Count
  Log PASS 'marketplace connectors' "$($mj.items.Count) on first page, $ok installable, next=$([bool]$mj.next)"
  $sample=$mj.items|Select-Object -First 1
  Log INFO 'sample connector' "$($sample.title) | packages=$($sample.packages.Count) remotes=$($sample.remotes.Count)"
}else{Log FAIL 'marketplace connectors' "status $($m.status) $($m.text.Substring(0,[Math]::Min(200,$m.text.Length)))"}
$m=Http GET "$base/api/marketplace/mcp?q=github" $h
if($m.status -eq 200){Log PASS 'marketplace search' "$((Json $m).items.Count) results for 'github'"}else{Log FAIL 'marketplace search' "status $($m.status)"}

# 5. Model server and tools
if($s){
  $mr=Http GET "$base/api/model/status" $h; $mst=Json $mr
  if($mst.connected){Log PASS 'model server' "model=$($mst.model) loaded=$($mst.loaded)"}else{Log WARN 'model server' "not connected: $($mst.error)"}
  $tl=Http GET "$base/api/tools" $h
  Log INFO 'tools' "status $($tl.status)"
}

# 6. Update channel
$u=Http GET "$base/api/updates" $h
if($u.status -eq 200){Log PASS 'update check' ((Json $u).message)}else{Log WARN 'update check' "status $($u.status)"}

# 7. Install facts
$exe=Get-ChildItem "$env:USERPROFILE\Desktop\Luminaria\App" -Filter 'LocalAIStudio.exe' -ErrorAction SilentlyContinue|Select-Object -First 1
if($exe){
  $sig=Get-AuthenticodeSignature $exe.FullName
  Log INFO 'installed exe' "$($exe.FullName) version=$($exe.VersionInfo.FileVersion) publisher=$($exe.VersionInfo.CompanyName) signature=$($sig.Status)"
}else{Log WARN 'installed exe' 'not found on Desktop\Luminaria\App'}

$lines|Set-Content $Report -Encoding utf8
Write-Host "`nReport written to $Report"
