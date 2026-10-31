# REST & SSE API Specification (`/api/v1`)

All endpoints return a standardized JSON envelope:
```json
{
  "success": true,
  "data": { ... },
  "meta": { ... }
}
```
Error responses return:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Detailed clinical or validation error message"
  }
}
```

## 1. Authentication & Session Management (`/api/v1/auth`)
- `POST /api/v1/auth/login` — Authenticate with email/password; returns JWT `access_token`, `refresh_token`, and user profile with roles & permissions.
- `POST /api/v1/auth/logout` — Revoke active session and record logout audit event.
- `GET /api/v1/auth/me` — Retrieve current authenticated user profile and RBAC permissions.
- `POST /api/v1/auth/forgot-password` — Generate single-use password reset token.
- `POST /api/v1/auth/reset-password` — Reset password using token.
- `POST /api/v1/auth/change-password` — Change password for authenticated researcher.

## 2. Research Overview Dashboard (`/api/v1/dashboard`)
- `GET /api/v1/dashboard/summary` — Returns 6 KPI card metrics, monthly enrollment chart data, follow-up stage completion chart data, recent patients, upcoming visits, AI job status breakdown, pending examiner reviews, and recent audit activity.

## 3. Patient Management (`/api/v1/patients`)
- `GET /api/v1/patients` — Paginated, sortable, filterable coded patient listing (`search`, `fracture_side`, `study_status`, `analysis_status`).
- `POST /api/v1/patients` — 6-step patient registration wizard submission; creates `Patient`, `PatientConsent`, `FractureRecord`, `SurgicalRecord`, and automatically schedules all 5 longitudinal `StudyVisit` records (`PreOperative`, `PostOp1Week`, `PostOp6Weeks`, `PostOp3Months`, `PostOp6Months`).
- `GET /api/v1/patients/export/csv` — Export authorized coded patient listing as CSV.
- `GET /api/v1/patients/{patient_id}` — Complete patient profile with demographics, consent, fracture, surgery, 5 visits, reports, and audit history.
- `PUT /api/v1/patients/{patient_id}` — Update patient study status or clinical notes.

## 4. Visit Management & Clinical Assessments (`/api/v1/visits`)
- `GET /api/v1/visits` — List all study visits with image, AI, review, and measurement counts.
- `GET /api/v1/visits/{visit_id}` — Detailed visit record with images, quality scores, calibrations, 3D mesh summary, and clinical assessment.
- `PUT /api/v1/visits/{visit_id}` — Update visit dates/status (enforces rule that `Completed` requires approved measurements).
- `PUT /api/v1/visits/{visit_id}/clinical-assessment` — Record swelling, trismus (`interincisal_opening_mm`), occlusion, neurosensory status, and hardware stability.

## 5. Image Acquisition & Quality Assessment (`/api/v1/images`)
- `GET /api/v1/images/visits/{visit_id}` — List all 4 standardized image views (`Frontal`, `RightLateral`, `LeftLateral`, `OPG`) and quality results.
- `POST /api/v1/images/visits/{visit_id}/upload` — Multipart upload with format/dimension/corruption validation and automatic quality assessment.
- `GET /api/v1/images/{image_id}/file` — Stream original or processed image file.
- `POST /api/v1/images/{image_id}/quality-check` — Re-run image quality assessment.
- `POST /api/v1/images/{image_id}/override` — Record manual examiner acceptance/rejection override with mandatory reason.

## 6. AI Pipeline, Provider Registry & SSE Stream (`/api/v1/ai`)
- `GET /api/v1/ai/visits/{visit_id}/pipeline` — Get all 11 pipeline stages and status for a visit.
- `POST /api/v1/ai/visits/{visit_id}/run` — Execute the 11-stage AI pipeline for a visit.
- `GET /api/v1/ai/visits/{visit_id}/stream` — Server-Sent Events (SSE) real-time stage progress stream.
- `GET /api/v1/ai/jobs` — Execution monitor KPIs and filterable job queue.
- `POST /api/v1/ai/jobs/{job_id}/retry` — Retry a specific stage job.
- `POST /api/v1/ai/jobs/{job_id}/cancel` — Cancel a queued/running stage job.
- `GET /api/v1/ai/providers` — List all configured AI provider adapters.
- `POST /api/v1/ai/providers` — Register a new task-specific AI provider adapter.
- `PUT /api/v1/ai/providers/{provider_id}` — Update provider adapter settings.
- `POST /api/v1/ai/providers/{provider_id}/test-connection` — Validate provider connectivity and compatibility.
- `POST /api/v1/ai/providers/{provider_id}/test-inference` — Run synthetic test inference on the adapter.

## 7. Landmark Review & Dual-Coordinate Audit (`/api/v1/landmarks`)
- `GET /api/v1/landmarks/definitions` — List protocol landmark definitions.
- `GET /api/v1/landmarks/visits/{visit_id}` — List all landmarks grouped by image view with AI predicted and examiner adjusted coordinates.
- `PUT /api/v1/landmarks/{landmark_id}/adjust` — Save examiner coordinate adjustment, approval, or `NotIdentifiable` status without overwriting `predicted_x`/`predicted_y`.
- `POST /api/v1/landmarks/images/{image_id}` — Add a permitted protocol landmark to an image.
- `POST /api/v1/landmarks/visits/{visit_id}/approve-all` — Batch approve landmarks for a visit or view.

## 8. 3D Reconstruction & Mesh Export (`/api/v1/reconstruction`)
- `GET /api/v1/reconstruction/visits/{visit_id}` — Retrieve 3D face mesh vertices, faces, 3D landmarks, geodesic paths, and coverage status.
- `POST /api/v1/reconstruction/visits/{visit_id}/generate` — Synthesize or regenerate 3D mesh for a visit.
- `GET /api/v1/reconstruction/visits/{visit_id}/export/{fmt}` — Download `.obj` or `.ply` 3D mesh file.

## 9. Physical Calibration (`/api/v1/calibration`)
- `GET /api/v1/calibration/visits/{visit_id}` — List calibrations for a visit.
- `POST /api/v1/calibration/visits/{visit_id}` — Create view-specific calibration (`mm_per_pixel = known_mm / measured_px`), archive prior version, and recalculate visit measurements.

## 10. Quantitative Measurements & Follow-Up (`/api/v1/measurements`)
- `GET /api/v1/measurements/visits/{visit_id}` — Retrieve all visit measurements, summary counts, and provenance metadata.
- `POST /api/v1/measurements/visits/{visit_id}/recalculate` — Re-run `MeasurementEngine` for the visit.
- `POST /api/v1/measurements/{measurement_id}/approve` — Approve or reject an individual measurement.
- `POST /api/v1/measurements/visits/{visit_id}/approve-batch` — Batch approve valid measurements and update visit completion status.
- `GET /api/v1/measurements/visits/{visit_id}/export` — Export visit measurements in `csv`, `xlsx`, or `json`.
- `GET /api/v1/measurements/patients/{patient_id}/follow-up` — Retrieve 5-visit longitudinal series, images, 3D mesh statuses, and clinical assessments.

## 11. Reports & Analytics (`/api/v1/reports`, `/api/v1/analytics`)
- `GET /api/v1/reports` — List generated 13-section research reports.
- `POST /api/v1/reports/generate` — Generate a new 13-section report (`PDF`, `CSV`, `XLSX`, `JSON`, `OBJ`, `PLY`).
- `GET /api/v1/reports/{report_id}/download/{fmt}` — Download report artifact in requested format.
- `GET /api/v1/reports/cohort/export` — Export full cohort dataset (`csv`, `xlsx`, `json`).
- `GET /api/v1/analytics/overview` — Cohort distributions, histograms, missing-data audit, `ICC(2,1)`, `Bland–Altman`, and `CV%`.

## 12. Administration (`/api/v1/admin`, `/api/v1/notifications`)
- `GET /api/v1/admin/users`, `POST /api/v1/admin/users`, `PUT /api/v1/admin/users/{id}`, `POST /api/v1/admin/users/{id}/reset-access`
- `GET /api/v1/admin/audit-logs`
- `GET /api/v1/admin/protocols`, `POST /api/v1/admin/protocols`
- `GET /api/v1/admin/settings`
- `GET /api/v1/notifications`, `POST /api/v1/notifications/{id}/read`
