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

set "ARGS=tests/test_esbao_mall_ui.py -m esbao -s -v"

:parse_args
if "%~1"=="" goto run_tests
if /I "%~1"=="--email-report" set "ARGS=%ARGS% --email-report"
if /I "%~1"=="-EmailReport" set "ARGS=%ARGS% --email-report"
if /I "%~1"=="--headed" set "ESB_UI_HEADLESS=false"
if /I "%~1"=="--foreground" set "ESB_UI_HEADLESS=false"
if /I "%~1"=="--headless" set "ESB_UI_HEADLESS=true"
shift
goto parse_args

:run_tests
"%PY%" -m pytest %ARGS%
exit /b %ERRORLEVEL%
