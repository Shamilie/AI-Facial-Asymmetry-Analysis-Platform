@echo off
setlocal
title AI Facial Asymmetry Analysis Platform — Full Docker Container Runner

echo ====================================================================
echo   Building and Running Entire Platform in Docker Containers...
echo   (PostgreSQL 16 + Redis + FastAPI Backend + Vite React Frontend)
echo ====================================================================
echo.

cd /d "%~dp0"

where docker-compose >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set COMPOSE_CMD=docker-compose
) else (
    set COMPOSE_CMD=docker compose
)

echo Executing: %COMPOSE_CMD% up --build -d
%COMPOSE_CMD% up --build -d

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Docker build or start failed. Please ensure Docker Desktop is running.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [OK] Containers started successfully!
echo Waiting for frontend to initialize...
timeout /t 3 >nul

start http://localhost:5173

echo.
echo Containers active:
%COMPOSE_CMD% ps
echo.
echo To view live logs:   %COMPOSE_CMD% logs -f
echo To stop containers:  %COMPOSE_CMD% down
echo.
pause
