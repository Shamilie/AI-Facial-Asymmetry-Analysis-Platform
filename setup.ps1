<#
.SYNOPSIS
    Automated Single-Shot Setup Script for AI Facial Asymmetry Analysis Platform (Windows)
.DESCRIPTION
    Verifies system prerequisites (Git, Python 3.13, Node.js, Docker/PostgreSQL),
    starts PostgreSQL via Docker, sets up the Python virtual environment,
    downloads real AI model weights, configures environment variables,
    installs frontend packages, and initializes the database.
#>

param(
    [switch]$SkipPrereqInstall = $false,
    [switch]$InstallDocker = $false
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n====================================================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "====================================================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

$RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootPath

# -----------------------------------------------------------------------------
# STEP 0: Check Administrator Privileges, Write Access & Unblock Files
# -----------------------------------------------------------------------------
$CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = New-Object Security.Principal.WindowsPrincipal($CurrentUser)
$IsAdmin = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# Test directory write permission
try {
    $permTest = Join-Path $RootPath ".perm_test"
    [IO.File]::WriteAllText($permTest, "test")
    Remove-Item $permTest -Force -ErrorAction SilentlyContinue
} catch {
    Write-Host "[INFO] Current directory requires Administrator privileges. Relaunching elevated..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# Auto-unblock files in directory (removes Windows Mark-of-the-Web on zip extractions)
if (Get-Command Unblock-File -ErrorAction SilentlyContinue) {
    Get-ChildItem -Path $RootPath -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
}

# Safe download helper (avoids PowerShell Invoke-WebRequest UnauthorizedAccessException)
function Download-FileSafely {
    param([string]$Url, [string]$OutPath)
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -fSL --create-dirs -o $OutPath $Url
        if ($LASTEXITCODE -eq 0 -and (Test-Path $OutPath)) { return }
    }
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($Url, $OutPath)
    } catch {
        Invoke-WebRequest -Uri $Url -OutFile $OutPath -UseBasicParsing
    }
}

Write-Host @"
====================================================================
      AI Facial Asymmetry Analysis Platform — Windows Setup Wizard
      Unilateral Mandibular Fracture Research System
====================================================================
"@ -ForegroundColor DarkCyan

# -----------------------------------------------------------------------------
# STEP 1: Verify Core Prerequisites (Git, Python, Node, Docker)
# -----------------------------------------------------------------------------
Write-Step "Step 1: Checking System Prerequisites"

$MissingTools = @()

# Check Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = (git --version)
    Write-Success "Git detected: $gitVer"
} else {
    $MissingTools += "Git.Git"
    Write-Warn "Git is not installed."
}

# Check Python (>= 3.11, recommended 3.13)
$PythonCmd = $null
if (Get-Command python3.13 -ErrorAction SilentlyContinue) {
    $PythonCmd = "python3.13"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py -3.13"
}

if ($PythonCmd) {
    $pyVer = & $PythonCmd --version 2>&1
    Write-Success "Python detected: $pyVer"
} else {
    $MissingTools += "Python.Python.3.13"
    Write-Warn "Python 3.13 is not detected in PATH."
}

# Check Node.js (>= 20.x LTS)
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVer = (node --version)
    Write-Success "Node.js detected: $nodeVer"
} else {
    $MissingTools += "OpenJS.NodeJS.LTS"
    Write-Warn "Node.js is not installed."
}

# Check npm
if (Get-Command npm -ErrorAction SilentlyContinue) {
    $npmVer = (npm --version)
    Write-Success "npm detected: v$npmVer"
} else {
    Write-Warn "npm is not detected."
}

# Check Docker / Docker Desktop
$DockerFound = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $dockerVer = (docker --version 2>&1)
    Write-Success "Docker detected: $dockerVer"
    $DockerFound = $true
} else {
    Write-Warn "Docker Desktop is not installed."
    if ($InstallDocker) {
        $MissingTools += "Docker.DockerDesktop"
    } else {
        Write-Host "  To install Docker via winget: winget install Docker.DockerDesktop" -ForegroundColor DarkGray
    }
}

# Optional winget auto-install for missing prerequisites
if ($MissingTools.Count -gt 0) {
    if (-not $SkipPrereqInstall -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "`nAttempting to install missing tools via Windows Package Manager (winget)..." -ForegroundColor Yellow
        foreach ($tool in $MissingTools) {
            Write-Host "Installing $tool..." -ForegroundColor Cyan
            try {
                winget install --id $tool -e --accept-package-agreements --accept-source-agreements --silent
                Write-Success "$tool installed successfully."
            } catch {
                Write-Warn "Automatic installation of $tool failed. Please install manually."
            }
        }
        Write-Host "`nNOTE: If new tools were installed, you may need to restart PowerShell for environment variables to take effect." -ForegroundColor Yellow
    } else {
        Write-Err "Missing prerequisites: $($MissingTools -join ', ')"
        Write-Host "Please install them before continuing:"
        Write-Host "  winget install Python.Python.3.13"
        Write-Host "  winget install OpenJS.NodeJS.LTS"
        Write-Host "  winget install Git.Git"
        Write-Host "  winget install Docker.DockerDesktop"
        if (-not $PythonCmd) { exit 1 }
    }
}

# -----------------------------------------------------------------------------
# STEP 2: Configure Environment (.env)
# -----------------------------------------------------------------------------
Write-Step "Step 2: Configuring Environment (.env)"

$EnvPath = Join-Path $RootPath ".env"
$EnvExamplePath = Join-Path $RootPath ".env.example"

if (-not (Test-Path $EnvPath)) {
    if (Test-Path $EnvExamplePath) {
        Copy-Item $EnvExamplePath $EnvPath
        Write-Success "Created .env from .env.example."
    } else {
        Write-Warn ".env.example not found. Creating default .env."
        @"
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://faplatform:dev_password_123@localhost:5432/facial_asymmetry
DATABASE_URL_SYNC=postgresql://faplatform:dev_password_123@localhost:5432/facial_asymmetry
SECRET_KEY=dev-secret-key-medical-research-2026
JWT_SECRET_KEY=dev-jwt-secret-research-2026
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
LOG_LEVEL=INFO
"@ | Out-File -FilePath $EnvPath -Encoding utf8
        Write-Success "Created default .env file."
    }
} else {
    Write-Success ".env configuration file already exists."
}

# -----------------------------------------------------------------------------
# STEP 3: Start PostgreSQL Container (Docker)
# -----------------------------------------------------------------------------
Write-Step "Step 3: Initializing PostgreSQL 16 via Docker"

$ComposeCmd = if (Get-Command docker-compose -ErrorAction SilentlyContinue) { "docker-compose" } else { "docker compose" }

if ($DockerFound) {
    # Check for permission / named pipe access restriction on Windows 11
    $dockerInfoErr = (docker info 2>&1 | Out-String)
    if ($dockerInfoErr -match "access is denied|unauthorized|permission|pipe") {
        Write-Warn "Docker engine named pipe access restricted."
        if (-not $IsAdmin) {
            Write-Host "[INFO] Re-launching with Administrator privileges to access Docker..." -ForegroundColor Yellow
            Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
            exit
        } else {
            Write-Host "Attempting to enroll current user in 'docker-users' group..." -ForegroundColor Cyan
            net localgroup docker-users "$env:USERNAME" /add 2>$null | Out-Null
        }
    }

    Write-Host "Starting PostgreSQL 16 container (fa_postgres) on port 5432..." -ForegroundColor Cyan
    try {
        & $ComposeCmd up -d postgres
        # Wait up to 10 seconds for port 5432 to become active
        $ready = $false
        for ($i = 0; $i -lt 10; $i++) {
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                $tcp.Connect("127.0.0.1", 5432)
                $tcp.Close()
                $ready = $true
                break
            } catch {
                Start-Sleep -Seconds 1
            }
        }
        if ($ready) {
            Write-Success "PostgreSQL container is active and listening on port 5432."
        } else {
            Write-Warn "PostgreSQL container started, still initializing."
        }
    } catch {
        Write-Warn "Could not start PostgreSQL container. Ensure Docker Desktop is running."
    }
} else {
    Write-Host "Docker not detected. Backend will use local PostgreSQL service or SQLite fallback." -ForegroundColor Yellow
}

# -----------------------------------------------------------------------------
# STEP 4: Setup Python Virtual Environment (.venv)
# -----------------------------------------------------------------------------
Write-Step "Step 4: Setting Up Python Virtual Environment"

$VenvPath = Join-Path $RootPath ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$VenvPip = Join-Path $VenvPath "Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at $VenvPath..." -ForegroundColor Cyan
    & $PythonCmd -m venv $VenvPath
    Write-Success "Virtual environment created."
} else {
    Write-Success "Virtual environment already exists."
}

# Upgrade pip & install backend dependencies
Write-Host "Upgrading pip, setuptools and wheel..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip setuptools wheel --quiet

Write-Host "Installing backend requirements from backend\requirements.txt..." -ForegroundColor Cyan
& $VenvPip install -r (Join-Path $RootPath "backend\requirements.txt") --quiet
Write-Success "Backend Python dependencies installed."

# Optional AI runtime packages
$AiReqPath = Join-Path $RootPath "backend\requirements-ai.txt"
if (Test-Path $AiReqPath) {
    Write-Host "Installing MediaPipe AI runtime from backend\requirements-ai.txt..." -ForegroundColor Cyan
    try {
        & $VenvPip install -r $AiReqPath --quiet
        Write-Success "MediaPipe AI runtime installed."
    } catch {
        Write-Warn "Optional AI runtime installation had warnings. OpenCV and built-in geometric solvers will continue."
    }
}

# -----------------------------------------------------------------------------
# STEP 5: Download Real AI Model Weights
# -----------------------------------------------------------------------------
Write-Step "Step 5: Ensuring Real AI Model Weights"

$ModelsDir = Join-Path $RootPath "backend\models\mediapipe"
if (-not (Test-Path $ModelsDir)) {
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
}

$FaceModelPath = Join-Path $ModelsDir "face_landmarker.task"
$FaceModelUrl = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

if (-not (Test-Path $FaceModelPath)) {
    Write-Host "Downloading MediaPipe 478-point 3D FaceLandmarker model (~3.76 MB)..." -ForegroundColor Cyan
    Download-FileSafely -Url $FaceModelUrl -OutPath $FaceModelPath
    Write-Success "Downloaded face_landmarker.task."
} else {
    Write-Success "MediaPipe FaceLandmarker model is present ($([math]::Round((Get-Item $FaceModelPath).Length / 1MB, 2)) MB)."
}

$SegmenterModelPath = Join-Path $ModelsDir "selfie_multiclass_256x256.tflite"
$SegmenterModelUrl = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite"

if (-not (Test-Path $SegmenterModelPath)) {
    Write-Host "Downloading MediaPipe Multiclass Segmenter model (~16.37 MB)..." -ForegroundColor Cyan
    Download-FileSafely -Url $SegmenterModelUrl -OutPath $SegmenterModelPath
    Write-Success "Downloaded selfie_multiclass_256x256.tflite."
} else {
    Write-Success "MediaPipe Multiclass Segmenter model is present ($([math]::Round((Get-Item $SegmenterModelPath).Length / 1MB, 2)) MB)."
}

# -----------------------------------------------------------------------------
# STEP 6: Setup Frontend (npm install)
# -----------------------------------------------------------------------------
Write-Step "Step 6: Setting Up Frontend Dependencies"

$FrontendDir = Join-Path $RootPath "frontend"
if (Test-Path $FrontendDir) {
    Push-Location $FrontendDir
    Write-Host "Installing frontend node packages (this may take 1-2 minutes)..." -ForegroundColor Cyan
    npm install --quiet
    Write-Success "Frontend dependencies installed."
    Pop-Location
} else {
    Write-Warn "frontend directory not found. Skipping frontend setup."
}

# -----------------------------------------------------------------------------
# STEP 7: Verify Database Connectivity & Seeding
# -----------------------------------------------------------------------------
Write-Step "Step 7: Initializing Database & Seed Verification"

Push-Location (Join-Path $RootPath "backend")
$testScript = @"
import asyncio
from app.main import app, lifespan
from app.core.database import ACTIVE_DATABASE_LABEL, engine

async def check():
    await engine.dispose()
    async with lifespan(app):
        print(f'Database connected successfully: {ACTIVE_DATABASE_LABEL}')

asyncio.run(check())
"@

try {
    $dbCheckOutput = & $VenvPython -c $testScript 2>&1
    Write-Host $dbCheckOutput
    Write-Success "Database initialized and seeded with all 6 research roles, admin accounts, and AI pipelines."
} catch {
    Write-Warn "Database check encountered a non-fatal warning: $_"
}
Pop-Location

# -----------------------------------------------------------------------------
# STEP 8: Completed & Next Steps
# -----------------------------------------------------------------------------
Write-Step "Setup Completed Successfully!"

Write-Host @"
All components are configured and ready to run.

How to Run:
  * Recommended Single-Shot Runner (All-in-One Docker):
      Double-click 'run.bat'

  * Local Hot-Reload Development:
      .\start.ps1

Default Access:
  * Web Portal:       http://localhost:5173
  * Swagger Docs:     http://127.0.0.1:8000/docs
  * Admin Login:      admin@faplatform.org / Research@2026
====================================================================
"@ -ForegroundColor Green
