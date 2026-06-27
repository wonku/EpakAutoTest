@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

set "STEPS=5000"
set "PAUSE=500"
if not "%~1"=="" set "STEPS=%~1"
if not "%~2"=="" set "PAUSE=%~2"

set "ANDROID_SDK=%LOCALAPPDATA%\Android\Sdk"
set "ANDROID_HOME=%ANDROID_SDK%"
set "ANDROID_SDK_ROOT=%ANDROID_SDK%"
set "PATH=%ProgramFiles%\nodejs;%APPDATA%\npm;%ANDROID_SDK%\platform-tools;%PATH%"

echo ========================================
echo Appium Random Explore
echo Project: %CD%
echo Steps: %STEPS%  PauseMs: %PAUSE%
echo ========================================
echo.

adb devices -l
if errorlevel 1 (
    echo [ERROR] adb not found. Check Android SDK platform-tools.
    goto :finish
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_appium_explore.ps1" -Steps %STEPS% -PauseMs %PAUSE%
set "EXITCODE=%ERRORLEVEL%"

:finish
echo.
if "%EXITCODE%"=="" set "EXITCODE=0"
echo Finished with exit code %EXITCODE%
echo Latest report: reports\mobile\appium\
echo.
pause
exit /b %EXITCODE%
