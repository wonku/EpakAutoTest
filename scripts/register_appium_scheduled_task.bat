@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_appium_scheduled_task.ps1" -StartTime 03:00 -Steps 100
pause
