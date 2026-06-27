@echo off
setlocal
cd /d "%~dp0.."
if not exist reports\junit mkdir reports\junit
set ESB_UI_HEADLESS=true
set PYTEST_ARGS=tests/test_epak_mall_ui.py -m epak -s -v --junitxml=reports/junit/epak-ui.xml
if /I "%SEND_EMAIL_REPORT%"=="true" set PYTEST_ARGS=%PYTEST_ARGS% --email-report
python -m pytest %PYTEST_ARGS%
exit /b %ERRORLEVEL%
