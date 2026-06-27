param(
    [switch]$EmailReport
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$env:ESB_UI_HEADLESS = "true"

$pytestArgs = @("tests/test_esbao_mall_ui.py", "-m", "esbao", "-s", "-v")
if ($EmailReport) {
    $pytestArgs += "--email-report"
}

python -m pytest @pytestArgs
exit $LASTEXITCODE
