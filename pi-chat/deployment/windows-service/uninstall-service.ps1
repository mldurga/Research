# Uninstall PI Vision Chat Backend Windows Service
# Run this script as Administrator

param(
    [string]$ServiceName = "PIVisionChatBackend",
    [string]$NSSMPath = "C:\nssm\nssm.exe"
)

Write-Host "Uninstalling PI Vision Chat Backend service..." -ForegroundColor Cyan

# Check if running as administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

# Check if service exists
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) {
    Write-Host "Service '$ServiceName' not found" -ForegroundColor Yellow
    exit 0
}

# Stop service if running
if ($service.Status -eq "Running") {
    Write-Host "Stopping service..." -ForegroundColor Cyan
    Stop-Service $ServiceName -Force
    Start-Sleep -Seconds 2
}

# Remove service using NSSM
if (Test-Path $NSSMPath) {
    Write-Host "Removing service..." -ForegroundColor Cyan
    & $NSSMPath remove $ServiceName confirm
} else {
    # Fallback to sc.exe
    Write-Host "Removing service using sc.exe..." -ForegroundColor Cyan
    sc.exe delete $ServiceName
}

Start-Sleep -Seconds 2

# Verify removal
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) {
    Write-Host "`nSUCCESS: Service uninstalled successfully!" -ForegroundColor Green
} else {
    Write-Host "`nWARNING: Service may still exist" -ForegroundColor Yellow
}
