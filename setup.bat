@echo off
setlocal
title AI Facial Asymmetry Analysis Platform — Setup

echo ====================================================================
echo   AI Facial Asymmetry Analysis Platform — Windows Single-Shot Setup
echo ====================================================================
echo.

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Setup encountered an issue. See messages above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Setup finished successfully! Press any key to exit.
pause >nul
