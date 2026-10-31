# Local Windows Setup & Execution Guide

## 1. Prerequisites

- **OS**: Windows 10 / 11
- **Python**: Python 3.13 (`python3.13` / `pip3.13`)
- **Node.js**: Node.js 20+ and npm 9+
- **Optional Docker**: Docker Desktop (if running PostgreSQL 16 + Redis 7 containers via `docker-compose.yml`; local SQLite async mode works out-of-the-box with zero external services).

## 2. Environment Configuration

Copy `.env.example` to `.env` in the project root (already pre-created for local development):
```powershell
Copy-Item .env.example .env
```

## 3. Backend Startup (FastAPI + SQLAlchemy 2.x + Seed Data)

Open PowerShell in `backend/`:
```powershell
cd backend
python3.13 -m pip install -r requirements.txt
python3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
On first startup, the backend automatically:
1. Creates all 27 database tables (or run `alembic upgrade head` when targeting PostgreSQL).
2. Seeds the 6 RBAC roles and 6 demo user accounts.
3. Seeds active study protocol `UMF-ASYM-2026` v1.0, 23 landmark definitions, 14 measurement definitions, and 7 task-specific AI provider configurations.
4. Generates 6 synthetic unilateral mandibular fracture patients (`SYNTH-UMF-001` through `SYNTH-UMF-006`) with synthetic Frontal, Right Lateral, Left Lateral, and OPG images, landmarks, calibrations, 3D meshes (`.obj`/`.ply`), validated measurements, and a 13-section PDF/Excel/CSV/JSON report.

## 4. Frontend Startup (React + TypeScript + Vite)

Open a second PowerShell terminal in `frontend/`:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser. Vite proxies `/api/v1` requests directly to `http://localhost:8000`.

## 5. Demo Accounts (Password for all accounts: `Research@2026`)

| Role | Email | Password |
|---|---|---|
| **System Administrator** | `admin@faplatform.org` | `Research@2026` |
| **Principal Investigator** | `pi@faplatform.org` | `Research@2026` |
| **Research Coordinator** | `coordinator@faplatform.org` | `Research@2026` |
| **Clinician / Examiner** | `examiner@faplatform.org` | `Research@2026` |
| **Research Analyst** | `analyst@faplatform.org` | `Research@2026` |
| **Read-only Researcher** | `readonly@faplatform.org` | `Research@2026` |

## 6. Running Automated Tests

### Backend Pytest Suite
```powershell
cd backend
python3.13 -m pytest -v
```

### Frontend Vitest & Production Build
```powershell
cd frontend
npm test
npm run build
```
