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
Write-Host "         451bypass v1.0 -- Automated Installer and Setup       " -ForegroundColor Cyan
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
$DomainsSrc = Join-Path $CurrentDir "domains"
$UnScript = Join-Path $CurrentDir "uninstall.ps1"

if (-not (Test-Path $PackageSrc)) {
    Write-Host "[*] Downloading 451bypass package from GitHub..." -ForegroundColor Cyan
    $ZipPath = Join-Path $env:TEMP "451bypass-main.zip"
    $ExtractDir = Join-Path $env:TEMP "451bypass-main-extract"
    if (Test-Path $ExtractDir) {
        Remove-Item -Path $ExtractDir -Recurse -Force | Out-Null
    }
    Invoke-WebRequest -Uri "https://github.com/nebylotech/451bypass/archive/refs/heads/main.zip" -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
    $ExtractedRoot = Join-Path $ExtractDir "451bypass-main"
    $PackageSrc = Join-Path $ExtractedRoot "bypass451"
    $DomainsSrc = Join-Path $ExtractedRoot "domains"
    $UnScript = Join-Path $ExtractedRoot "uninstall.ps1"
}

if (Test-Path $PackageSrc) {
    Copy-Item -Path $PackageSrc -Destination $InstallDir -Recurse -Force
}

if (Test-Path $DomainsSrc) {
    Copy-Item -Path $DomainsSrc -Destination $InstallDir -Recurse -Force
}

if (Test-Path $UnScript) {
    Copy-Item -Path $UnScript -Destination $InstallDir -Force
}

$CmdContent = "@echo off`r`nset `"PYTHONPATH=%~dp0;%PYTHONPATH%`"`r`n`"$($PythonCmd.Source)`" -m bypass451 %*"
Set-Content -Path (Join-Path $InstallDir "451b.cmd") -Value $CmdContent -Encoding ASCII
if (Test-Path (Join-Path $CurrentDir "bypass451")) {
    Set-Content -Path (Join-Path $CurrentDir "451b.cmd") -Value $CmdContent -Encoding ASCII
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
$ExistingAcc = ""
$ExistingTok = ""

if (Test-Path $ConfigFile) {
    try {
        $Json = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        $ExistingAcc = $Json.account_id
        $ExistingTok = $Json.api_token
    } catch {}
}

if ($AccountId) { $ExistingAcc = $AccountId.Trim() }
if ($ApiToken) { $ExistingTok = $ApiToken.Trim() }

if ($ExistingTok -and -not $ExistingAcc) {
    Write-Host "[*] Discovering Cloudflare Account ID automatically..." -ForegroundColor Yellow
    $PyDiscover = "import sys; sys.path.insert(0, r'$InstallDir'); from bypass451.cloudflare import list_accounts, verify_token; valid, msg = verify_token('$ExistingTok'); sys.exit(f'ERROR: {msg}') if not valid else None; accs = list_accounts('$ExistingTok'); sys.exit('ERROR: No account found') if not accs else print(accs[0]['id'])"
    $ExistingAcc = (& $PythonCmd.Source -c $PyDiscover 2>&1).Trim()
    if ($ExistingAcc -and $ExistingAcc -notlike "*ERROR*") {
        Write-Host "[+] Discovered Account ID: $ExistingAcc" -ForegroundColor Green
    } else {
        $ExistingAcc = ""
    }
}

if ($ExistingAcc -and $ExistingTok) {
    Write-Host ""
    Write-Host "[*] Applying Cloudflare credentials and syncing Worker..." -ForegroundColor Yellow
    $PyInitCode = "import sys; sys.path.insert(0, r'$InstallDir'); from bypass451.config import load_config, save_config; from bypass451.cloudflare import verify_token, get_subdomain; from bypass451.sync import sync_to_cloudflare; cfg = load_config(); cfg.account_id = '$ExistingAcc'; cfg.api_token = '$ExistingTok'; cfg.worker_name = '$WorkerName'; valid, msg = verify_token(cfg.api_token); sys.exit(f'ERROR: Token invalid: {msg}') if not valid else None; sub = get_subdomain(cfg.account_id, cfg.api_token); cfg.subdomain = sub if sub else cfg.subdomain; save_config(cfg); ok, smsg = sync_to_cloudflare(cfg, force=True); print(f'[+] Worker status: {smsg}') if ok else sys.exit(f'ERROR: Sync failed: {smsg}')"
    $InitRes = & $PythonCmd.Source -c $PyInitCode 2>&1
    Write-Host $InitRes
} else {
    if ($NonInteractive) {
        Write-Host "[-] Cloudflare credentials missing in non-interactive mode." -ForegroundColor Red
        exit 1
    }

    & (Join-Path $InstallDir "451b.cmd") setup
}

if (-not $SkipService) {
    Write-Host ""
    Write-Host "[*] Registering background sync task in Windows Task Scheduler..." -ForegroundColor Yellow
    $TaskRunner = Join-Path $InstallDir "451b.cmd"
    schtasks /delete /tn "51-BYPASS-Sync" /f 2>$null | Out-Null
    schtasks /create /tn "451bypass-Sync" /tr "cmd.exe /c \"\"$TaskRunner\"\" service run-once" /sc daily /st 04:00 /f 2>$null | Out-Null
    Write-Host "[+] Background sync task '451bypass-Sync' registered successfully (daily at 04:00)." -ForegroundColor Green
}

Write-Host ""
Write-Host "[*] Running final verification..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
& (Join-Path $InstallDir "451b.cmd") diagnostics

Write-Host ""
Write-Host "===============================================================" -ForegroundColor Green
Write-Host "        451bypass v1.0 IS FULLY INSTALLED AND READY!           " -ForegroundColor Green
Write-Host "===============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  You can now type '451b' in ANY terminal:" -ForegroundColor Cyan
Write-Host "    451b                   - Open interactive dashboard" -ForegroundColor White
Write-Host "    451b test              - Test 451/403 bypass for AI APIs" -ForegroundColor White
Write-Host "    451b domains list      - View all active proxied domains" -ForegroundColor White
Write-Host "    451b sync              - Re-sync domains with Cloudflare" -ForegroundColor White
Write-Host ""
