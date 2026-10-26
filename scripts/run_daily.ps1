$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "D:\Codex\Python312\python.exe"
$Launcher = Join-Path $ProjectRoot "launch.py"
$LockPath = Join-Path $ProjectRoot "data\run.lock"
$LogDir = Join-Path $ProjectRoot "logs"
$RunLog = Join-Path $LogDir "scheduler.log"
$TempDir = Join-Path $ProjectRoot "data\tmp"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

if (Test-Path -LiteralPath $LockPath) {
    $lockAge = (Get-Date) - (Get-Item -LiteralPath $LockPath).LastWriteTime
    if ($lockAge.TotalHours -lt 3) {
        Add-Content -LiteralPath $RunLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') A run is already active; skipping."
        exit 0
    }
    Remove-Item -LiteralPath $LockPath -ErrorAction SilentlyContinue
}

New-Item -ItemType File -Path $LockPath -Force | Out-Null
Add-Content -LiteralPath $RunLog -Value "`n$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Starting scheduled digest."

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:DAILY_INFO_GAP_FILE_LOG_ONLY = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "vendor"
$env:PIP_CACHE_DIR = Join-Path $ProjectRoot ".cache\pip"
$env:TEMP = $TempDir
$env:TMP = $TempDir
Set-Location -LiteralPath $ProjectRoot

try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "Python not found at $Python"
    }

    Add-Content -LiteralPath $RunLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Running pipeline."
    $ErrorActionPreference = "Continue"
    & $Python $Launcher run --publish 2>&1 |
        ForEach-Object { $_.ToString() } |
        Tee-Object -FilePath $RunLog -Append
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    exit $exitCode
}
catch {
    Add-Content -LiteralPath $RunLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ERROR: $($_.Exception.Message)"
    exit 1
}
finally {
    Remove-Item -LiteralPath $LockPath -ErrorAction SilentlyContinue
}

