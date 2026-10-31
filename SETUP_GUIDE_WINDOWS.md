# AI Facial Asymmetry Analysis Platform — Windows Setup Guide

Comprehensive setup guide for deploying and running the **AI Facial Asymmetry Analysis Platform** on a new Windows 10/11 system.

---

## 1. Prerequisites & Technology Stack

| Component | Verified Version | Purpose | Installation (winget or Web) |
| :--- | :--- | :--- | :--- |
| **Operating System** | Windows 10 / 11 (64-bit) | Host OS | — |
| **Python** | `>= 3.13.0` (or `3.12.x`) | Backend API, AI inference, numerical engines | `winget install Python.Python.3.13`<br>or [python.org](https://www.python.org/downloads/) |
| **Node.js & npm** | Node `>= 20.x LTS` (e.g. `v22.x`)<br>npm `>= 10.x` | Frontend React + Vite development server | `winget install OpenJS.NodeJS.LTS`<br>or [nodejs.org](https://nodejs.org/) |
| **Git** | `>= 2.40.0` | Version control & repository synchronization | `winget install Git.Git`<br>or [git-scm.com](https://git-scm.com/download/win) |
| **PostgreSQL** *(Recommended)* | `>= 15` or `16` | Primary database with JSONB and relational integrity | `winget install PostgreSQL.PostgreSQL.16`<br>*(Or auto-started in Docker container `fa_postgres`, or SQLite WAL fallback)* |
| **Docker Desktop** *(Recommended)* | Latest | Runs PostgreSQL 16 container, Redis, or entire multi-container stack | `winget install Docker.DockerDesktop`<br>or [docker.com](https://www.docker.com/products/docker-desktop/) |

> [!NOTE]
> The platform features **automatic database detection & Docker orchestration**:
> - Running **`run.bat`** automatically verifies Docker Desktop, creates `.env`, downloads neural models, builds the stack, and starts all 4 containers (`fa_postgres`, `fa_redis`, `fa_backend`, `fa_frontend`) on ports 5432, 6379, 8000, and 5173.
> - For manual development without Docker containers, the backend automatically connects to local PostgreSQL if available or falls back to high-performance SQLite WAL mode (`facial_asymmetry.db`).

---

## 2. Automated Single-Shot Docker Setup & Runner (Recommended)

To set up and run the entire platform on a new Windows machine in a single step:

1. Ensure **Docker Desktop** is installed.
2. In Windows File Explorer, simply double-click **`run.bat`**.
3. The script automatically:
   - Verifies Docker CLI & engine status (starting Docker Desktop if stopped).
   - Configures `.env` from `.env.example`.
   - Verifies and downloads Google MediaPipe neural weights (FaceLandmarker + Multiclass Segmenter).
   - Executes `docker compose up --build -d` building both backend and frontend images.
   - Waits for services to become healthy and opens your browser to **`http://localhost:5173`**.
   - Provides live interactive options to view container logs (`L`), restart (`R`), or stop (`S`).

---

## 3. Manual Step-by-Step Setup

If you prefer installing and configuring each component manually:

### Step 3.1: Clone Repository
```powershell
git clone https://github.com/Shamilie/AI-Facial-Asymmetry-Analysis-Platform.git
cd AI-Facial-Asymmetry-Analysis-Platform
```

### Step 3.2: Configure Environment Variables
```powershell
Copy-Item .env.example .env
```
*(Optionally edit `.env` to add your `GEMINI_API_KEY` for narrative report generation).*

### Step 3.3: Set Up Python Virtual Environment & Backend
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip setuptools wheel

# Install backend dependencies
pip install -r backend\requirements.txt
pip install -r backend\requirements-ai.txt
```

### Step 3.4: Download Real AI Model Weights
Ensure the MediaPipe model weights are placed in `backend\models\mediapipe\`:
```powershell
New-Item -ItemType Directory -Path backend\models\mediapipe -Force

# 1. 478-point 3D FaceLandmarker (~3.76 MB)
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" -OutFile "backend\models\mediapipe\face_landmarker.task"

# 2. Multiclass Image Segmenter (~16.37 MB)
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite" -OutFile "backend\models\mediapipe\selfie_multiclass_256x256.tflite"
```

### Step 3.5: Set Up Frontend
```powershell
cd frontend
npm install
cd ..
```

---

## 4. Platform Launch Options

### Option A: 1-Click Docker Runner (Recommended)
Double-click **`run.bat`** (or execute `.\run.bat` in Command Prompt / PowerShell).

Runs all 4 services inside Docker containers:
- **`fa_postgres`**: PostgreSQL 16 on port `5432`
- **`fa_redis`**: Redis 7 cache & broker on port `6379`
- **`fa_backend`**: FastAPI backend on port `8000`
- **`fa_frontend`**: Nginx Alpine serving React SPA & reverse proxying on port `5173`

### Option B: Local Hybrid Development (PowerShell)
For rapid hot-reloading frontend/backend code without rebuilding Docker images:
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

### Option C: Manual Launch (Separate Terminals)

**Step 1 — Start PostgreSQL (Docker or Native Service):**
```powershell
docker compose up -d postgres
```

**Step 2 — Terminal 1 — Backend:**
```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Step 3 — Terminal 2 — Frontend:**
```powershell
cd frontend
npm run dev
```

---

## 5. Live Configuration & API Keys (Database Table)

API credentials and AI provider configurations can be configured dynamically without restarting the server or managing `.env` files:

1. Log in as an Administrator (`admin@faplatform.org` / `Research@2026`).
2. Navigate to **Administration** -> **System Settings**.
3. Configure your API keys live in the database table:
   - `GEMINI_API_KEY`: Google Gemini Flash / Pro models for multimodal narrative report drafting.
   - `NVIDIA_API_KEY`: NVIDIA NIM API for hardware-accelerated deep inference.
   - `OPENAI_API_KEY`: OpenAI GPT-4o / vision models.
   - `CUSTOM_GPU_API_KEY`: Custom on-premise GPU inference cluster endpoints.
4. Values are masked (`••••••••`), cached in memory for sub-millisecond retrieval, and all updates are recorded with immutable audit log entries.

---

## 5. Seeded User Accounts & Roles

All accounts share the default development password: **`Research@2026`**

| Role | Email | Permissions & Menus Visible |
| :--- | :--- | :--- |
| **System Administrator** | `admin@faplatform.org` | Full platform access, User Management, AI Config, Audit Logs |
| **Principal Investigator** | `pi@faplatform.org` | Study oversight, Protocol Config, Audit Logs, Clinical & AI outputs |
| **Research Coordinator** | `coordinator@faplatform.org` | Patient enrollment, Visit scheduling, Image acquisition, AI analysis |
| **Clinician / Examiner** | `examiner@faplatform.org` | Landmark review & approvals, Physical calibration, Measurement review |
| **Research Analyst** | `analyst@faplatform.org` | Coded records, Measurement results, Reports, Research Analytics |
| **Read-only Researcher** | `readonly@faplatform.org` | Read-only viewing of anonymized patient records & longitudinal measurements |

---

## 6. Troubleshooting & FAQs

### Q1: "Execution of scripts is disabled on this system"
Run PowerShell with bypass permission:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Or simply double-click **`setup.bat`** or **`start.bat`**, which automatically bypass execution restrictions.

### Q2: Port 8000 or Port 5173 is already in use
Find and stop any previous instances running on the port:
```powershell
Get-Process | Where-Object { $_.ProcessName -match "python|node" } | Stop-Process -Force
```

### Q3: How to test that everything works
Run the integrated backend test suite:
```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python -m pytest tests/ -v
```
Expected output: **`12 passed in ~20s`**.
