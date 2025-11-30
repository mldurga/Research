# Install PI Vision Chat Backend as Windows Service
# Run this script as Administrator

param(
    [string]$BackendPath = "C:\pi-chat\backend",
    [string]$ServiceName = "PIVisionChatBackend",
    [string]$NSSMPath = "C:\nssm\nssm.exe"
)

Write-Host "Installing PI Vision Chat Backend as Windows Service..." -ForegroundColor Cyan

# Check if running as administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

# Check if NSSM exists
if (-not (Test-Path $NSSMPath)) {
    Write-Host "ERROR: NSSM not found at $NSSMPath" -ForegroundColor Red
    Write-Host "Please download NSSM from https://nssm.cc/download and extract to C:\nssm" -ForegroundColor Yellow
    exit 1
}

# Check if backend path exists
if (-not (Test-Path $BackendPath)) {
    Write-Host "ERROR: Backend path not found: $BackendPath" -ForegroundColor Red
    exit 1
}

# Get Python executable path
$pythonExe = Join-Path $BackendPath "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Python virtual environment not found" -ForegroundColor Red
    Write-Host "Please create virtual environment and install dependencies first" -ForegroundColor Yellow
    exit 1
}

# Get main.py path
$mainPy = Join-Path $BackendPath "app\main.py"
if (-not (Test-Path $mainPy)) {
    Write-Host "ERROR: main.py not found: $mainPy" -ForegroundColor Red
    exit 1
}

# Check if service already exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Service already exists. Removing..." -ForegroundColor Yellow
    & $NSSMPath stop $ServiceName
    & $NSSMPath remove $ServiceName confirm
    Start-Sleep -Seconds 2
}

# Install service
Write-Host "Installing service..." -ForegroundColor Cyan
& $NSSMPath install $ServiceName $pythonExe "-m" "app.main"

# Configure service
Write-Host "Configuring service..." -ForegroundColor Cyan
& $NSSMPath set $ServiceName AppDirectory $BackendPath
& $NSSMPath set $ServiceName DisplayName "PI Vision Chat Backend"
& $NSSMPath set $ServiceName Description "FastAPI backend for PI Vision Chat Interface with LLM integration"
& $NSSMPath set $ServiceName Start SERVICE_AUTO_START

# Set recovery options
& $NSSMPath set $ServiceName AppStdout "$BackendPath\logs\service-stdout.log"
& $NSSMPath set $ServiceName AppStderr "$BackendPath\logs\service-stderr.log"
& $NSSMPath set $ServiceName AppRotateFiles 1
& $NSSMPath set $ServiceName AppRotateOnline 1
& $NSSMPath set $ServiceName AppRotateSeconds 86400
& $NSSMPath set $ServiceName AppRotateBytes 1048576

# Configure failure actions (restart on failure)
& $NSSMPath set $ServiceName AppExit Default Restart
& $NSSMPath set $ServiceName AppRestartDelay 5000

# Start service
Write-Host "Starting service..." -ForegroundColor Cyan
Start-Service $ServiceName

# Wait a moment for service to start
Start-Sleep -Seconds 3

# Check service status
$service = Get-Service -Name $ServiceName
if ($service.Status -eq "Running") {
    Write-Host "`nSUCCESS: Service installed and started successfully!" -ForegroundColor Green
    Write-Host "`nService Details:" -ForegroundColor Cyan
    Write-Host "  Name: $ServiceName"
    Write-Host "  Status: $($service.Status)"
    Write-Host "  Start Type: $($service.StartType)"
    Write-Host "`nAPI should be available at: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "Logs location: $BackendPath\logs\" -ForegroundColor Cyan
} else {
    Write-Host "`nWARNING: Service installed but not running" -ForegroundColor Yellow
    Write-Host "Status: $($service.Status)" -ForegroundColor Yellow
    Write-Host "Check logs at: $BackendPath\logs\" -ForegroundColor Yellow
}

Write-Host "`nUseful commands:" -ForegroundColor Cyan
Write-Host "  Start service:   Start-Service $ServiceName"
Write-Host "  Stop service:    Stop-Service $ServiceName"
Write-Host "  Restart service: Restart-Service $ServiceName"
Write-Host "  Check status:    Get-Service $ServiceName"
Write-Host "  View logs:       Get-Content $BackendPath\logs\pi_chat_*.log -Tail 50"
