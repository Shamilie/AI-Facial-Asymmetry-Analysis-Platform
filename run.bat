@echo off
setlocal enabledelayedexpansion
title AI Facial Asymmetry Analysis Platform — Docker Runner

echo ====================================================================
echo   AI Facial Asymmetry Analysis Platform
echo   Automated Single-Shot Docker Setup ^& Runner (Windows)
echo ====================================================================
echo.

cd /d "%~dp0"

:: -----------------------------------------------------------------------------
:: STEP 1: Verify Docker Installation
:: -----------------------------------------------------------------------------
echo [1/5] Checking Docker installation...

where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] 'docker' command was not found in PATH.
    echo Checking standard Docker Desktop installation paths...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        set "PATH=%PATH%;%ProgramFiles%\Docker\Docker\resources\bin"
    ) else if exist "%LOCALAPPDATA%\Programs\Docker\Docker Desktop.exe" (
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Docker\Docker\resources\bin"
    ) else (
        echo.
        echo [ERROR] Docker Desktop is not installed on this system.
        echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop/
        echo or run in an elevated PowerShell: winget install Docker.DockerDesktop
        echo.
        pause
        exit /b 1
    )
)

:: -----------------------------------------------------------------------------
:: STEP 2: Check / Start Docker Engine Daemon
:: -----------------------------------------------------------------------------
echo [2/5] Checking Docker daemon status...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Docker daemon is not active. Attempting to start Docker Desktop...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Docker\Docker Desktop.exe" (
        start "" "%LOCALAPPDATA%\Programs\Docker\Docker Desktop.exe"
    )
    
    echo Waiting for Docker engine to initialize (up to 45 seconds)...
    set /a attempts=0
    :WAIT_DOCKER
    timeout /t 3 >nul
    set /a attempts+=1
    docker info >nul 2>&1
    if %ERRORLEVEL% EQU 0 goto DOCKER_READY
    if !attempts! GEQ 15 (
        echo.
        echo [ERROR] Docker daemon did not start in time.
        echo Please ensure Docker Desktop is running and try again.
        echo.
        pause
        exit /b 1
    )
    echo ... waiting for Docker daemon (!attempts!/15)
    goto WAIT_DOCKER
)

:DOCKER_READY
echo [OK] Docker daemon is active and responsive.

:: -----------------------------------------------------------------------------
:: STEP 3: Environment Setup (.env and AI model weights)
:: -----------------------------------------------------------------------------
echo [3/5] Verifying environment and model weights...

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] Created .env configuration from .env.example
    )
)

:: Check if MediaPipe AI model weights exist
set "MODEL_DIR=backend\models\mediapipe"
if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"

if not exist "%MODEL_DIR%\face_landmarker.task" (
    echo [INFO] Downloading MediaPipe 478-pt 3D Face Landmarker model (~3.8 MB)...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task' -OutFile '%MODEL_DIR%\face_landmarker.task'"
)

if not exist "%MODEL_DIR%\selfie_multiclass_256x256.tflite" (
    echo [INFO] Downloading Multiclass Face Segmentation model (~16.4 MB)...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite' -OutFile '%MODEL_DIR%\selfie_multiclass_256x256.tflite'"
)

:: -----------------------------------------------------------------------------
:: STEP 4: Build and Start Containers via Docker Compose
:: -----------------------------------------------------------------------------
echo [4/5] Building and starting all Docker services...
echo       - PostgreSQL 16 Relational + JSONB Database
echo       - Redis 7 Cache ^& Task Broker
echo       - FastAPI Python Backend (Port 8000)
echo       - Vite React Frontend + Nginx (Port 5173)
echo.

where docker-compose >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "COMPOSE_CMD=docker-compose"
) else (
    set "COMPOSE_CMD=docker compose"
)

%COMPOSE_CMD% up --build -d

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Docker Compose failed to build or start containers.
    echo Check the error messages above.
    pause
    exit /b %ERRORLEVEL%
)

:: -----------------------------------------------------------------------------
:: STEP 5: Service Health Check & Browser Launch
:: -----------------------------------------------------------------------------
echo.
echo [5/5] Verifying services and opening browser...

:: Brief wait for Nginx and backend to settle
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ready = $false; for ($i = 0; $i -lt 15; $i++) { try { $res = Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 2; if ($res.StatusCode -eq 200) { $ready = $true; break } } catch { Start-Sleep -Seconds 1 } }; exit $(if ($ready) { 0 } else { 1 })" >nul 2>&1

start http://localhost:5173

echo.
echo ====================================================================
echo   PLATFORM SUCCESSFULLY STARTED!
echo ====================================================================
echo   * Web Application:     http://localhost:5173
echo   * Backend API:         http://localhost:8000
echo   * Interactive Docs:    http://localhost:5173/docs  (or :8000/docs)
echo.
echo   Default Development Accounts:
echo   - Administrator:       admin@faplatform.org     / Research@2026
echo   - Principal Invest.:   pi@faplatform.org        / Research@2026
echo   - Research Coord.:     coordinator@faplatform.org / Research@2026
echo   - Clinician/Examiner:  examiner@faplatform.org  / Research@2026
echo   - Research Analyst:    analyst@faplatform.org   / Research@2026
echo.
echo Container Status:
%COMPOSE_CMD% ps
echo.
echo ====================================================================
echo Options:
echo   [L] View live logs
echo   [S] Stop all platform containers
echo   [R] Restart all platform containers
echo   Press any other key to close this console (containers keep running).
echo ====================================================================
set /p USER_CHOICE="Select an option [L/S/R/Exit]: "

if /i "%USER_CHOICE%"=="L" (
    echo Streaming container logs (Press Ctrl+C to stop logs)...
    %COMPOSE_CMD% logs -f
) else if /i "%USER_CHOICE%"=="S" (
    echo Stopping all containers...
    %COMPOSE_CMD% down
    echo Platform stopped.
    pause
) else if /i "%USER_CHOICE%"=="R" (
    echo Restarting all containers...
    %COMPOSE_CMD% restart
    echo Platform restarted.
    pause
) else (
    echo Containers are running in the background. Enjoy!
)
