param(
    [string]$TaskName = "Pyautotest Esbao Mall UI",
    [string]$StartTime = "01:00"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ScriptPath = Join-Path $ProjectRoot "scripts\run_esbao_ui_scheduled.ps1"

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily Esbao mall UI smoke check with email report" `
    -Force | Out-Null

$Info = Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo
Write-Output "Created scheduled task: $TaskName"
Write-Output "Daily start time: $StartTime"
Write-Output "Next run: $($Info.NextRunTime)"
Write-Output "Script: $ScriptPath"
Write-Output ""
Write-Output "Ensure .env has EMAIL_* configured; scheduled run uses -EmailReport automatically."
