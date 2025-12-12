@echo off
title FilamentHub - Pro Menu (Batch Starter)

REM Starte PowerShell Menü mit erweiterten Rechten (ohne nervigen Policies)
powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0menu_pro_v3.ps1"

echo.
echo FilamentHub Pro Menü wurde beendet.
pause
