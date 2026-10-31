"""
Visit management endpoints (Page 6):
  * GET   /visits                             — all study visits across patients
  * GET   /patients/{patient_id}/visits       — visits for a specific patient
  * POST  /patients/{patient_id}/visits       — create/schedule a visit
  * GET   /visits/{visit_id}                  — full visit detail
  * PATCH /visits/{visit_id}                  — update visit dates, status, notes
  * POST  /visits/{visit_id}/clinical-assessment — save clinical examination findings
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import bad_request, not_found, ok
from app.core.security import require_permissions
from app.models.clinical import ClinicalAssessment
from app.models.image import VisitImage
from app.models.measurement import MeasurementStatusEnum
from app.models.patient import Patient
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum
from app.services.audit import record_audit

router = APIRouter(tags=["Visits"])


class VisitCreateRequest(BaseModel):
    visit_type: VisitTypeEnum
    planned_date: date | None = None
    actual_date: date | None = None
    notes: str | None = None


class VisitPatchRequest(BaseModel):
    planned_date: date | None = None
    actual_date: date | None = None
    status: VisitStatusEnum | None = None
    notes: str | None = None
    reason: str | None = None


class ClinicalAssessmentRequest(BaseModel):
    assessment_date: date | None = None
    facial_swelling_grade: str | None = None
    occlusion_status: str | None = None
    maximal_interincisal_opening_mm: float | None = None
    neurosensory_status: str | None = None
    chin_deviation_mm: float | None = None
    chin_deviation_side: str | None = None
    soft_tissue_healing: str | None = None
    pain_score_vas: float | None = None
    complications_present: bool = False
    complication_details: str | None = None
    paired_physical_measurements: dict | None = None
    examiner_notes: str | None = None


def _serialize_visit(v: Visit, patient_code: str | None = None, fracture_side: str | None = None) -> dict[str, Any]:
    imgs = [im for im in v.images if not im.is_deleted]
    ms = [m for m in v.measurements if m.is_current]
    approved_ms = [m for m in ms if m.status == MeasurementStatusEnum.APPROVED]
    image_upload_status = (
        f"{len(imgs)}/4 Uploaded" if len(imgs) < 4 else "All 4 Views Uploaded"
    )
    ai_status = v.ai_jobs[-1].status.value if v.ai_jobs else "NotStarted"
    examiner_review_status = (
        "Approved"
        if (ms and len(approved_ms) == len([m for m in ms if m.right_value is not None]))
        else ("ReviewRequired" if ms else "Pending")
    )
    return {
        "id": str(v.id),
        "patient_id": str(v.patient_id),
        "patient_code": patient_code or (v.patient.patient_code if v.patient else None),
        "fracture_side": fracture_side,
        "visit_type": v.visit_type.value,
        "planned_date": v.planned_date.isoformat() if v.planned_date else None,
        "actual_date": v.actual_date.isoformat() if v.actual_date else None,
        "status": v.status.value,
        "image_count": len(imgs),
        "image_upload_status": image_upload_status,
        "ai_analysis_status": ai_status,
        "examiner_review_status": examiner_review_status,
        "measurement_count": len(ms),
        "approved_measurement_count": len(approved_ms),
        "completion_status": "Completed" if v.status == VisitStatusEnum.COMPLETED else "Incomplete",
        "notes": v.notes,
        "updated_at": (v.updated_at or v.created_at).isoformat(),
    }


@router.get("/visits")
async def list_all_visits(
    status: str | None = Query(default=None),
    visit_type: str | None = Query(default=None),
    patient_id: uuid.UUID | None = Query(default=None),
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Visit)
        .join(Patient, Patient.id == Visit.patient_id)
        .where(Patient.is_deleted.is_(False))
        .options(
            selectinload(Visit.patient).selectinload(Patient.fracture_detail),
            selectinload(Visit.images),
            selectinload(Visit.measurements),
            selectinload(Visit.ai_jobs),
        )
        .order_by(Visit.planned_date.asc())
    )
    if status:
        stmt = stmt.where(Visit.status == status)
    if visit_type:
        stmt = stmt.where(Visit.visit_type == visit_type)
    if patient_id:
        stmt = stmt.where(Visit.patient_id == patient_id)

    visits = list((await db.execute(stmt)).scalars().all())
    return ok(
        [
            _serialize_visit(
                v,
                v.patient.patient_code if v.patient else None,
                v.patient.fracture_detail.fracture_side.value
                if v.patient and v.patient.fracture_detail and v.patient.fracture_detail.fracture_side
                else None,
            )
            for v in visits
        ]
    )


@router.get("/patients/{patient_id}/visits")
async def list_patient_visits(
    patient_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await list_all_visits(patient_id=patient_id, current_user=current_user, db=db)


@router.post("/patients/{patient_id}/visits")
async def create_patient_visit(
    patient_id: uuid.UUID,
    payload: VisitCreateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.VISIT_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pat = (await db.execute(select(Patient).where(Patient.id == patient_id))).scalar_one_or_none()
    if pat is None:
        raise not_found("Patient")
    v = Visit(
        patient_id=patient_id,
        visit_type=payload.visit_type,
        planned_date=payload.planned_date,
        actual_date=payload.actual_date,
        status=VisitStatusEnum.SCHEDULED if payload.planned_date else VisitStatusEnum.PLANNED,
        notes=payload.notes,
        protocol_version_id=pat.protocol_version_id,
    )
    db.add(v)
    await db.flush()
    await record_audit(
        db,
        user=current_user,
        action="visit.create",
        resource_type="visit",
        resource_id=v.id,
        after={"patient_id": str(patient_id), "visit_type": v.visit_type.value},
        request=request,
    )
    return ok({"id": str(v.id), "visit_type": v.visit_type.value, "status": v.status.value})


@router.get("/visits/{visit_id}")
async def get_visit(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Visit)
        .where(Visit.id == visit_id)
        .options(
            selectinload(Visit.patient).selectinload(Patient.fracture_detail),
            selectinload(Visit.patient).selectinload(Patient.surgery_detail),
            selectinload(Visit.images).selectinload(VisitImage.quality_results),
            selectinload(Visit.measurements),
            selectinload(Visit.ai_jobs),
            selectinload(Visit.reconstruction_assets),
        )
    )
    v = (await db.execute(stmt)).scalar_one_or_none()
    if v is None:
        raise not_found("Visit")

    clin = (
        await db.execute(select(ClinicalAssessment).where(ClinicalAssessment.visit_id == visit_id))
    ).scalars().first()

    data = _serialize_visit(
        v,
        v.patient.patient_code if v.patient else None,
        v.patient.fracture_detail.fracture_side.value
        if v.patient and v.patient.fracture_detail and v.patient.fracture_detail.fracture_side
        else None,
    )
    data["surgery_date"] = (
        v.patient.surgery_detail.surgery_date.isoformat()
        if v.patient and v.patient.surgery_detail and v.patient.surgery_detail.surgery_date
        else None
    )
    data["study_status"] = v.patient.study_status.value if v.patient else None
    data["clinical_assessment"] = (
        {
            "id": str(clin.id),
            "assessment_date": clin.assessment_date.isoformat() if clin.assessment_date else None,
            "facial_swelling_grade": clin.facial_swelling_grade,
            "occlusion_status": clin.occlusion_status,
            "maximal_interincisal_opening_mm": clin.maximal_interincisal_opening_mm,
            "neurosensory_status": clin.neurosensory_status,
            "chin_deviation_mm": clin.chin_deviation_mm,
            "chin_deviation_side": clin.chin_deviation_side,
            "soft_tissue_healing": clin.soft_tissue_healing,
            "pain_score_vas": clin.pain_score_vas,
            "complications_present": clin.complications_present,
            "complication_details": clin.complication_details,
            "paired_physical_measurements": clin.paired_physical_measurements,
            "examiner_notes": clin.examiner_notes,
        }
        if clin
        else None
    )
    return ok(data)


@router.patch("/visits/{visit_id}")
async def patch_visit(
    visit_id: uuid.UUID,
    payload: VisitPatchRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.VISIT_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Visit)
        .where(Visit.id == visit_id)
        .options(selectinload(Visit.images), selectinload(Visit.measurements), selectinload(Visit.ai_jobs))
    )
    v = (await db.execute(stmt)).scalar_one_or_none()
    if v is None:
        raise not_found("Visit")

    before = {"status": v.status.value, "actual_date": v.actual_date.isoformat() if v.actual_date else None}

    if payload.status == VisitStatusEnum.COMPLETED:
        # Enforce rule: do not mark a visit Completed unless measurements have been examiner-approved
        approved = [m for m in v.measurements if m.is_current and m.status == MeasurementStatusEnum.APPROVED]
        if not approved:
            raise bad_request(
                "Cannot mark visit Completed until quantitative measurements have been reviewed and approved by an examiner."
            )

    if payload.planned_date is not None:
        v.planned_date = payload.planned_date
    if payload.actual_date is not None:
        v.actual_date = payload.actual_date
    if payload.status is not None:
        v.status = payload.status
    if payload.notes is not None:
        v.notes = payload.notes

    await record_audit(
        db,
        user=current_user,
        action="visit.update",
        resource_type="visit",
        resource_id=v.id,
        before=before,
        after={"status": v.status.value, "actual_date": v.actual_date.isoformat() if v.actual_date else None},
        reason=payload.reason or "Updated visit schedule/status",
        request=request,
    )
    return await get_visit(visit_id, current_user, db)


@router.post("/visits/{visit_id}/clinical-assessment")
async def save_clinical_assessment(
    visit_id: uuid.UUID,
    payload: ClinicalAssessmentRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.VISIT_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    v = (await db.execute(select(Visit).where(Visit.id == visit_id))).scalar_one_or_none()
    if v is None:
        raise not_found("Visit")
    clin = (
        await db.execute(select(ClinicalAssessment).where(ClinicalAssessment.visit_id == visit_id))
    ).scalars().first()
    if clin is None:
        clin = ClinicalAssessment(visit_id=v.id, patient_id=v.patient_id, examiner_id=current_user.id)
        db.add(clin)
    for field_name, val in payload.model_dump().items():
        setattr(clin, field_name, val)
    clin.examiner_id = current_user.id
    await db.flush()
    await record_audit(
        db,
        user=current_user,
        action="visit.clinical_assessment",
        resource_type="clinical_assessment",
        resource_id=clin.id,
        after=payload.model_dump(),
        request=request,
    )
    return await get_visit(visit_id, current_user, db)
