@echo off
rem Dubbelklik om Bridge Oefenen te starten (BEN, tunnel en server).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\start.ps1"
if errorlevel 1 pause
