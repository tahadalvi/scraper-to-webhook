# Registers a daily Windows Task Scheduler job that runs the scraper.
# Run once from PowerShell in this folder:  .\schedule_windows.ps1 -At "09:15"

param(
    [string]$At = "09:15",
    [string]$TaskName = "scraper-to-webhook"
)

$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scraper.py"

$action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Task '$TaskName' will run daily at $At. Logs: $root\runs.log"
