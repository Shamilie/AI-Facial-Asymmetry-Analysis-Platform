# AI Facial Asymmetry Analysis Platform

A production-oriented clinical research web application for longitudinal quantitative analysis of facial and mandibular asymmetry in patients with **unilateral mandibular fractures treated by fixation** across five standardized study visits:

1. **Pre-operative (`PreOperative`)**
2. **Post-operative – 1 week (`PostOp1Week`)**
3. **Post-operative – 6 weeks (`PostOp6Weeks`)**
4. **Post-operative – 3 months (`PostOp3Months`)**
5. **Post-operative – 6 months (`PostOp6Months`)**

> **Research Measurement & Documentation Disclaimer**: This software is strictly intended for clinical research measurement and documentation. Quantitative outputs do not constitute a medical diagnosis, treatment recommendation, or substitute for clinical judgment.

---

## Key Capabilities

- **4 Standardized Multi-Modal Views per Visit**: Standardized Frontal facial photograph, Right Lateral facial photograph, Left Lateral facial photograph, and Orthopantomogram (OPG).
- **11-Stage AI Processing Pipeline with Real-Time SSE Updates**: Task-specific provider adapters for `MediaPipe`, `OpenAI`, `NVIDIA NIM/Triton`, `CustomGPU`, `LocalModel` (PyTorch/ONNX), and deterministic `Demo` fallback.
- **Interactive SVG/Canvas Landmark Review & Dual-Coordinate Audit Trail**: Drag-to-refine landmarks with zoom/pan controls while permanently preserving original AI predictions (`predicted_x`, `predicted_y`) alongside examiner adjustments (`examiner_x`, `examiner_y`) and review reasons.
- **View-Specific Physical Calibration Engine**: Interactive two-point pixel ruler (`mm_per_pixel = known_marker_length_mm / measured_marker_length_px`), OPG magnification & regional distortion factors, and strict rejection of generic screen PPI (`1 mm = 3.78 px`) assumptions.
- **Three.js 3D Face Reconstruction & Dijkstra Geodesic Surface Paths**: Interactive 3D mesh viewport with coverage quality grading (`Complete`, `Partial`, `LowConfidence`, `Failed`, `RequiresReview`) and `.OBJ` / `.PLY` export.
- **Validated Bilateral Asymmetry Engine & Biostatistical Analytics**: Computes `|R - L|`, `Asymmetry Index (%) = |R - L| / (R + L) * 100`, `ICC(2,1)`, `Bland–Altman` bias & 95% Limits of Agreement, and `CV%`.
- **13-Section Research Reports & Multi-Format Export**: Generates downloadable `PDF`, `CSV`, `Excel (.xlsx)`, `JSON`, `OBJ`, and `PLY` reports.
- **6-Role RBAC & Immutable Audit Logging**: Backend-enforced permissions and append-only `AuditLog` protected by database immutability listeners.

---

## Quick Start (Windows)

### 1-Click Single-Shot Docker Runner (Recommended)
Double-click **`run.bat`** (or execute `.\run.bat` in Command Prompt / PowerShell).

This automatically:
1. Checks and starts Docker Desktop (if not active).
2. Syncs latest commits from Git on every rerun (`git pull`).
3. Sets up `.env` and downloads MediaPipe AI models.
4. Intelligently orchestrates containers:
   - **Reuses** `fa_postgres` (PostgreSQL 16) and `fa_redis` images/containers without recreation.
   - **Rebuilds and updates** `fa_backend` and `fa_frontend` with the latest code.
5. Opens your browser to **`http://localhost:5173`**.

---

### Manual Launch (Separate Terminals)

#### 1. Start the FastAPI Backend
```powershell
cd backend
python3.13 -m pip install -r requirements.txt
python3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the React + Vite Frontend
```powershell
cd frontend
npm install
npm run dev
```

### 3. Sign In (`http://localhost:5173`)
Use any of the 6 seeded research accounts (Password: `Research@2026`):
- `admin@faplatform.org` (System Administrator)
- `pi@faplatform.org` (Principal Investigator)
- `coordinator@faplatform.org` (Research Coordinator)
- `examiner@faplatform.org` (Clinician / Examiner)
- `analyst@faplatform.org` (Research Analyst)
- `readonly@faplatform.org` (Read-only Researcher)

---

## Documentation Index

- [System Architecture](docs/architecture.md)
- [Database Design (27 Tables)](docs/database-design.md)
- [REST & SSE API Specification](docs/api-specification.md)
- [AI Model Configuration & Privacy Guide](docs/ai-model-configuration.md)
- [Measurement & Biostatistical Methodology](docs/measurement-methodology.md)
- [Local Windows Setup Guide](docs/setup-guide.md)
- [Implementation Status Matrix](IMPLEMENTATION_STATUS.md)
