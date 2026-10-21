[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Continue"

Write-Host "===============================================================" -ForegroundColor Yellow
Write-Host "           451bypass -- Full System Uninstaller                " -ForegroundColor Yellow
Write-Host "===============================================================" -ForegroundColor Yellow
Write-Host ""

$InstallDir = Join-Path $env:LOCALAPPDATA "451bypass"
$ConfigFile = Join-Path $InstallDir "config.json"
$LegacyConfigFile = Join-Path (Join-Path $env:LOCALAPPDATA "51-bypass") "config.json"

$AccountId = ""
$ApiToken = ""
$WorkerName = "ai-gateway"

if (Test-Path $ConfigFile) {
    try {
        $json = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        $AccountId = $json.account_id
        $ApiToken = $json.api_token
        if ($json.worker_name) { $WorkerName = $json.worker_name }
    } catch {}
} elseif (Test-Path $LegacyConfigFile) {
    try {
        $json = Get-Content $LegacyConfigFile -Raw | ConvertFrom-Json
        $AccountId = $json.account_id
        $ApiToken = $json.api_token
        if ($json.worker_name) { $WorkerName = $json.worker_name }
    } catch {}
}

if ($AccountId -and $ApiToken -and $WorkerName) {
    Write-Host "[*] Deleting Cloudflare Worker '$WorkerName'..." -ForegroundColor Yellow
    try {
        $headers = @{
            "Authorization" = "Bearer $ApiToken"
            "User-Agent" = "451bypass/1.0"
        }
        $uri = "https://api.cloudflare.com/client/v4/accounts/$AccountId/workers/scripts/$WorkerName"
        $res = Invoke-RestMethod -Uri $uri -Method Delete -Headers $headers
        if ($res.success) {
            Write-Host "[+] Cloudflare Worker '$WorkerName' successfully deleted from Cloudflare." -ForegroundColor Green
        } else {
            Write-Host "[-] Could not delete worker: $($res.errors[0].message)" -ForegroundColor Red
        }
    } catch {
        Write-Host "[!] Cloudflare API call returned: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "[*] No Cloudflare credentials found to delete worker." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[*] Removing Windows background tasks..." -ForegroundColor Yellow
schtasks /delete /tn "451bypass-Sync" /f 2>&1 | Out-Null
schtasks /delete /tn "51-BYPASS-Sync" /f 2>&1 | Out-Null
Write-Host "[+] Windows Scheduled Tasks removed." -ForegroundColor Green

Write-Host ""
Write-Host "[*] Removing application directories and configs..." -ForegroundColor Yellow

$dirsToRemove = @(
    $InstallDir,
    (Join-Path $env:LOCALAPPDATA "51-bypass"),
    (Join-Path $env:USERPROFILE ".451bypass"),
    (Join-Path $env:USERPROFILE ".51-bypass")
)

foreach ($d in $dirsToRemove) {
    if (Test-Path $d) {
        Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
    }
}
Write-Host "[+] Application directories deleted." -ForegroundColor Green

Write-Host ""
Write-Host "[*] Cleaning User PATH..." -ForegroundColor Yellow
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath) {
    $filtered = ($userPath -split ";") | Where-Object { $_ -and $_ -notlike "*451bypass*" -and $_ -notlike "*51-bypass*" }
    [Environment]::SetEnvironmentVariable("Path", ($filtered -join ";"), "User")
    Write-Host "[+] Removed from User PATH." -ForegroundColor Green
}

Write-Host ""
Write-Host "===============================================================" -ForegroundColor Green
Write-Host "         451bypass IS FULLY REMOVED FROM YOUR SYSTEM           " -ForegroundColor Green
Write-Host "===============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  - Windows background task stopped and removed" -ForegroundColor White
Write-Host "  - Cloudflare Worker deleted from your Cloudflare account" -ForegroundColor White
Write-Host "  - Application files and configs removed" -ForegroundColor White
Write-Host "  - System PATH variable cleaned" -ForegroundColor White
Write-Host ""
