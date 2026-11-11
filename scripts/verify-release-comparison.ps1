param(
    [Parameter(Mandatory)][string]$Report,
    [Parameter(Mandatory)][string]$BaselineInstaller,
    [Parameter(Mandatory)][string]$CandidateInstaller
)

$ErrorActionPreference = 'Stop'
$comparison = Get-Content -LiteralPath $Report -Raw | ConvertFrom-Json
$versions = foreach ($installer in @($BaselineInstaller, $CandidateInstaller)) {
    $file = Get-Item -LiteralPath $installer
    $version = ([string]$file.VersionInfo.ProductVersion).Trim()
    if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid installer version in $($file.Name)." }
    $property = $comparison.installer_sha256.PSObject.Properties[$version]
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if (!$property -or $property.Value -ne $hash) {
        throw "The comparison report does not match the exact $version installer."
    }
    $version
}
$baseline, $candidate = $versions
if ([version]$candidate -le [version]$baseline) { throw 'The candidate must be newer than the baseline.' }
$cases = @($comparison.cases.PSObject.Properties)
if ($cases.Count -ne 10) { throw 'The comparison must contain ten acceptance cases.' }
$baselinePassed = 0
$candidatePassed = 0
$seen = @{}
foreach ($case in $cases) {
    if ($case.Name -notmatch '^(0[1-9]|10)\s+' -or $seen.ContainsKey($Matches[1])) {
        throw "Unexpected or duplicate acceptance case $($case.Name)."
    }
    $seen[$Matches[1]] = $true
    $before = $case.Value.PSObject.Properties[$baseline].Value.status
    $after = $case.Value.PSObject.Properties[$candidate].Value.status
    if ($before -notin @('PASS','FAIL') -or $after -notin @('PASS','FAIL')) {
        throw "Acceptance case $($case.Name) needs a verdict for both installers."
    }
    if ($before -eq 'PASS') { $baselinePassed++ }
    if ($after -eq 'PASS') { $candidatePassed++ }
}
if ($candidatePassed -lt $baselinePassed) {
    throw "Acceptance regressed from $baselinePassed/10 to $candidatePassed/10."
}
Write-Output "Verified exact installers. Acceptance passed $baselinePassed/10 on $baseline and $candidatePassed/10 on $candidate."
