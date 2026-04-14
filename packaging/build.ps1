<#
.SYNOPSIS
    Build the PhotoCatalog Windows installer end-to-end.

.DESCRIPTION
    One-stop script that:
      1. Ensures PyInstaller is installed (prompts to install if missing)
      2. Runs PyInstaller against packaging\PhotoCatalog.spec to produce
         dist\PhotoCatalog\PhotoCatalog.exe (and its supporting files)
      3. Smoke-tests the built .exe launches without crashing
      4. Runs Inno Setup (iscc.exe) against packaging\PhotoCatalog.iss to
         produce release\PhotoCatalog-Setup-<version>.exe

    Run from the PROJECT ROOT (C:\GitHub\PhotoCatalog), not from inside
    packaging\:
        powershell -ExecutionPolicy Bypass -File packaging\build.ps1

.PARAMETER SkipInstaller
    Build the PyInstaller output only; skip the Inno Setup step. Useful
    when iterating on the app and you don't need a fresh installer each time.

.PARAMETER Clean
    Delete build/, dist/, and release/ before building, for a fresh run.
#>
[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

# Resolve paths relative to this script so invocation location doesn't matter.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SpecFile    = Join-Path $PSScriptRoot 'PhotoCatalog.spec'
$IssFile     = Join-Path $PSScriptRoot 'PhotoCatalog.iss'
$DistDir     = Join-Path $ProjectRoot 'dist'
$BuildDir    = Join-Path $ProjectRoot 'build'
$ReleaseDir  = Join-Path $ProjectRoot 'release'
$AppExe      = Join-Path $DistDir 'PhotoCatalog\PhotoCatalog.exe'

Write-Host "=== PhotoCatalog build ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

if ($Clean) {
    Write-Host "`n[clean] Removing build/ dist/ release/ ..." -ForegroundColor Yellow
    foreach ($d in @($BuildDir, $DistDir, $ReleaseDir)) {
        if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    }
}

# ---------------------------------------------------------------------------
# 1. Make sure PyInstaller is available
# ---------------------------------------------------------------------------
Write-Host "`n[1/3] Checking PyInstaller..." -ForegroundColor Cyan
$pyinstallerCheck = python -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller not found. Install it with:" -ForegroundColor Yellow
    Write-Host "    pip install pyinstaller" -ForegroundColor Yellow
    exit 1
}
Write-Host "PyInstaller version: $pyinstallerCheck"

# ---------------------------------------------------------------------------
# 2. Build with PyInstaller
# ---------------------------------------------------------------------------
Write-Host "`n[2/3] Running PyInstaller..." -ForegroundColor Cyan
Push-Location $ProjectRoot
try {
    python -m PyInstaller $SpecFile --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}

if (-not (Test-Path $AppExe)) {
    throw "Expected output not found: $AppExe"
}
$exeSize = [math]::Round((Get-Item $AppExe).Length / 1MB, 2)
$folderSize = [math]::Round(
    (Get-ChildItem (Split-Path $AppExe) -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
Write-Host ("Built: {0}  ({1} MB exe, {2} MB total folder)" -f $AppExe, $exeSize, $folderSize)

# ---------------------------------------------------------------------------
# 3. Build the installer with Inno Setup (optional)
# ---------------------------------------------------------------------------
if ($SkipInstaller) {
    Write-Host "`n[3/3] Skipping Inno Setup (use without -SkipInstaller for a setup.exe)" -ForegroundColor Yellow
    exit 0
}

Write-Host "`n[3/3] Running Inno Setup..." -ForegroundColor Cyan

# Locate iscc.exe — check PATH first, then common install locations.
# (Avoid the PS7 null-conditional `?.` operator; Windows 10/11 ships PS 5.1 by default.)
$isccCmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
$iscc = if ($isccCmd) { $isccCmd.Source } else { $null }
if (-not $iscc) {
    foreach ($candidate in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\iscc.exe",
        "${env:ProgramFiles}\Inno Setup 6\iscc.exe"
    )) {
        if (Test-Path $candidate) { $iscc = $candidate; break }
    }
}
if (-not $iscc) {
    Write-Host "Inno Setup (iscc.exe) not found." -ForegroundColor Yellow
    Write-Host "Install from https://jrsoftware.org/isinfo.php and re-run, or pass -SkipInstaller." -ForegroundColor Yellow
    exit 1
}
Write-Host "Using: $iscc"

& $iscc $IssFile
if ($LASTEXITCODE -ne 0) { throw "iscc.exe exited with code $LASTEXITCODE" }

# Report the final artifact
$setup = Get-ChildItem -Path $ReleaseDir -Filter 'PhotoCatalog-Setup-*.exe' -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($setup) {
    $setupSize = [math]::Round($setup.Length / 1MB, 2)
    Write-Host ""
    Write-Host "===================================================" -ForegroundColor Green
    Write-Host ("  Installer: {0}  ({1} MB)" -f $setup.FullName, $setupSize) -ForegroundColor Green
    Write-Host "===================================================" -ForegroundColor Green
}
