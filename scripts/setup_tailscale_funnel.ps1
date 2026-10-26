$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SiteRoot = Join-Path $ProjectRoot "docs"
$Tailscale = "C:\Program Files\Tailscale\tailscale.exe"
$PublicPath = "/info-gap"

if (-not (Test-Path -LiteralPath $Tailscale)) {
    throw "Tailscale is not installed at $Tailscale"
}
if (-not (Test-Path -LiteralPath (Join-Path $SiteRoot "index.html"))) {
    throw "Website not found at $SiteRoot"
}

$arguments = @(
    "funnel",
    "--bg",
    "--yes",
    "--https=443",
    "--set-path=$PublicPath",
    $SiteRoot
)
$process = Start-Process `
    -FilePath $Tailscale `
    -ArgumentList $arguments `
    -Verb RunAs `
    -WindowStyle Hidden `
    -Wait `
    -PassThru

if ($process.ExitCode -ne 0) {
    throw "Tailscale Funnel setup failed with exit code $($process.ExitCode)"
}

& $Tailscale funnel status

