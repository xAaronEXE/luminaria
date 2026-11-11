#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-f0-9]{32}$')]
    [string]$AccountId
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$configPath = Join-Path $PSScriptRoot 'wrangler.private-sync.local.jsonc'
if (Test-Path -LiteralPath $configPath) {
    throw 'A private sync configuration already exists. Follow the private sync guide to resume or update that deployment.'
}
$name = 'luminaria-sync-' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
if (-not $PSCmdlet.ShouldProcess("Cloudflare account $AccountId", "Create a Worker, D1 database, and private R2 bucket named $name")) {
    return
}

$node = (Get-Command node -CommandType Application | Select-Object -First 1).Source
$wrangler = Join-Path $PSScriptRoot 'node_modules/wrangler/bin/wrangler.js'
if (-not (Test-Path -LiteralPath $wrangler)) {
    throw 'Run npm ci in auth-service to install the pinned Wrangler version.'
}
$config = [ordered]@{
    name = $name
    account_id = $AccountId
    main = 'src/private_sync.js'
    compatibility_date = '2026-10-16'
    workers_dev = $true
    preview_urls = $false
    vars = @{ SYNC_ENABLED = 'true' }
}
function Save-WorkerConfig {
    $config | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $configPath -Encoding utf8
}
function Invoke-Wrangler {
    param([string[]]$Arguments)
    & $node $wrangler @Arguments --config $configPath
    if ($LASTEXITCODE -ne 0) {
        throw "Wrangler failed during $($Arguments -join ' '). See PRIVATE-SYNC.md to resume with the generated configuration."
    }
}

Save-WorkerConfig
Write-Host 'Cloudflare is a separate company. R2 needs a subscription and a payment method. Account usage can incur charges.'
Invoke-Wrangler -Arguments @('d1', 'create', $name) | Out-Host
$databases = (Invoke-Wrangler -Arguments @('d1', 'list', '--json') | Out-String) | ConvertFrom-Json
$database = @($databases | Where-Object name -EQ $name)
if ($database.Count -ne 1 -or $database[0].uuid -notmatch '^[a-f0-9-]{36}$') {
    throw "Could not confirm the D1 ID for $name. See PRIVATE-SYNC.md."
}
$config.d1_databases = @(@{ binding = 'DB'; database_name = $name; database_id = $database[0].uuid })
$config.r2_buckets = @(@{ binding = 'SYNC_BUCKET'; bucket_name = $name })
Save-WorkerConfig
Invoke-Wrangler -Arguments @('r2', 'bucket', 'create', $name) | Out-Host
Invoke-Wrangler -Arguments @('d1', 'execute', $name, '--remote', '--file', 'migrations/0005_cloud_sync.sql') | Out-Host
$deployment = Invoke-Wrangler -Arguments @('deploy')
$deployment | Out-Host

$key = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant()
$hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::ASCII.GetBytes($key))).ToLowerInvariant()
ConvertTo-Json -InputObject @($hash) -Compress | & $node $wrangler secret put SYNC_DEVICE_KEY_HASHES --config $configPath
if ($LASTEXITCODE -ne 0) {
    throw 'The Worker refused the device-key configuration. Follow the manual key steps in PRIVATE-SYNC.md.'
}
Write-Host 'Enter the Worker URL printed by Wrangler and this device key in Settings → Cloud sync.'
Write-Host $key
