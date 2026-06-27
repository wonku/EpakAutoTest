@echo off
setlocal EnableExtensions EnableDelayedExpansion

if /i not "%~1"=="elevated" (
    net session >nul 2>&1
    if errorlevel 1 (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/k cd /d \"%~dp0\" ^& call \"%~f0\" elevated' -Verb RunAs"
        exit /b
    )
)

set "IFACE=WLAN"
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -First 1).Name" 2^>nul`) do set "IFACE=%%I"

echo Adapter: !IFACE!
netsh interface ipv4 set address name="!IFACE!" source=dhcp
netsh interface ipv4 set dnsservers name="!IFACE!" source=dhcp
netsh interface ipv4 show config name="!IFACE!"
echo.
pause
endlocal
