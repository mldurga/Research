<#
.SYNOPSIS
  Run the PI Advisor MCP server interactively (console window) using the
  project virtual environment. Use for testing; use install_service.ps1 for
  unattended operation.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)
$ErrorActionPreference = "Stop"

$python = Join-Path $InstallDir ".venv\Scripts\python.exe"
$server = Join-Path $InstallDir "pi_mcp_server.py"
if (-not (Test-Path $python)) { Write-Error "venv not found at $python — run offline\install_offline.ps1 first." }
if (-not (Test-Path (Join-Path $InstallDir ".env"))) { Write-Error ".env not found — copy .env.example and configure it." }

Write-Host "Starting PI Advisor MCP server (Ctrl+C to stop) ..." -ForegroundColor Cyan
& $python $server
