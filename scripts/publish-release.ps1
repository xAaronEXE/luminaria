[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Repository,
    [Parameter(Mandatory)][string]$Report,
    [Parameter(Mandatory)][string]$BaselineInstaller
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$version = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'VERSION must look like 1.2.3.' }
$installer = Join-Path $root "release/Luminaria-$version-Setup.exe"
$checksums = Join-Path $root 'release/SHA256SUMS.txt'
$notes = Join-Path $root "docs/release-notes/$version.md"
$null = Get-Item -LiteralPath $installer, $checksums, $notes
if (([string](Get-Item -LiteralPath $installer).VersionInfo.ProductVersion).Trim() -ne $version) {
    throw 'Installer version does not match VERSION.'
}
& "$PSScriptRoot/verify-release-comparison.ps1" -Report $Report -BaselineInstaller $BaselineInstaller -CandidateInstaller $installer
$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
$expected = "$hash  Luminaria-$version-Setup.exe"
if ((Get-Content -LiteralPath $checksums -Raw).Trim() -ne $expected) {
    throw 'The published checksum must match the verified installer.'
}
$target = & git -C $root rev-parse HEAD
if ($LASTEXITCODE -or $target -notmatch '^[a-f0-9]{40}$') { throw 'Cannot resolve the release commit.' }
$trackedChanges = & git -C $root status --porcelain --untracked-files=no
if ($LASTEXITCODE -or $trackedChanges) { throw 'Commit the release source before publishing.' }
if ($PSCmdlet.ShouldProcess("$Repository at $target", "Publish Luminaria $version")) {
    & gh release create "v$version" $installer $checksums --repo $Repository --target $target --title "Luminaria $version" --notes-file $notes
    if ($LASTEXITCODE) { throw 'GitHub release creation failed.' }
}
