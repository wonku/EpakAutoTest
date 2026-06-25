$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$AndroidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$env:Path = "$env:ProgramFiles\nodejs;$env:APPDATA\npm;$AndroidSdk\platform-tools;" + $env:Path

Write-Output "Starting Appium server at http://127.0.0.1:4723 ..."
Write-Output "ANDROID_HOME=$AndroidSdk"
appium --address 127.0.0.1 --port 4723
