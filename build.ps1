# Build portable WindowsCleaner.exe (no Python needed for end users)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing build dependencies..."
python -m pip install -r requirements.txt pyinstaller -q

Write-Host "Building WindowsCleaner.exe ..."
python -m PyInstaller --noconfirm --clean windowscleaner.spec

$exe = Join-Path $PSScriptRoot "dist\WindowsCleaner.exe"
if (-not (Test-Path $exe)) { throw "Build failed: $exe not found" }

$zip = Join-Path $PSScriptRoot "dist\WindowsCleaner-portable.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $exe -DestinationPath $zip -Force

Write-Host ""
Write-Host "Done. Share either:"
Write-Host "  $exe"
Write-Host "  $zip"
Write-Host ""
Write-Host "End users: extract/run WindowsCleaner.exe - no Python required."
Write-Host "For privacy/services cleanup: use Restart as Administrator (UAC)."
