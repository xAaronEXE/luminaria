# Publishes the built installer to the private GitHub repository's Releases.
# The update service reads the latest non-draft release; desktop apps never see the repository.
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$version=(Get-Content "$PSScriptRoot/VERSION" -Raw).Trim()
$name="Luminaria-$version-Setup.exe"
$installer="release/$name"
$sums='release/SHA256SUMS.txt'
$notes="docs/release-notes/$version.md"
foreach($file in $installer,$sums,$notes){if(-not(Test-Path $file)){throw "Missing $file. Run build.ps1 and write the release notes first."}}
$hash=(Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()
if(-not(Select-String -Path $sums -SimpleMatch "$hash  $name" -Quiet)){throw 'SHA256SUMS.txt does not match the installer. Run build.ps1 again.'}
gh release create "v$version" $installer $sums --repo xAaronEXE/luminaria --target main --title "Luminaria $version" --notes-file $notes
if($LASTEXITCODE){throw 'Release publishing failed'}
