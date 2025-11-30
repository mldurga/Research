# Install PI Vision Chat Extension
# Run this script as Administrator

param(
    [string]$SourcePath = "C:\pi-chat\pi-vision-extension",
    [string]$PIVisionPath = "C:\Program Files\AVEVA\PI Vision\Scripts\app\editor\symbols\ext"
)

Write-Host "Installing PI Vision Chat Extension..." -ForegroundColor Cyan

# Check if running as administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

# Check if source path exists
if (-not (Test-Path $SourcePath)) {
    Write-Host "ERROR: Source path not found: $SourcePath" -ForegroundColor Red
    exit 1
}

# Check if PI Vision is installed
if (-not (Test-Path $PIVisionPath)) {
    Write-Host "ERROR: PI Vision path not found: $PIVisionPath" -ForegroundColor Red
    Write-Host "Please verify PI Vision installation" -ForegroundColor Yellow
    exit 1
}

# Create pichat directory
$destPath = Join-Path $PIVisionPath "pichat"
Write-Host "Creating extension directory: $destPath" -ForegroundColor Cyan
New-Item -Path $destPath -ItemType Directory -Force | Out-Null

# Copy files
Write-Host "Copying extension files..." -ForegroundColor Cyan
Copy-Item "$SourcePath\*" -Destination $destPath -Recurse -Force

# Set permissions for IIS
Write-Host "Setting permissions..." -ForegroundColor Cyan
$acl = Get-Acl $destPath
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "IIS_IUSRS",
    "ReadAndExecute",
    "ContainerInherit,ObjectInherit",
    "None",
    "Allow"
)
$acl.SetAccessRule($rule)
Set-Acl $destPath $acl

# Restart IIS
Write-Host "Restarting IIS..." -ForegroundColor Cyan
iisreset

Start-Sleep -Seconds 5

Write-Host "`nSUCCESS: PI Vision Chat Extension installed!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  1. Open PI Vision in your browser"
Write-Host "  2. Clear browser cache (Ctrl+Shift+Del)"
Write-Host "  3. Go to Edit mode"
Write-Host "  4. Look for 'PI Chat' symbol in the symbol palette"
Write-Host "`nInstallation location: $destPath" -ForegroundColor Cyan
