param(
    [string]$ApkPath = "",
    [string]$PackageName = "",
    [string]$DeviceSerial = "",
    [int]$Events = 5000,
    [int]$ThrottleMs = 200,
    [switch]$EmailReport
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

if ([string]::IsNullOrWhiteSpace($ApkPath)) {
    $ApkPath = Join-Path $ProjectRoot "app-release.apk"
}

$env:MOBILE_APK_PATH = $ApkPath
$env:MONKEY_EVENT_COUNT = [string]$Events
$env:MONKEY_THROTTLE_MS = [string]$ThrottleMs

if (-not [string]::IsNullOrWhiteSpace($PackageName)) {
    $env:MOBILE_PACKAGE_NAME = $PackageName
}

if (-not [string]::IsNullOrWhiteSpace($DeviceSerial)) {
    $env:MOBILE_DEVICE_SERIAL = $DeviceSerial
}

$pytestArgs = @("tests/mobile/test_monkey.py", "-m", "monkey", "-s")
if ($EmailReport) {
    $pytestArgs += "--email-report"
}

pytest @pytestArgs
exit $LASTEXITCODE
