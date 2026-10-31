"""
Reports and Exports endpoints (Page 16):
  * POST /reports/generate             — generate a patient-level or cohort-level report
  * GET  /reports                      — list reports with filters
  * GET  /reports/{report_id}          — full report payload
  * GET  /reports/{report_id}/download — download in PDF, CSV, Excel, JSON, OBJ or PLY
  * GET  /reports/cohort/export        — direct cohort data export (CSV/Excel/JSON/PDF)
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.reporting.summary import deterministic_summary
from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import bad_request, not_found, ok
from app.core.security import require_permissions
from app.models.calibration import CalibrationRecord
from app.models.image import VisitImage
from app.models.landmark import LandmarkPrediction, PredictionStatusEnum
from app.models.measurement import Measurement
from app.models.patient import Patient
from app.models.protocol import ProtocolVersion
from app.models.reconstruction import ReconstructionAsset
from app.models.report import (
    ExportFormatEnum,
    Report,
    ReportExport,
    ReportStatusEnum,
    ReportTypeEnum,
)
from app.models.visit import Visit, VisitTypeEnum
from app.services.audit import record_audit
from app.services.report_exporter import (
    RESEARCH_DISCLAIMER,
    build_csv_bytes,
    build_excel_bytes,
    build_pdf_bytes,
)
from app.services.storage import get_storage

router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportGenerateRequest(BaseModel):
    patient_id: uuid.UUID
    visit_id: uuid.UUID | None = None
    report_type: str = "PatientSummary"
    title: str | None = None
    approved_only: bool = False


async def _assemble_patient_report_payload(
    db: AsyncSession,
    patient_id: uuid.UUID,
    visit_id: uuid.UUID | None,
    approved_only: bool = False,
) -> tuple[Patient, Visit | None, dict[str, Any]]:
    stmt = (
        select(Patient)
        .where(Patient.id == patient_id)
        .options(
            selectinload(Patient.consents),
            selectinload(Patient.fracture_detail),
            selectinload(Patient.surgery_detail),
            selectinload(Patient.visits).selectinload(Visit.images).selectinload(VisitImage.quality_results),
            selectinload(Patient.visits).selectinload(Visit.measurements).selectinload(Measurement.measurement_definition),
        )
    )
    patient = (await db.execute(stmt)).scalar_one_or_none()
    if patient is None:
        raise not_found("Patient")

    visit = None
    if visit_id:
        visit = next((v for v in patient.visits if v.id == visit_id), None)
    elif patient.visits:
        visit = patient.visits[0]

    proto = (
        await db.execute(select(ProtocolVersion).where(ProtocolVersion.is_current.is_(True)))
    ).scalars().first()

    # Gather images & quality for the selected visit
    images_payload = []
    landmark_counts = {"total": 0, "predicted": 0, "reviewed": 0, "approved": 0, "not_identifiable": 0}
    cals_payload = []
    measurements_payload = []

    if visit:
        for im in visit.images:
            if im.is_deleted:
                continue
            q = im.quality_results[-1] if im.quality_results else None
            images_payload.append(
                {
                    "image_type": im.image_type.value,
                    "width": im.width,
                    "height": im.height,
                    "acceptance_status": im.acceptance_status,
                    "quality_status": q.status.value if q else "NotAssessed",
                    "issues": q.issues if q else [],
                }
            )
            preds = list(
                (
                    await db.execute(
                        select(LandmarkPrediction).where(
                            LandmarkPrediction.image_id == im.id,
                            LandmarkPrediction.is_current.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for pr in preds:
                landmark_counts["total"] += 1
                if pr.status == PredictionStatusEnum.PREDICTED:
                    landmark_counts["predicted"] += 1
                elif pr.status == PredictionStatusEnum.REVIEWED:
                    landmark_counts["reviewed"] += 1
                elif pr.status == PredictionStatusEnum.APPROVED:
                    landmark_counts["approved"] += 1
                elif pr.status == PredictionStatusEnum.NOT_IDENTIFIABLE:
                    landmark_counts["not_identifiable"] += 1

        cals = list(
            (
                await db.execute(
                    select(CalibrationRecord).where(
                        CalibrationRecord.visit_id == visit.id,
                        CalibrationRecord.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        cals_payload = [
            {
                "calibration_type": c.calibration_type.value,
                "reference_marker_type": c.reference_marker_type,
                "mm_per_pixel": c.mm_per_pixel,
                "is_physical": c.is_physical,
                "same_plane_confirmed": c.same_plane_confirmed,
                "calibration_method": c.calibration_method,
            }
            for c in cals
        ]

        for m in sorted(
            [m for m in visit.measurements if m.is_current],
            key=lambda x: x.measurement_definition.display_order if x.measurement_definition else 999,
        ):
            if approved_only and m.status.value != "Approved":
                continue
            measurements_payload.append(
                {
                    "code": m.measurement_definition.code if m.measurement_definition else "",
                    "name": m.measurement_definition.name if m.measurement_definition else "",
                    "right_value": m.right_value,
                    "left_value": m.left_value,
                    "absolute_difference": m.absolute_difference,
                    "asymmetry_index": m.asymmetry_index,
                    "unit": m.unit,
                    "source_image_type": m.source_image_type,
                    "method": m.method.value,
                    "status": m.status.value,
                    "model_name": m.model_name,
                    "model_version": m.model_version,
                    "warnings": m.warnings or [],
                }
            )

    # Follow-up longitudinal summary across all 5 visits
    v_order = [
        VisitTypeEnum.PRE_OPERATIVE,
        VisitTypeEnum.POST_OP_1_WEEK,
        VisitTypeEnum.POST_OP_6_WEEKS,
        VisitTypeEnum.POST_OP_3_MONTHS,
        VisitTypeEnum.POST_OP_6_MONTHS,
    ]
    follow_up_summary = []
    for vt in v_order:
        v_item = next((x for x in patient.visits if x.visit_type == vt), None)
        if not v_item:
            continue
        cur_ms = [m for m in v_item.measurements if m.is_current]
        ais = [m.asymmetry_index for m in cur_ms if m.asymmetry_index is not None]
        follow_up_summary.append(
            {
                "visit_type": vt.value,
                "status": v_item.status.value,
                "measurement_count": len(cur_ms),
                "approved_count": sum(1 for m in cur_ms if m.status.value == "Approved"),
                "mean_asymmetry_index": round(sum(ais) / len(ais), 2) if ais else None,
            }
        )

    consent = patient.consents[0] if patient.consents else None
    narrative = deterministic_summary(
        {
            "patient_code": patient.patient_code,
            "visit_label": visit.visit_type.value if visit else "All Visits",
            "measurements": measurements_payload,
        }
    )

    payload = {
        "patient": {
            "id": str(patient.id),
            "patient_code": patient.patient_code,
            "fracture_side": patient.fracture_detail.fracture_side.value if patient.fracture_detail and patient.fracture_detail.fracture_side else "N/A",
            "fracture_classification": patient.fracture_detail.fracture_classification if patient.fracture_detail else "N/A",
            "fixation_type": patient.surgery_detail.fixation_type if patient.surgery_detail else "N/A",
            "surgery_date": patient.surgery_detail.surgery_date.isoformat() if patient.surgery_detail and patient.surgery_detail.surgery_date else "N/A",
            "consent_status": consent.consent_status.value if consent else "Obtained",
            "is_synthetic": patient.is_synthetic,
        },
        "study": {
            "protocol_title": "Longitudinal Facial Asymmetry Analysis in Unilateral Mandibular Fractures (UMF-ASYM-2026)",
            "protocol_version": proto.version_number if proto else "1.0",
        },
        "visit": (
            {
                "id": str(visit.id),
                "visit_type": visit.visit_type.value,
                "planned_date": visit.planned_date.isoformat() if visit.planned_date else None,
                "actual_date": visit.actual_date.isoformat() if visit.actual_date else None,
                "status": visit.status.value,
            }
            if visit
            else {}
        ),
        "images": images_payload,
        "landmark_summary": landmark_counts,
        "calibrations": cals_payload,
        "measurements": measurements_payload,
        "follow_up_summary": follow_up_summary,
        "summary_text": narrative,
        "disclaimer": RESEARCH_DISCLAIMER,
        "limitations": [
            "Frontal and lateral photographs require view-specific physical calibration in the measured anatomical plane.",
            "OPG panoramic radiographs exhibit regional magnification and horizontal distortion; pixel spacing alone does not correct distortion.",
            "3D surface geodesic paths approximate flexible tape measurements and require paired physical validation.",
            "Outputs are for research documentation only and must not be used as a diagnosis or clinical treatment recommendation.",
        ],
    }
    return patient, visit, payload


def _serialize_report(r: Report) -> dict[str, Any]:
    rid = str(r.id)
    content = r.content or {}
    return {
        "id": rid,
        "patient_id": str(r.patient_id),
        "patient_code": r.patient.patient_code if r.patient else (content.get("patient", {}) or {}).get("patient_code", "SYNTH"),
        "visit_id": str(r.visit_id) if r.visit_id else None,
        "report_code": f"RPT-{rid[:8].upper()}",
        "report_type": r.report_type.value,
        "title": r.title,
        "status": r.status.value,
        "ai_provider": "Demo",
        "model_version": "demo-1.0.0",
        "summary_text": content.get("summary_text", r.title),
        "content": content,
        "content_json": {
            **content,
            "section_13_research_disclaimer": content.get("disclaimer", RESEARCH_DISCLAIMER),
        },
        "generated_by_email": r.generator.email if r.generator else None,
        "created_at": r.created_at.isoformat(),
        "downloads": {
            "pdf": f"/api/v1/reports/{rid}/download?format=PDF",
            "csv": f"/api/v1/reports/{rid}/download?format=CSV",
            "xlsx": f"/api/v1/reports/{rid}/download?format=Excel",
            "json": f"/api/v1/reports/{rid}/download?format=JSON",
            "obj": f"/api/v1/reports/{rid}/download?format=OBJ",
            "ply": f"/api/v1/reports/{rid}/download?format=PLY",
        },
    }


@router.post("/generate")
async def generate_report(
    req: ReportGenerateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.REPORT_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    patient, visit, payload = await _assemble_patient_report_payload(
        db, req.patient_id, req.visit_id, req.approved_only
    )
    title = req.title or (
        f"{patient.patient_code} — {visit.visit_type.value if visit else 'Longitudinal'} Quantitative Research Report"
    )
    payload["title"] = title

    rt_map = {
        "LongitudinalResearchReport": ReportTypeEnum.PATIENT_SUMMARY,
        "SingleVisitSummary": ReportTypeEnum.VISIT_ANALYSIS,
        "ExaminerSignOffDossier": ReportTypeEnum.PATIENT_SUMMARY,
    }
    rt_enum = rt_map.get(req.report_type)
    if rt_enum is None:
        try:
            rt_enum = ReportTypeEnum(req.report_type)
        except ValueError:
            rt_enum = ReportTypeEnum.PATIENT_SUMMARY

    rpt = Report(
        patient_id=patient.id,
        visit_id=visit.id if visit else None,
        report_type=rt_enum,
        title=title,
        content=payload,
        generated_by=current_user.id,
        protocol_version_id=patient.protocol_version_id,
        status=ReportStatusEnum.GENERATED,
    )
    db.add(rpt)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="report.generate",
        resource_type="report",
        resource_id=rpt.id,
        after={"patient_code": patient.patient_code, "title": title},
        request=request,
    )
    return ok(_serialize_report(rpt), message="Research report generated")


@router.get("")
async def list_reports(
    patient_id: uuid.UUID | None = Query(default=None),
    report_type: str | None = Query(default=None),
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Report).order_by(Report.created_at.desc()).limit(100)
    if patient_id:
        stmt = stmt.where(Report.patient_id == patient_id)
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    rows = list((await db.execute(stmt)).scalars().all())
    return ok([_serialize_report(r) for r in rows])


@router.get("/cohort/export")
async def export_cohort_dataset(
    format: str = Query(default="csv", pattern="^(csv|excel|json)$"),
    approved_only: bool = Query(default=False),
    fracture_side: str | None = Query(default=None),
    request: Request = None,  # type: ignore[assignment]
    current_user: Any = Depends(require_permissions(P.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = (
        select(Measurement, Visit, Patient)
        .join(Visit, Visit.id == Measurement.visit_id)
        .join(Patient, Patient.id == Visit.patient_id)
        .where(Measurement.is_current.is_(True), Patient.is_deleted.is_(False))
        .options(
            selectinload(Measurement.measurement_definition),
            selectinload(Patient.fracture_detail),
        )
        .order_by(Patient.patient_code.asc(), Visit.planned_date.asc())
    )
    rows = []
    for m, v, p in (await db.execute(stmt)).all():
        if approved_only and m.status.value != "Approved":
            continue
        p_side = p.fracture_detail.fracture_side.value if p.fracture_detail and p.fracture_detail.fracture_side else None
        if fracture_side and p_side != fracture_side:
            continue
        rows.append(
            {
                "patient_code": p.patient_code,
                "is_synthetic": p.is_synthetic,
                "fracture_side": p_side,
                "visit_type": v.visit_type.value,
                "visit_status": v.status.value,
                "measurement_code": m.measurement_definition.code if m.measurement_definition else "",
                "measurement_name": m.measurement_definition.name if m.measurement_definition else "",
                "right_value": m.right_value,
                "left_value": m.left_value,
                "absolute_difference": m.absolute_difference,
                "asymmetry_index_pct": m.asymmetry_index,
                "unit": m.unit,
                "source_view": m.source_image_type,
                "provenance_method": m.method.value,
                "validation_status": m.status.value,
                "model_version": m.model_version,
            }
        )

    await record_audit(
        db,
        user=current_user,
        action="report.cohort_export",
        resource_type="cohort_dataset",
        after={"format": format, "approved_only": approved_only, "row_count": len(rows)},
        request=request,
    )
    if format == "json":
        body = json.dumps({"disclaimer": RESEARCH_DISCLAIMER, "count": len(rows), "records": rows}, indent=2).encode("utf-8")
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="cohort_measurements_export.json"'},
        )
    if format == "excel":
        return Response(
            content=build_excel_bytes("Cohort_Measurements", rows, {"approved_only": approved_only}),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="cohort_measurements_export.xlsx"'},
        )
    return Response(
        content=build_csv_bytes(rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cohort_measurements_export.csv"'},
    )


@router.get("/{report_id}")
async def get_report(
    report_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    r = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if r is None:
        raise not_found("Report")
    return ok(_serialize_report(r))


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    format: str = Query(default="PDF", pattern="^(PDF|CSV|Excel|JSON|OBJ|PLY)$"),
    request: Request = None,  # type: ignore[assignment]
    current_user: Any = Depends(require_permissions(P.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    r = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if r is None:
        raise not_found("Report")

    _, visit, payload = await _assemble_patient_report_payload(db, r.patient_id, r.visit_id)
    payload["title"] = r.title

    storage = get_storage()
    fmt = ExportFormatEnum(format)

    if fmt == ExportFormatEnum.PDF:
        raw = build_pdf_bytes(payload)
        ext, mime = "pdf", "application/pdf"
    elif fmt == ExportFormatEnum.CSV:
        raw = build_csv_bytes(payload.get("measurements", []))
        ext, mime = "csv", "text/csv"
    elif fmt == ExportFormatEnum.EXCEL:
        raw = build_excel_bytes("Report_Measurements", payload.get("measurements", []), payload.get("patient"))
        ext, mime = "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == ExportFormatEnum.JSON:
        raw = json.dumps(payload, indent=2, default=str).encode("utf-8")
        ext, mime = "json", "application/json"
    else:
        # OBJ or PLY mesh export for the report's visit
        if not visit:
            raise bad_request("No visit associated with this report for 3D mesh export.")
        asset = (
            await db.execute(
                select(ReconstructionAsset)
                .where(ReconstructionAsset.visit_id == visit.id)
                .order_by(ReconstructionAsset.created_at.desc())
            )
        ).scalars().first()
        if asset is None:
            raise bad_request("No 3D mesh available for this visit.")
        obj_str = storage.read(asset.file_path).decode("utf-8")
        if fmt == ExportFormatEnum.PLY:
            from app.ai.reconstruction.mesh import parse_obj, to_ply

            verts, faces = parse_obj(obj_str)
            raw = to_ply(verts, faces, comment="RESEARCH EXPORT MESH").encode("utf-8")
            ext, mime = "ply", "application/octet-stream"
        else:
            raw = obj_str.encode("utf-8")
            ext, mime = "obj", "application/octet-stream"

    saved_key = storage.save("reports", raw, ext, subdir=str(r.patient_id))
    exp = ReportExport(
        report_id=r.id,
        export_format=fmt,
        file_path=saved_key,
        file_size=len(raw),
        exported_by=current_user.id,
    )
    r.status = ReportStatusEnum.EXPORTED
    db.add(exp)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="report.export",
        resource_type="report",
        resource_id=r.id,
        after={"format": fmt.value, "file_size": len(raw)},
        request=request,
    )
    return Response(
        content=raw,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="report_{r.id}.{ext}"'},
    )
