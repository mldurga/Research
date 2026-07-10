<#
.SYNOPSIS
  Register the PI Advisor MCP server for unattended operation on Windows
  using the built-in Task Scheduler (no extra binaries needed in the
  air-gapped environment).

.DESCRIPTION
  Creates a scheduled task that:
    * starts at system boot (before any logon),
    * runs as the service account you specify,
    * restarts automatically if the process exits,
    * logs stdout/stderr to <InstallDir>\logs\server.log.

  IMPORTANT for Kerberos PI Web API access: the account given here is the
  identity used for SSPI/Negotiate against the PI Web API gateway. Use the
  designated domain service account and make sure it has a PI mapping.

  Alternative service wrappers (NSSM, WinSW) also work if your organisation
  prefers real Windows services — point them at:
    <InstallDir>\.venv\Scripts\python.exe <InstallDir>\pi_mcp_server.py

.EXAMPLE
  .\install_service.ps1 -ServiceAccount "CORP\svc-piadvisor"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ServiceAccount,
    [string]$InstallDir = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$TaskName = "PI Advisor MCP Server",
    [switch]$Uninstall
)
$ErrorActionPreference = "Stop"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task '$TaskName' removed."
    return
}

$python = Join-Path $InstallDir ".venv\Scripts\python.exe"
$server = Join-Path $InstallDir "pi_mcp_server.py"
$logDir = Join-Path $InstallDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Wrapper keeps a rolling log and restarts the server if it ever exits.
$wrapper = Join-Path $InstallDir "deploy\service_wrapper.ps1"
@"
`$log = "$logDir\server.log"
while (`$true) {
    if ((Test-Path `$log) -and ((Get-Item `$log).Length -gt 50MB)) {
        Move-Item -Force `$log "`$log.1"
    }
    "`$(Get-Date -Format o) service wrapper: starting server" | Add-Content `$log
    & "$python" "$server" *>> `$log
    "`$(Get-Date -Format o) service wrapper: server exited (`$LASTEXITCODE), restarting in 10 s" | Add-Content `$log
    Start-Sleep -Seconds 10
}
"@ | Set-Content -Path $wrapper -Encoding UTF8

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapper`"" `
    -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650)

Write-Host "You will be prompted for the password of $ServiceAccount."
$cred = Get-Credential -UserName $ServiceAccount -Message "Service account password"

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -User $cred.UserName `
    -Password $cred.GetNetworkCredential().Password -RunLevel Limited | Out-Null

Write-Host "`nTask '$TaskName' registered (runs at boot as $($cred.UserName))." -ForegroundColor Green
Write-Host "Start it now with:   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Watch the log with:  Get-Content '$logDir\server.log' -Wait -Tail 50"
