@echo off
setlocal

set "MOBILE_APK_PATH=%~dp0..\app-release.apk"
set "MONKEY_EVENT_COUNT=5000"
set "MONKEY_THROTTLE_MS=200"

pytest tests\mobile\test_monkey.py -m monkey -s
exit /b %ERRORLEVEL%
