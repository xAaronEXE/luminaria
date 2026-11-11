@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1

findstr /x /c:"0.4.0" VERSION >nul
if errorlevel 1 (
  echo Set VERSION to 0.4.0 after the roadmap and live acceptance checks are complete.
  popd
  exit /b 1
)

if not exist "data" mkdir "data"
set "LOG=%CD%\data\release-0.4.0.log"
echo Testing and building Luminaria 0.4.0. See "%LOG%" for details.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run-tests.ps1" >"%LOG%" 2>&1
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -File "build.ps1" >>"%LOG%" 2>&1
if errorlevel 1 goto failed
if not exist "release\Luminaria-0.4.0-Setup.exe" goto failed
if not exist "release\SHA256SUMS.txt" goto failed
echo Installer and checksums are ready in the release folder.
popd
exit /b 0

:failed
echo The release build stopped. See "%LOG%" and "data\test-report.txt".
popd
exit /b 1
