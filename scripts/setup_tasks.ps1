param(
    [switch]$SkipPowerSettings
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$CurrentUser = "$env:USERDOMAIN\$env:USERNAME"

if (-not (Test-Path -LiteralPath $PowerShell)) {
    throw "Windows PowerShell not found at $PowerShell"
}

function Register-DailyGapTask {
    param(
        [string]$TaskName,
        [string]$ScriptName,
        [datetime]$At,
        [bool]$Wake
    )

    $scriptPath = Join-Path $PSScriptRoot $ScriptName
    $argument = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $action = New-ScheduledTaskAction `
        -Execute $PowerShell `
        -Argument $argument `
        -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    $principal = New-ScheduledTaskPrincipal `
        -UserId $CurrentUser `
        -LogonType Interactive `
        -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet `
        -WakeToRun:$Wake `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 120)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Daily Info Gap scheduled task" `
        -Force | Out-Null
}

Register-DailyGapTask `
    -TaskName "DailyInfoGap" `
    -ScriptName "run_daily.ps1" `
    -At (Get-Date "05:45") `
    -Wake $true

Register-DailyGapTask `
    -TaskName "DailyInfoGapHibernate" `
    -ScriptName "hibernate_if_idle.ps1" `
    -At (Get-Date "07:15") `
    -Wake $false

Write-Host "Scheduled tasks installed:"
Get-ScheduledTask -TaskName "DailyInfoGap*" |
    Select-Object TaskName, State |
    Format-Table -AutoSize

if (-not $SkipPowerSettings) {
    & powercfg.exe /hibernate on
    & powercfg.exe /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
    & powercfg.exe /setactive SCHEME_CURRENT
    Write-Host "AC wake timer enabled. If Windows reports access denied, run this script as administrator."
}

