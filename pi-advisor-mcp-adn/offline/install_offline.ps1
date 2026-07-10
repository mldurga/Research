<#
.SYNOPSIS
  Install PI Advisor MCP (ADN edition) on the AIR-GAPPED Windows server from
  the offline bundle. No internet access is used at any point.

.DESCRIPTION
  Steps:
    1. Silently installs Python 3.12 to its own directory (does NOT touch PATH,
       so any existing Python installs/scripts are untouched).
    2. Creates an isolated virtual environment inside the install directory.
    3. Installs all dependencies from the bundled wheels (pip --no-index).
    4. Copies the application source and the embedding model into place.
    5. Creates .env from the template if absent.
    6. Runs verify_install.py.

  Run from an elevated PowerShell prompt, from inside the bundle:
    PS> Set-ExecutionPolicy -Scope Process Bypass
    PS> .\app\offline\install_offline.ps1 -InstallDir C:\PIAdvisor
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\PIAdvisor",
    [string]$PythonDir  = "C:\Python312",
    # Bundle root = two levels up from this script (bundle\app\offline\..)
    [string]$BundleDir  = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")),
    [switch]$SkipPythonInstall,
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"
Write-Host "== PI Advisor ADN offline installer ==" -ForegroundColor Cyan
Write-Host "Bundle : $BundleDir"
Write-Host "Target : $InstallDir"

$wheels = Join-Path $BundleDir "wheels"
$models = Join-Path $BundleDir "models"
$appSrc = Join-Path $BundleDir "app"
foreach ($p in @($wheels, $models, $appSrc)) {
    if (-not (Test-Path $p)) { Write-Error "Bundle folder missing: $p — check -BundleDir." }
}

# ------------------------------------------------------------- 1. Python
$pythonExe = Join-Path $PythonDir "python.exe"
if (-not $SkipPythonInstall -and -not (Test-Path $pythonExe)) {
    $installer = Get-ChildItem (Join-Path $BundleDir "python") -Filter "python-3.12.*-amd64.exe" | Select-Object -First 1
    if (-not $installer) { Write-Error "Python installer not found in bundle\python." }
    Write-Host "`n[1/6] Installing Python 3.12 to $PythonDir (isolated — PATH untouched) ..."
    # PrependPath=0 and Include_launcher=0: existing Python environments and
    # scripts on this server keep working exactly as before.
    Start-Process -Wait -FilePath $installer.FullName -ArgumentList @(
        "/quiet", "InstallAllUsers=1", "PrependPath=0", "Include_launcher=0",
        "Include_test=0", "AssociateFiles=0", "TargetDir=$PythonDir"
    )
    if (-not (Test-Path $pythonExe)) { Write-Error "Python installation failed." }
} else {
    Write-Host "`n[1/6] Python already present at $pythonExe"
}
& $pythonExe --version

# ------------------------------------------------------------- 2. App source
Write-Host "`n[2/6] Copying application source to $InstallDir ..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path (Join-Path $appSrc "*") -Destination $InstallDir -Recurse -Force

# ------------------------------------------------------------- 3. venv
$venv = Join-Path $InstallDir ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
Write-Host "`n[3/6] Creating virtual environment $venv ..."
& $pythonExe -m venv $venv
if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed." }

# ------------------------------------------------------------- 4. Dependencies
Write-Host "`n[4/6] Installing dependencies from bundled wheels (offline) ..."
& $venvPython -m pip install --no-index --find-links $wheels --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { Write-Error "pip bootstrap failed." }
& $venvPython -m pip install --no-index --find-links $wheels -r (Join-Path $InstallDir "requirements-lock.txt")
if ($LASTEXITCODE -ne 0) { Write-Error "Dependency installation failed." }

# ------------------------------------------------------------- 5. Model + config
Write-Host "`n[5/6] Copying embedding model ..."
Copy-Item -Path $models -Destination $InstallDir -Recurse -Force

$authSrc = Join-Path $BundleDir "auth"
if (Test-Path $authSrc) {
    Copy-Item -Path $authSrc -Destination $InstallDir -Recurse -Force
    Write-Host "Copied auth\jwks.json (offline Entra token validation)."
}

$envFile = Join-Path $InstallDir ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $InstallDir ".env.example") $envFile
    Write-Host ".env created from template — EDIT IT NOW (PI Web API URL, auth mode, allowlist)." -ForegroundColor Yellow
}
# Restrict .env to Administrators + SYSTEM (it may hold secrets).
icacls $envFile /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:F" | Out-Null
Write-Host ".env ACL restricted to Administrators and SYSTEM."
Write-Host "If the service runs as a dedicated account, grant it read access:" -ForegroundColor Yellow
Write-Host "    icacls `"$envFile`" /grant:r `"DOMAIN\svc-account:R`""

# ------------------------------------------------------------- 6. Verify
if (-not $SkipVerify) {
    Write-Host "`n[6/6] Running installation verification ..."
    & $venvPython (Join-Path $InstallDir "offline\verify_install.py")
    if ($LASTEXITCODE -ne 0) { Write-Error "Verification FAILED — see output above." }
} else {
    Write-Host "`n[6/6] Verification skipped."
}

Write-Host "`n== Installation complete ==" -ForegroundColor Green
Write-Host @"
Next steps:
  1. Edit $InstallDir\.env  (PI Web API, AUTH_MODE, allowlist)
  2. Test interactively:    $InstallDir\deploy\run_server.ps1
  3. Install as service:    $InstallDir\deploy\install_service.ps1
  4. Connect Copilot Studio: see $InstallDir\docs\COPILOT_INTEGRATION.md
"@
