@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" -c "import greenlet" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] greenlet is blocked by Application Control Policy.
    echo         Playwright UI tests cannot run on this machine.
    echo         Ask IT to allow: Python\Lib\site-packages\greenlet\*.pyd
    echo         Self-check: "%PY%" -c "import greenlet"
    echo.
    exit /b 2
)

set ESB_UI_HEADLESS=true
set "ARGS=tests/test_epak_mall_ui.py -m epak -s -v"
if /I "%~1"=="--email-report" set "ARGS=%ARGS% --email-report"
if /I "%~1"=="-EmailReport" set "ARGS=%ARGS% --email-report"

"%PY%" -m pytest %ARGS%
exit /b %ERRORLEVEL%
