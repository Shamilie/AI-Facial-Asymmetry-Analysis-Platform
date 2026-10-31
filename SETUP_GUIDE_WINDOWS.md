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
> - If Docker is installed, `start.bat` / `start.ps1` automatically boots PostgreSQL 16 in the background (`fa_postgres` container on port 5432).
> - If PostgreSQL is already running natively on port 5432, it connects directly.
> - If neither is available, it gracefully falls back to high-performance local SQLite WAL mode (`facial_asymmetry.db`).
> - You can also run the **entire platform** (PostgreSQL + Redis + FastAPI Backend + Nginx Frontend) in Docker via **`start_docker.bat`**.

---

## 2. Automated Single-Shot Setup (Recommended)

### Method A: 1-Click Double-Click
1. In Windows File Explorer, open the project root folder.
2. Double-click **`setup.bat`**.
3. The wizard will automatically:
   - Verify Python, Node.js, and Git.
   - Create the Python virtual environment (`.venv`).
   - Install all backend dependencies (`backend/requirements.txt` + `backend/requirements-ai.txt`).
   - Download the real Google MediaPipe 478-3D and Image Segmenter neural model weights.
   - Configure `.env` from `.env.example`.
   - Install all frontend npm dependencies (`frontend/package.json`).
   - Initialize and seed the database with all 6 research roles, administrator accounts, and AI pipelines.

### Method B: Via PowerShell Console
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

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

## 4. Starting the Application

### Option A: 1-Click Launch with Docker PostgreSQL (Recommended for Development)
Double-click **`start.bat`** (or execute `.\start.ps1` in PowerShell).

This automatically:
1. Detects Docker and brings up the **PostgreSQL 16** container (`docker compose up -d postgres`).
2. Verifies TCP connectivity on port `5432`.
3. Launches the **FastAPI Python Backend** (`http://127.0.0.1:8000`, Docs: `http://127.0.0.1:8000/docs`).
4. Launches the **Vite React Frontend** (`http://localhost:5173`).
5. Opens your default web browser to the Login page.

### Option B: 1-Click Full Containerized Stack (Production / Isolated Mode)
Double-click **`start_docker.bat`** (or execute `docker compose up --build -d`).

Runs all 4 services inside Docker:
- **`fa_postgres`**: PostgreSQL 16 on port `5432`
- **`fa_redis`**: Redis 7 cache & broker on port `6379`
- **`fa_backend`**: FastAPI backend on port `8000`
- **`fa_frontend`**: Nginx Alpine serving React SPA & reverse proxying on port `5173`

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
