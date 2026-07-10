<#
.SYNOPSIS
  Build the complete offline installation bundle on an INTERNET-CONNECTED
  Windows machine. The resulting folder/zip is everything you carry into the
  air-gapped environment.

.DESCRIPTION
  Produces .\bundle\ containing:
    python\python-3.12.10-amd64.exe   — Python installer for the target server
    wheels\*.whl                      — every locked dependency + pip/setuptools/wheel
    models\bge-base-en-v1.5\          — embedding model (~430 MB)
    app\                              — this project's source, config template, docs
    auth\jwks.json                    — Entra ID signing keys (if -TenantId given)

  Requires: Python 3.12 x64 installed on THIS machine (winget install
  Python.Python.3.12, or run the downloaded installer manually), because the
  wheel download must run under CPython 3.12 to match the target exactly.

.EXAMPLE
  .\download_bundle.ps1
  .\download_bundle.ps1 -TenantId 11111111-2222-3333-4444-555555555555
#>
[CmdletBinding()]
param(
    [string]$BundleDir = (Join-Path $PSScriptRoot "..\bundle"),
    # Entra tenant id — when given, exports jwks.json for fully-offline
    # token validation (AUTH_JWKS_FILE).
    [string]$TenantId = "",
    # Sovereign-cloud login host override, if applicable.
    [string]$LoginHost = "login.microsoftonline.com",
    [string]$PythonInstallerVersion = "3.12.10",
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
$BundleDir = Resolve-Path $BundleDir

Write-Host "== PI Advisor ADN offline bundle builder ==" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host "Bundle : $BundleDir"

# ---------------------------------------------------------------- 1. Python
$pyDir = Join-Path $BundleDir "python"
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
$installer = Join-Path $pyDir "python-$PythonInstallerVersion-amd64.exe"
if (-not (Test-Path $installer)) {
    $url = "https://www.python.org/ftp/python/$PythonInstallerVersion/python-$PythonInstallerVersion-amd64.exe"
    Write-Host "`n[1/5] Downloading Python installer: $url"
    Invoke-WebRequest -Uri $url -OutFile $installer
} else {
    Write-Host "`n[1/5] Python installer already present."
}

# Locate a local CPython 3.12 to run pip with (tags must match the target).
$py = $null
foreach ($candidate in @("py -3.12", "python3.12", "python")) {
    try {
        $v = & $candidate.Split()[0] $candidate.Split()[1..99] -c "import sys;print(sys.version_info[:2])" 2>$null
        if ($v -match "\(3, 12\)") { $py = $candidate; break }
    } catch { }
}
if (-not $py) {
    Write-Error ("CPython 3.12 was not found on this machine. Install it first " +
                 "(the installer was just downloaded to $installer), then re-run this script.")
}
Write-Host "Using local Python: $py"
function Invoke-Py { & $py.Split()[0] ($py.Split()[1..99] + $args) }

# ---------------------------------------------------------------- 2. Wheels
Write-Host "`n[2/5] Downloading locked wheels (win_amd64 / cp312) ..."
$wheelDir = Join-Path $BundleDir "wheels"
New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
$lock = Join-Path $ProjectRoot "requirements-lock.txt"

# --no-deps + fully-pinned lock = exact, marker-safe, reproducible set.
Invoke-Py -m pip download -r $lock -d $wheelDir --no-deps --only-binary=:all: `
    --platform win_amd64 --python-version 312 --implementation cp
if ($LASTEXITCODE -ne 0) { Write-Error "Wheel download failed." }

# venv bootstrap tooling for the air-gapped side
Invoke-Py -m pip download pip setuptools wheel -d $wheelDir --only-binary=:all: `
    --platform win_amd64 --python-version 312 --implementation cp
if ($LASTEXITCODE -ne 0) { Write-Error "pip/setuptools/wheel download failed." }
Write-Host ("Wheels: " + (Get-ChildItem $wheelDir -Filter *.whl).Count + " files, " +
            "{0:N0} MB" -f ((Get-ChildItem $wheelDir | Measure-Object Length -Sum).Sum / 1MB))

# ---------------------------------------------------------------- 3. Model
Write-Host "`n[3/5] Downloading embedding model ..."
Invoke-Py -m pip install --quiet "huggingface_hub>=0.23"
Invoke-Py (Join-Path $PSScriptRoot "download_model.py") (Join-Path $BundleDir "models")
if ($LASTEXITCODE -ne 0) { Write-Error "Model download failed." }

# ---------------------------------------------------------------- 4. JWKS
if ($TenantId) {
    Write-Host "`n[4/5] Exporting Entra ID JWKS for offline token validation ..."
    $authDir = Join-Path $BundleDir "auth"
    New-Item -ItemType Directory -Force -Path $authDir | Out-Null
    $jwksUrl = "https://$LoginHost/$TenantId/discovery/v2.0/keys"
    Invoke-WebRequest -Uri $jwksUrl -OutFile (Join-Path $authDir "jwks.json")
    Write-Host "JWKS saved (source: $jwksUrl). Re-export monthly — Microsoft rotates signing keys."
} else {
    Write-Host "`n[4/5] Skipping JWKS export (no -TenantId). Needed only for AUTH_MODE=entra_jwt with AUTH_JWKS_FILE."
}

# ---------------------------------------------------------------- 5. App source
Write-Host "`n[5/5] Copying application source ..."
$appDir = Join-Path $BundleDir "app"
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$include = @("*.py", "requirements.txt", "requirements-lock.txt", ".env.example", "README.md", ".gitignore")
foreach ($pattern in $include) {
    Copy-Item -Path (Join-Path $ProjectRoot $pattern) -Destination $appDir -Force -ErrorAction SilentlyContinue
}
foreach ($sub in @("offline", "deploy", "docs")) {
    Copy-Item -Path (Join-Path $ProjectRoot $sub) -Destination $appDir -Recurse -Force
}

if ($Zip) {
    $zipPath = "$BundleDir.zip"
    Write-Host "`nCompressing to $zipPath ..."
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    Compress-Archive -Path (Join-Path $BundleDir "*") -DestinationPath $zipPath
}

Write-Host "`n== Bundle complete ==" -ForegroundColor Green
Write-Host "Carry the bundle into the air-gapped environment and run:"
Write-Host "    app\offline\install_offline.ps1"
