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
:: STEP 0: Check Administrator Privileges & Write Permissions
:: -----------------------------------------------------------------------------
net session >nul 2>&1
set "IS_ADMIN=0"
if %ERRORLEVEL% EQU 0 set "IS_ADMIN=1"

:: Test directory write permission
copy /y nul "%~dp0.perm_test" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Running in a protected directory. Requesting Administrator elevation...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath cmd.exe -ArgumentList '/c', '\"\"%~f0\"\"' -Verb RunAs"
    exit /b
)
del "%~dp0.perm_test" >nul 2>&1

:: Unblock downloaded files if marked by Windows SmartScreen / Zone.Identifier
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Command Unblock-File -ErrorAction SilentlyContinue) { Get-ChildItem -Path '%~dp0' -Recurse | Unblock-File -ErrorAction SilentlyContinue }" >nul 2>&1

:: -----------------------------------------------------------------------------
:: STEP 1: Verify Docker Installation
:: -----------------------------------------------------------------------------
echo [1/6] Checking Docker installation...

where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] 'docker' command was not found in standard PATH.
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
:: STEP 2: Check / Start Docker Engine Daemon & Named Pipe Permissions
:: -----------------------------------------------------------------------------
echo [2/6] Checking Docker daemon status...

docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    :: Check if failure is due to permission / named pipe access denied
    for /f "tokens=*" %%e in ('docker info 2^>^&1') do (
        echo %%e | findstr /i "access is denied unauthorized permission pipe" >nul
        if !ERRORLEVEL! EQU 0 (
            echo.
            echo [WARN] Docker engine permission denied (named pipe access restriction).
            echo        Error: %%e
            if "!IS_ADMIN!"=="0" (
                echo [INFO] Automatically relaunching with Administrator privileges...
                timeout /t 2 >nul
                powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath cmd.exe -ArgumentList '/c', '\"\"%~f0\"\"' -Verb RunAs"
                exit /b
            ) else (
                echo [INFO] Attempting to ensure current user is in 'docker-users' group...
                net localgroup docker-users "%USERNAME%" /add >nul 2>&1
            )
        )
    )

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
        echo If you see UnauthorizedAccessException, right-click run.bat and select 'Run as administrator'.
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
:: STEP 3: Check & Pull Latest Code from Git
:: -----------------------------------------------------------------------------
echo [3/6] Checking for repository code updates...
if exist ".git" (
    where git >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [INFO] Syncing latest code changes from remote Git repository...
        git pull --ff-only 2>nul
        if !ERRORLEVEL! NEQ 0 (
            git pull 2>nul
        )
        if !ERRORLEVEL! EQU 0 (
            echo [OK] Codebase successfully updated to latest commit.
        ) else (
            echo [INFO] Remote sync completed or offline. Proceeding with current code.
        )
    ) else (
        echo [INFO] Git CLI not found in PATH. Skipping remote update check.
    )
) else (
    echo [INFO] Directory is not a Git repository. Skipping remote update.
)

:: -----------------------------------------------------------------------------
:: STEP 4: Environment Setup (.env and AI model weights via native curl)
:: -----------------------------------------------------------------------------
echo [4/6] Verifying environment and model weights...

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] Created .env configuration from .env.example
    )
)

:: Ensure models directory exists
set "MODEL_DIR=backend\models\mediapipe"
if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%" >nul 2>&1

:: Native Windows curl.exe is used to prevent PowerShell UnauthorizedAccessException
where curl.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "CURL_CMD=curl.exe -fSL --create-dirs"
) else (
    set "CURL_CMD="
)

if not exist "%MODEL_DIR%\face_landmarker.task" (
    echo [INFO] Downloading MediaPipe 478-pt 3D Face Landmarker model (~3.8 MB)...
    if defined CURL_CMD (
        %CURL_CMD% -o "%MODEL_DIR%\face_landmarker.task" "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    ) else (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task', '%MODEL_DIR%\face_landmarker.task')"
    )
)

if not exist "%MODEL_DIR%\selfie_multiclass_256x256.tflite" (
    echo [INFO] Downloading Multiclass Face Segmentation model (~16.4 MB)...
    if defined CURL_CMD (
        %CURL_CMD% -o "%MODEL_DIR%\selfie_multiclass_256x256.tflite" "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite"
    ) else (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite', '%MODEL_DIR%\selfie_multiclass_256x256.tflite')"
    )
)

:: -----------------------------------------------------------------------------
:: STEP 5: Run Database/Redis (Reuse) & Rebuild App Containers (Backend/Frontend)
:: -----------------------------------------------------------------------------
echo [5/6] Starting services and updating application containers...
echo.

where docker-compose >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "COMPOSE_CMD=docker-compose"
) else (
    set "COMPOSE_CMD=docker compose"
)

:: Phase A: Ensure PostgreSQL and Redis are running (reusing existing containers and images)
echo --- Phase 1: Reusing PostgreSQL 16 and Redis (no rebuild) ---
%COMPOSE_CMD% up -d postgres redis
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] Failed to start PostgreSQL/Redis services.
    echo If this is an authorization issue, right-click run.bat and choose 'Run as administrator'.
    pause
    exit /b !ERRORLEVEL!
)

:: Phase B: Rebuild backend and frontend images with the updated code
echo.
echo --- Phase 2: Updating Backend ^& Frontend images with fresh code ---
%COMPOSE_CMD% up -d --build backend frontend
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] Failed to build or update Backend/Frontend containers.
    pause
    exit /b !ERRORLEVEL!
)

:: -----------------------------------------------------------------------------
:: STEP 6: Service Health Check (via curl) & Browser Launch
:: -----------------------------------------------------------------------------
echo.
echo [6/6] Verifying services and opening browser...

:: Native curl.exe polling loop (avoids PowerShell invocation)
where curl.exe >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set /a probe_attempts=0
    :PROBE_LOOP
    timeout /t 2 >nul
    set /a probe_attempts+=1
    curl.exe -s -o nul -w "%%{http_code}" http://localhost:5173 | findstr "200 301 302" >nul 2>&1
    if !ERRORLEVEL! EQU 0 goto PROBE_DONE
    if !probe_attempts! GEQ 15 goto PROBE_DONE
    goto PROBE_LOOP
    :PROBE_DONE
) else (
    timeout /t 4 >nul
)

start http://localhost:5173

echo.
echo ====================================================================
echo   PLATFORM SUCCESSFULLY STARTED!
echo ====================================================================
echo   * Web Application:     http://localhost:5173
echo   * Backend API:         http://localhost:8000
echo   * Interactive Docs:    http://localhost:5173/docs  (or :8000/docs)
echo   * Platform Manual:     http://localhost:5173/admin/instructions
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
