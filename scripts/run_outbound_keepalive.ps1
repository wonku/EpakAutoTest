param(
    [switch]$EmailReport
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$scriptArgs = @()
if ($EmailReport) {
    $scriptArgs += "--email-report"
}

python (Join-Path $PSScriptRoot "outbound_call_keepalive.py") @scriptArgs
exit $LASTEXITCODE
