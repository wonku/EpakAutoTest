param(
    [int]$Events = 10000,
    [int]$ThrottleMs = 200
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $ProjectRoot "reports\scheduled"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogDir "monkey-$Timestamp.log"

Set-Location $ProjectRoot

$env:MOBILE_LOGIN_ENABLED = "true"
$env:MONKEY_EVENT_COUNT = [string]$Events
$env:MONKEY_THROTTLE_MS = [string]$ThrottleMs

"[$(Get-Date -Format s)] Scheduled monkey started" | Tee-Object -FilePath $LogPath
"ProjectRoot=$ProjectRoot" | Tee-Object -FilePath $LogPath -Append
"Events=$Events ThrottleMs=$ThrottleMs" | Tee-Object -FilePath $LogPath -Append

adb devices -l 2>&1 | Tee-Object -FilePath $LogPath -Append
adb shell input keyevent KEYCODE_WAKEUP 2>&1 | Tee-Object -FilePath $LogPath -Append
adb shell wm dismiss-keyguard 2>&1 | Tee-Object -FilePath $LogPath -Append
adb shell svc power stayon true 2>&1 | Tee-Object -FilePath $LogPath -Append

pytest "tests/mobile/test_monkey.py" -m monkey -s --email-report 2>&1 | Tee-Object -FilePath $LogPath -Append
$ExitCode = $LASTEXITCODE

"[$(Get-Date -Format s)] Scheduled monkey finished with exit code $ExitCode" | Tee-Object -FilePath $LogPath -Append
exit $ExitCode
