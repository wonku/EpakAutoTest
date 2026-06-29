@echo off
setlocal
cd /d "%~dp0.."

if not exist reports\outbound-keepalive mkdir reports\outbound-keepalive

set "SCRIPT_ARGS=scripts\outbound_call_keepalive.py"
if /I "%SEND_EMAIL_REPORT%"=="true" set "SCRIPT_ARGS=%SCRIPT_ARGS% --email-report"

python %SCRIPT_ARGS%
exit /b %ERRORLEVEL%
