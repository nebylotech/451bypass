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

foreach ($launcher in @("451b.py", "451bypass.py")) {
    $lSrc = Join-Path $CurrentDir $launcher
    if (Test-Path $lSrc) {
        Copy-Item -Path $lSrc -Destination $InstallDir -Force
    }
}

foreach ($unScript in @("uninstall.ps1", "uninstall.bat")) {
    $uSrc = Join-Path $CurrentDir $unScript
    if (Test-Path $uSrc) {
        Copy-Item -Path $uSrc -Destination $InstallDir -Force
    }
}

$CmdContent = "@echo off`r`n`"$($PythonCmd.Source)`" `"%~dp0451b.py`" %*"
foreach ($cmdName in @("451b.cmd", "451bypass.cmd")) {
    Set-Content -Path (Join-Path $InstallDir $cmdName) -Value $CmdContent -Encoding ASCII
    Set-Content -Path (Join-Path $CurrentDir $cmdName) -Value $CmdContent -Encoding ASCII
}

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
$Legacy51Dir = Join-Path $env:LOCALAPPDATA "51-bypass"
$DotConfigFile = Join-Path (Join-Path $env:USERPROFILE ".451bypass") "config.json"
$LegacyDotConfigFile = Join-Path (Join-Path $env:USERPROFILE ".51-bypass") "config.json"
$LegacyConfigFile = Join-Path (Join-Path $env:USERPROFILE ".cloudflare-dns") "config.json"

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

if ((-not $ExistingAcc -or -not $ExistingTok) -and (Test-Path (Join-Path $Legacy51Dir "config.json"))) {
    try {
        $Json = Get-Content (Join-Path $Legacy51Dir "config.json") -Raw | ConvertFrom-Json
        if (-not $ExistingAcc) { $ExistingAcc = $Json.account_id }
        if (-not $ExistingTok) { $ExistingTok = $Json.api_token }
        if (-not $ExistingSub) { $ExistingSub = $Json.subdomain }
    } catch {}
}

if ((-not $ExistingAcc -or -not $ExistingTok) -and (Test-Path $DotConfigFile)) {
    try {
        $Json = Get-Content $DotConfigFile -Raw | ConvertFrom-Json
        if (-not $ExistingAcc) { $ExistingAcc = $Json.account_id }
        if (-not $ExistingTok) { $ExistingTok = $Json.api_token }
        if (-not $ExistingSub) { $ExistingSub = $Json.subdomain }
    } catch {}
}

if ((-not $ExistingAcc -or -not $ExistingTok) -and (Test-Path $LegacyDotConfigFile)) {
    try {
        $Json = Get-Content $LegacyDotConfigFile -Raw | ConvertFrom-Json
        if (-not $ExistingAcc) { $ExistingAcc = $Json.account_id }
        if (-not $ExistingTok) { $ExistingTok = $Json.api_token }
        if (-not $ExistingSub) { $ExistingSub = $Json.subdomain }
    } catch {}
}

if ((-not $ExistingAcc -or -not $ExistingTok) -and (Test-Path $LegacyConfigFile)) {
    try {
        $Json = Get-Content $LegacyConfigFile -Raw | ConvertFrom-Json
        if (-not $ExistingAcc) { $ExistingAcc = $Json.AccountId }
        if (-not $ExistingTok) { $ExistingTok = $Json.ApiToken }
        if (-not $ExistingSub) { $ExistingSub = $Json.Subdomain }
    } catch {}
}

if ($AccountId) { $ExistingAcc = $AccountId }
if ($ApiToken) { $ExistingTok = $ApiToken }

if (-not $ExistingAcc -or -not $ExistingTok) {
    if ($NonInteractive) {
        Write-Host "[-] Cloudflare credentials missing in non-interactive mode." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "=== Cloudflare Workers Configuration ===" -ForegroundColor Yellow
    Write-Host "Credentials can be obtained free from https://dash.cloudflare.com" -ForegroundColor Cyan
    Write-Host "1. Account ID: 32-character string on the right side of Cloudflare Dashboard."
    Write-Host "2. API Token: My Profile -> API Tokens -> Create Token -> 'Edit Cloudflare Workers'."
    Write-Host ""

    $ExistingAcc = Read-Host "Enter Cloudflare Account ID [$ExistingAcc]"
    $ExistingTok = Read-Host "Enter Cloudflare API Token"
}

Write-Host ""
Write-Host "[*] Initializing Cloudflare Worker and domain rules..." -ForegroundColor Yellow

$PyInitCode = "import sys; from pathlib import Path; sys.path.insert(0, r'$InstallDir'); from bypass451.config import load_config, save_config; from bypass451.cloudflare import verify_token, get_subdomain; from bypass451.sync import sync_to_cloudflare; cfg = load_config(); cfg.account_id = '$ExistingAcc'.strip() if '$ExistingAcc' else cfg.account_id; cfg.api_token = '$ExistingTok'.strip() if '$ExistingTok' else cfg.api_token; cfg.worker_name = '$WorkerName'; valid, msg = verify_token(cfg.api_token); sys.exit(f'ERROR: Token invalid: {msg}') if not valid else None; sub = get_subdomain(cfg.account_id, cfg.api_token); cfg.subdomain = sub if sub else cfg.subdomain; save_config(cfg); ok, smsg = sync_to_cloudflare(cfg, force=True); print(f'[+] Worker status: {smsg}') if ok else sys.exit(f'ERROR: Sync failed: {smsg}')"

$InitRes = & $PythonCmd.Source -c $PyInitCode 2>&1
Write-Host $InitRes

if (-not $SkipService) {
    Write-Host ""
    Write-Host "[*] Registering background sync task in Windows Task Scheduler..." -ForegroundColor Yellow
    $SrvRes = & $PythonCmd.Source (Join-Path $InstallDir "451b.py") service install 2>&1
    Write-Host $SrvRes
}

Write-Host ""
Write-Host "[*] Running final verification..." -ForegroundColor Yellow
& $PythonCmd.Source (Join-Path $InstallDir "451b.py") diagnostics

Write-Host ""
Write-Host "===============================================================" -ForegroundColor Green
Write-Host "           451bypass IS FULLY INSTALLED AND READY!             " -ForegroundColor Green
Write-Host "===============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  You can now type '451b' (or '451bypass') in ANY terminal:" -ForegroundColor Cyan
Write-Host "    451b                   - Open interactive dashboard" -ForegroundColor White
Write-Host "    451b test              - Test 451/403 bypass for AI APIs" -ForegroundColor White
Write-Host "    451b domains list      - View all active proxied domains" -ForegroundColor White
Write-Host "    451b sync              - Re-sync domains with Cloudflare" -ForegroundColor White
Write-Host ""
Write-Host "  Use in your Python code / LangChain / Cursor:" -ForegroundColor Yellow
Write-Host "    base_url = 'https://$WorkerName.$ExistingSub.workers.dev/api.openai.com/v1'" -ForegroundColor Green
Write-Host ""
