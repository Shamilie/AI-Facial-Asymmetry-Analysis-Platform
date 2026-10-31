<#
.SYNOPSIS
    Single-Click Launcher for AI Facial Asymmetry Analysis Platform (Windows)
.DESCRIPTION
    Launches FastAPI Uvicorn backend and Vite React frontend, then opens the browser.
#>

$RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootPath

$VenvPython = Join-Path $RootPath ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    if (Get-Command python3.13 -ErrorAction SilentlyContinue) {
        $VenvPython = "python3.13"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $VenvPython = "python"
    } else {
        Write-Host "Python environment not detected. Please run setup.bat first." -ForegroundColor Red
        pause
        exit 1
    }
}

Write-Host @"
====================================================================
  Starting AI Facial Asymmetry Analysis Platform...
  Backend API:   http://127.0.0.1:8000 (Docs: http://127.0.0.1:8000/docs)
  Frontend Web:  http://localhost:5173
====================================================================
"@ -ForegroundColor Cyan

# Start Backend Server in a new window
$BackendCmd = "cd /d `"$RootPath\backend`" && `"$VenvPython`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process cmd.exe -ArgumentList "/k title FA Platform Backend (Port 8000) && $BackendCmd"

Start-Sleep -Seconds 2

# Start Frontend Dev Server in a new window
$FrontendCmd = "cd /d `"$RootPath\frontend`" && npm run dev"
Start-Process cmd.exe -ArgumentList "/k title FA Platform Frontend (Port 5173) && $FrontendCmd"

Start-Sleep -Seconds 3

# Open default browser
Start-Process "http://localhost:5173"

Write-Host "`nPlatform started! Both server consoles are running in the background." -ForegroundColor Green
Write-Host "Press Ctrl+C or close the server windows to stop the platform.`n"
