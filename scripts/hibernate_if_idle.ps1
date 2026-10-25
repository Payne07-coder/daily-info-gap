$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LockPath = Join-Path $ProjectRoot "data\run.lock"
$RunLog = Join-Path $ProjectRoot "logs\scheduler.log"

if (Test-Path -LiteralPath $LockPath) {
    Add-Content -LiteralPath $RunLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Digest still running; hibernate skipped."
    exit 0
}

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class IdleTime {
    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO {
        public uint cbSize;
        public uint dwTime;
    }

    [DllImport("user32.dll")]
    static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

    public static uint Seconds() {
        var info = new LASTINPUTINFO();
        info.cbSize = (uint)Marshal.SizeOf(info);
        if (!GetLastInputInfo(ref info)) return 0;
        return ((uint)Environment.TickCount - info.dwTime) / 1000;
    }
}
"@

$idleSeconds = [IdleTime]::Seconds()
if ($idleSeconds -ge 600) {
    Add-Content -LiteralPath $RunLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') System idle for $idleSeconds seconds; hibernating."
    & shutdown.exe /h
}
else {
    Add-Content -LiteralPath $RunLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') User input detected; hibernate skipped."
}

