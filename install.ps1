[CmdletBinding()]
param(
    [string]$AccountId,
    [string]$ApiToken,
    [string]$WorkerName = "ai-gateway",
    [switch]$SkipService,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "          451bypass -- Automated Installer and Setup           " -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[*] Checking environment..." -ForegroundColor Yellow

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $PythonCmd) {
    Write-Host "[-] Python is not installed or not found in system PATH." -ForegroundColor Red
    Write-Host "    Please install Python 3.8+ from https://www.python.org/ or Microsoft Store." -ForegroundColor Yellow
    exit 1
}

$PyVer = (& $PythonCmd.Source --version 2>&1)
Write-Host "[+] Found $PyVer ($($PythonCmd.Source))" -ForegroundColor Green

$InstallDir = Join-Path $env:LOCALAPPDATA "451bypass"
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$CurrentDir = $PSScriptRoot
if (-not $CurrentDir) {
    $CurrentDir = (Get-Location).Path
}

Write-Host "[*] Installing 451bypass into: $InstallDir" -ForegroundColor Yellow

$PackageSrc = Join-Path $CurrentDir "bypass451"
if (Test-Path $PackageSrc) {
    Copy-Item -Path $PackageSrc -Destination $InstallDir -Recurse -Force
}

$DomainsSrc = Join-Path $CurrentDir "domains"
if (Test-Path $DomainsSrc) {
    Copy-Item -Path $DomainsSrc -Destination $InstallDir -Recurse -Force
}

$UnScript = Join-Path $CurrentDir "uninstall.ps1"
if (Test-Path $UnScript) {
    Copy-Item -Path $UnScript -Destination $InstallDir -Force
}

$CmdContent = "@echo off`r`nset `"PYTHONPATH=%~dp0;%PYTHONPATH%`"`r`n`"$($PythonCmd.Source)`" -m bypass451 %*"
Set-Content -Path (Join-Path $InstallDir "451b.cmd") -Value $CmdContent -Encoding ASCII
Set-Content -Path (Join-Path $CurrentDir "451b.cmd") -Value $CmdContent -Encoding ASCII

Write-Host "[+] Core files installed successfully." -ForegroundColor Green

Write-Host "[*] Checking PATH environment variable..." -ForegroundColor Yellow
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $UserPath) { $UserPath = "" }

if ($UserPath -notlike "*$InstallDir*") {
    $NewPath = if ($UserPath.Trim().Length -gt 0) { "$UserPath;$InstallDir" } else { $InstallDir }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "[+] Added $InstallDir to User PATH." -ForegroundColor Green
} else {
    Write-Host "[+] $InstallDir is already in User PATH." -ForegroundColor Green
}

if ($env:Path -notlike "*$InstallDir*") {
    $env:Path = "$env:Path;$InstallDir"
}

$ConfigFile = Join-Path $InstallDir "config.json"
$ExistingAcc = ""
$ExistingTok = ""
$ExistingSub = ""

if (Test-Path $ConfigFile) {
    try {
        $Json = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        $ExistingAcc = $Json.account_id
        $ExistingTok = $Json.api_token
        $ExistingSub = $Json.subdomain
    } catch {}
}

if ($AccountId) { $ExistingAcc = $AccountId.Trim() }
if ($ApiToken) { $ExistingTok = $ApiToken.Trim() }

if (-not $ExistingAcc -or -not $ExistingTok) {
    if ($NonInteractive) {
        Write-Host "[-] Cloudflare credentials missing in non-interactive mode." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "===============================================================" -ForegroundColor Yellow
    Write-Host "             Cloudflare Workers Configuration                  " -ForegroundColor Yellow
    Write-Host "===============================================================" -ForegroundColor Yellow
    Write-Host "To set up your zero-cost gateway, enter your Cloudflare API credentials:" -ForegroundColor Cyan
    Write-Host "  1. Account ID: 32-character ID from your Cloudflare dashboard (right column)." -ForegroundColor White
    Write-Host "  2. API Token: Profile -> API Tokens -> Create Token -> 'Edit Cloudflare Workers'." -ForegroundColor White
    Write-Host ""

    while (-not $ExistingAcc) {
        $ExistingAcc = (Read-Host "Enter Cloudflare Account ID").Trim()
    }
    while (-not $ExistingTok) {
        $ExistingTok = (Read-Host "Enter Cloudflare API Token").Trim()
    }
}

Write-Host ""
Write-Host "[*] Initializing Cloudflare Worker and domain rules..." -ForegroundColor Yellow

$PyInitCode = "import sys; from pathlib import Path; sys.path.insert(0, r'$InstallDir'); from bypass451.config import load_config, save_config; from bypass451.cloudflare import verify_token, get_subdomain; from bypass451.sync import sync_to_cloudflare; cfg = load_config(); cfg.account_id = '$ExistingAcc'.strip() if '$ExistingAcc' else cfg.account_id; cfg.api_token = '$ExistingTok'.strip() if '$ExistingTok' else cfg.api_token; cfg.worker_name = '$WorkerName'; valid, msg = verify_token(cfg.api_token); sys.exit(f'ERROR: Token invalid: {msg}') if not valid else None; sub = get_subdomain(cfg.account_id, cfg.api_token); cfg.subdomain = sub if sub else cfg.subdomain; save_config(cfg); ok, smsg = sync_to_cloudflare(cfg, force=True); print(f'[+] Worker status: {smsg}') if ok else sys.exit(f'ERROR: Sync failed: {smsg}')"

$InitRes = & $PythonCmd.Source -c $PyInitCode 2>&1
Write-Host $InitRes

if (-not $SkipService) {
    Write-Host ""
    Write-Host "[*] Registering background sync task in Windows Task Scheduler..." -ForegroundColor Yellow
    $SrvRes = & (Join-Path $InstallDir "451b.cmd") service install 2>&1
    Write-Host $SrvRes
}

Write-Host ""
Write-Host "[*] Running final verification..." -ForegroundColor Yellow
& (Join-Path $InstallDir "451b.cmd") diagnostics

Write-Host ""
Write-Host "===============================================================" -ForegroundColor Green
Write-Host "           451bypass IS FULLY INSTALLED AND READY!             " -ForegroundColor Green
Write-Host "===============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  You can now type '451b' in ANY terminal:" -ForegroundColor Cyan
Write-Host "    451b                   - Open interactive dashboard" -ForegroundColor White
Write-Host "    451b test              - Test 451/403 bypass for AI APIs" -ForegroundColor White
Write-Host "    451b domains list      - View all active proxied domains" -ForegroundColor White
Write-Host "    451b sync              - Re-sync domains with Cloudflare" -ForegroundColor White
Write-Host ""
