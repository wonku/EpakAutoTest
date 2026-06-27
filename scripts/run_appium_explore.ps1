param(
    [string]$ApkPath = "",
    [string]$DeviceSerial = "",
    [int]$Steps = 100,
    [int]$PauseMs = 500,
    [switch]$EmailReport,
    [switch]$SkipAppiumStart
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$AndroidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$AppiumUrl = if ($env:APPIUM_SERVER_URL) { $env:APPIUM_SERVER_URL.Trim() } else { "http://127.0.0.1:4723" }

$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$env:Path = "$env:ProgramFiles\nodejs;$env:APPDATA\npm;$AndroidSdk\platform-tools;" + $env:Path
Set-Location $ProjectRoot

if ([string]::IsNullOrWhiteSpace($ApkPath)) {
    $ApkPath = Join-Path $ProjectRoot "app-release.apk"
}
$env:MOBILE_APK_PATH = $ApkPath

if (-not [string]::IsNullOrWhiteSpace($DeviceSerial)) {
    $env:MOBILE_DEVICE_SERIAL = $DeviceSerial
}

$env:MOBILE_LOGIN_ENABLED = "true"
$env:APPIUM_EXPLORE_STEPS = [string]$Steps
$env:APPIUM_EXPLORE_PAUSE_MS = [string]$PauseMs

function Test-AppiumRunning {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri "$Url/status" -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-AppiumServer {
    param([string]$Url)
    if (Test-AppiumRunning -Url $Url) {
        Write-Output "Appium already running at $Url"
        return
    }

    Write-Output "Starting Appium server at $Url ..."
    Start-Process -WindowStyle Hidden -FilePath "appium" -ArgumentList "--address", "127.0.0.1", "--port", "4723" | Out-Null

    for ($attempt = 1; $attempt -le 30; $attempt++) {
        Start-Sleep -Seconds 1
        if (Test-AppiumRunning -Url $Url) {
            Write-Output "Appium is ready."
            return
        }
    }

    throw "Appium did not become ready within 30 seconds. Run .\scripts\start_appium.ps1 in another terminal and retry."
}

if (-not $SkipAppiumStart) {
    Start-AppiumServer -Url $AppiumUrl
}

Write-Output "Device list:"
adb devices -l

$pytestArgs = @("tests/mobile/test_appium_explore.py", "-m", "appium", "-s")
if ($EmailReport) {
    $pytestArgs += "--email-report"
}

pytest @pytestArgs
exit $LASTEXITCODE
