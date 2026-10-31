<#
.SYNOPSIS
    Single-Click Launcher for AI Facial Asymmetry Analysis Platform (Windows)
.DESCRIPTION
    Ensures PostgreSQL is up in Docker, launches FastAPI backend & Vite frontend,
    then opens the browser.
#>

param(
    [switch]$DockerAll = $false
)

$RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootPath

# -----------------------------------------------------------------------------
# Check Compose Command (docker-compose vs docker compose)
# -----------------------------------------------------------------------------
$ComposeCmd = if (Get-Command docker-compose -ErrorAction SilentlyContinue) { "docker-compose" } else { "docker compose" }

# -----------------------------------------------------------------------------
# Mode 1: Full Docker Containerized Stack (-DockerAll)
# -----------------------------------------------------------------------------
if ($DockerAll) {
    Write-Host @"
====================================================================
  Building and Starting All Services in Docker Containers...
  PostgreSQL 16 + Redis + FastAPI Backend + Vite React Frontend
====================================================================
"@ -ForegroundColor Cyan

    & $ComposeCmd up --build -d
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:5173"
    Write-Host "`nAll containers are active! Access the platform at http://localhost:5173" -ForegroundColor Green
    exit 0
}

# -----------------------------------------------------------------------------
# Mode 2: Hybrid Dev (Docker PostgreSQL + Local Hot-Reload Dev Servers)
# -----------------------------------------------------------------------------
Write-Host @"
====================================================================
  Starting AI Facial Asymmetry Analysis Platform
  PostgreSQL Database:  localhost:5432 (Docker / Local)
  Backend API:          http://127.0.0.1:8000 (Docs: /docs)
  Frontend Web UI:      http://localhost:5173
====================================================================
"@ -ForegroundColor Cyan

# Step 1: Ensure PostgreSQL container is running via Docker
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Ensuring PostgreSQL 16 container is running in Docker..." -ForegroundColor Cyan
    try {
        & $ComposeCmd up -d postgres
    } catch {
        Write-Host "[WARN] Docker daemon not reachable. Checking local service..." -ForegroundColor Yellow
    }
}

# Step 2: Check port 5432 readiness
Write-Host "Verifying PostgreSQL connectivity on port 5432..." -ForegroundColor Cyan
$pgReady = $false
for ($i = 0; $i -lt 10; $i++) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 5432)
        $tcp.Close()
        $pgReady = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($pgReady) {
    Write-Host "[OK] PostgreSQL is healthy and accepting connections on port 5432." -ForegroundColor Green
} else {
    Write-Host "[INFO] Port 5432 not responding. Backend will use local SQLite WAL fallback." -ForegroundColor Yellow
}

# Step 3: Check Python environment
$VenvPython = Join-Path $RootPath ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    if (Get-Command python3.13 -ErrorAction SilentlyContinue) {
        $VenvPython = "python3.13"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $VenvPython = "python"
    } else {
        Write-Host "[ERROR] Python environment not detected. Please run setup.bat first." -ForegroundColor Red
        pause
        exit 1
    }
}

# Step 4: Start Backend Server in a dedicated window
Write-Host "Starting FastAPI Uvicorn backend server on port 8000..." -ForegroundColor Cyan
$BackendCmd = "cd /d `"$RootPath\backend`" && `"$VenvPython`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process cmd.exe -ArgumentList "/k title FA Platform Backend (Port 8000) && $BackendCmd"

Start-Sleep -Seconds 2

# Step 5: Start Frontend Server in a dedicated window
Write-Host "Starting Vite React frontend server on port 5173..." -ForegroundColor Cyan
$FrontendCmd = "cd /d `"$RootPath\frontend`" && npm run dev"
Start-Process cmd.exe -ArgumentList "/k title FA Platform Frontend (Port 5173) && $FrontendCmd"

Start-Sleep -Seconds 3

# Step 6: Launch default browser
Start-Process "http://localhost:5173"

Write-Host @"

[OK] Platform successfully started!
  * Frontend: http://localhost:5173
  * Swagger:  http://127.0.0.1:8000/docs

Server console windows are running in the background.
Close the console windows or press Ctrl+C inside them to stop.
"@ -ForegroundColor Green
