param(
    [int]$AfterMinutes = 5
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$ScriptPath = Join-Path $PSScriptRoot "run_daily.ps1"
$TaskName = "DailyInfoGapWakeTest"
$At = (Get-Date).AddMinutes($AfterMinutes)

$action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Once -At $At
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "One-off Daily Info Gap wake test" `
    -Force | Out-Null

Write-Host "Wake test scheduled for $($At.ToString('yyyy-MM-dd HH:mm:ss'))."
Write-Host "The computer will hibernate in 10 seconds. Keep it connected to power and leave the lid open."
Start-Sleep -Seconds 10
& shutdown.exe /h

