@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Static IPv4 (edit here if needed)
set "IP=192.168.100.152"
set "MASK=255.255.255.0"
set "GW=192.168.100.37"
set "DNS=192.168.100.37"
set "LOG=%~dp0set_network.log"

if /i not "%~1"=="elevated" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo Requesting administrator rights. Click Yes on the UAC prompt.
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/k cd /d \"%~dp0\" ^& call \"%~f0\" elevated' -Verb RunAs"
        exit /b
    )
)

echo.
echo ========================================
echo   Set static IP and DNS
echo   Log: %LOG%
echo ========================================
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Not running as administrator.
    echo Right-click this file and choose "Run as administrator".
    goto end
)

>>"%LOG%" echo.
>>"%LOG%" echo [%date% %time%] start

set "IFACE="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$a = Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' } | Select-Object -First 1; if ($a) { $a.Name }" 2^>nul`) do set "IFACE=%%I"

if not defined IFACE (
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$c = Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1; if ($c) { $c.InterfaceAlias }" 2^>nul`) do set "IFACE=%%I"
)

if not defined IFACE set "IFACE=WLAN"

echo Adapter: !IFACE!
echo IP:      %IP%
echo Mask:    %MASK%
echo Gateway: %GW%
echo DNS:     %DNS%
echo.
>>"%LOG%" echo adapter=!IFACE! ip=%IP%

echo [1/2] Setting IP and gateway...
netsh interface ipv4 set address name="!IFACE!" static %IP% %MASK% %GW% 1 >nul 2>>"%LOG%"
set "RC=!errorlevel!"

if !RC! neq 0 (
    echo Trying alias Wi-Fi ...
    netsh interface ipv4 set address name="Wi-Fi" static %IP% %MASK% %GW% 1 >nul 2>>"%LOG%"
    set "RC=!errorlevel!"
    if !RC! equ 0 set "IFACE=Wi-Fi"
)

if !RC! neq 0 (
    echo.
    echo FAILED to set IP/gateway. Error code: !RC!
    echo Log: %LOG%
    echo.
    echo Try manual setup: Win+R, type ncpa.cpl, open IPv4, enter:
    echo   IP %IP%  Mask %MASK%  Gateway %GW%  DNS %DNS%
    goto end
)

echo [2/2] Setting DNS...
netsh interface ipv4 set dnsservers name="!IFACE!" static %DNS% primary >nul 2>>"%LOG%"
set "RC=!errorlevel!"
if !RC! neq 0 (
    echo.
    echo FAILED to set DNS. Error code: !RC!
    goto end
)

echo.
echo SUCCESS. Current config:
netsh interface ipv4 show config name="!IFACE!"
>>"%LOG%" echo [%date% %time%] success

:end
echo.
pause
endlocal
