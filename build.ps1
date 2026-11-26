# Publish a self-contained WindowsCleaner.exe (no separate .NET install for the recipient).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$out = Join-Path $PSScriptRoot "dist"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }

dotnet publish "src\WindowsCleaner.App\WindowsCleaner.App.csproj" `
    -c Release -r win-x64 --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $out

$exe = Join-Path $out "WindowsCleaner.exe"
if (-not (Test-Path $exe)) { throw "Build failed: $exe not found" }

$zip = Join-Path $out "WindowsCleaner-portable.zip"
Compress-Archive -Path $exe -DestinationPath $zip -Force

Write-Host ""
Write-Host "Done. Share either:"
Write-Host "  $exe"
Write-Host "  $zip"
Write-Host "End users run WindowsCleaner.exe. For privacy, services, and bloat: Restart as Administrator."
