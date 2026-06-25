param(
    [string]$TaskName = "Pyautotest Appium Explore",
    [string]$StartTime = "03:00",
    [int]$Steps = 100,
    [int]$PauseMs = 500
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ScriptPath = Join-Path $ProjectRoot "scripts\run_appium_explore_scheduled.ps1"

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -Steps $Steps -PauseMs $PauseMs" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Run Appium random explore daily (login + email report)" `
    -Force | Out-Null

$Info = Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo
Write-Output "Created scheduled task: $TaskName"
Write-Output "Daily start time: $StartTime"
Write-Output "Next run: $($Info.NextRunTime)"
Write-Output "Script: $ScriptPath"
