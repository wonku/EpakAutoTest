param(
    [int]$Steps = 100,
    [int]$PauseMs = 500
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$AndroidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$LogDir = Join-Path $ProjectRoot "reports\scheduled"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$env:Path = "$env:ProgramFiles\nodejs;$env:APPDATA\npm;$AndroidSdk\platform-tools;" + $env:Path

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogDir "appium-explore-$Timestamp.log"

Set-Location $ProjectRoot

"[$(Get-Date -Format s)] Scheduled Appium explore started" | Tee-Object -FilePath $LogPath
"ProjectRoot=$ProjectRoot" | Tee-Object -FilePath $LogPath -Append
"Steps=$Steps PauseMs=$PauseMs" | Tee-Object -FilePath $LogPath -Append

adb devices -l 2>&1 | Tee-Object -FilePath $LogPath -Append
adb shell input keyevent KEYCODE_WAKEUP 2>&1 | Tee-Object -FilePath $LogPath -Append
adb shell wm dismiss-keyguard 2>&1 | Tee-Object -FilePath $LogPath -Append
adb shell svc power stayon true 2>&1 | Tee-Object -FilePath $LogPath -Append

& (Join-Path $PSScriptRoot "run_appium_explore.ps1") -Steps $Steps -PauseMs $PauseMs -EmailReport 2>&1 |
    Tee-Object -FilePath $LogPath -Append
$ExitCode = $LASTEXITCODE

"[$(Get-Date -Format s)] Scheduled Appium explore finished with exit code $ExitCode" |
    Tee-Object -FilePath $LogPath -Append
exit $ExitCode
