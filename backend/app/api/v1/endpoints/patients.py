"""
Patient management endpoints:
  * GET  /patients                             — searchable, filterable, sortable listing
  * GET  /patients/export                      — CSV/Excel export of authorized patient listing
  * POST /patients                             — 6-step registration wizard + automatic 5-visit creation
  * GET  /patients/{patient_id}                — complete patient record
  * PUT  /patients/{patient_id}                — update patient record / save draft
  * GET  /patients/{patient_id}/overview       — workspace overview (Page 5)
  * GET  /patients/{patient_id}/follow-up-comparison — longitudinal comparison (Page 13)
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import bad_request, conflict, not_found, ok, paginated
from app.core.security import has_permission, require_permissions
from app.models.audit import AuditLog
from app.models.clinical import ClinicalAssessment
from app.models.image import VisitImage
from app.models.measurement import Measurement, MeasurementDefinition
from app.models.patient import (
    ConsentStatusEnum,
    FractureDetail,
    FractureSideEnum,
    Patient,
    PatientConsent,
    SexEnum,
    StudyStatusEnum,
    SurgeryDetail,
)
from app.models.protocol import ProtocolVersion
from app.models.reconstruction import ReconstructionAsset
from app.models.report import Report
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum
from app.services.audit import record_audit
from app.services.protocol_catalog import VISIT_SCHEDULE
from app.services.report_exporter import build_csv_bytes, build_excel_bytes

router = APIRouter(prefix="/patients", tags=["Patients"])

VISIT_STAGE_ORDER = [
    VisitTypeEnum.PRE_OPERATIVE,
    VisitTypeEnum.POST_OP_1_WEEK,
    VisitTypeEnum.POST_OP_6_WEEKS,
    VisitTypeEnum.POST_OP_3_MONTHS,
    VisitTypeEnum.POST_OP_6_MONTHS,
]

VISIT_LABELS = {
    "PreOperative": "Pre-operative",
    "PostOp1Week": "1 Week",
    "PostOp6Weeks": "6 Weeks",
    "PostOp3Months": "3 Months",
    "PostOp6Months": "6 Months",
}


class ConsentInput(BaseModel):
    consent_status: ConsentStatusEnum = ConsentStatusEnum.OBTAINED
    consent_date: date | None = None
    consent_document_ref: str | None = None


class FractureInput(BaseModel):
    fracture_side: FractureSideEnum = FractureSideEnum.LEFT
    fracture_classification: str = Field(..., min_length=2)
    fracture_location: str = Field(..., min_length=2)
    injury_date: date | None = None
    injury_mechanism: str | None = None
    associated_fractures: str | None = None
    clinical_notes: str | None = None


class SurgeryInput(BaseModel):
    surgery_date: date
    fixation_type: str = Field(..., min_length=2)
    surgical_approach: str | None = None
    plate_details: str | None = None
    surgeon_name: str | None = None
    operative_notes: str | None = None


class PlannedVisitInput(BaseModel):
    visit_type: VisitTypeEnum
    planned_date: date | None = None
    actual_date: date | None = None


class PatientCreateRequest(BaseModel):
    patient_code: str = Field(..., min_length=3, max_length=100)
    hospital_id: str | None = None
    date_of_birth: date | None = None
    age_at_enrollment: int | None = Field(default=None, ge=0, le=120)
    sex: SexEnum | None = SexEnum.NOT_COLLECTED
    enrollment_date: date | None = None
    is_draft: bool = False
    is_synthetic: bool = False
    consent: ConsentInput = Field(default_factory=ConsentInput)
    fracture: FractureInput | None = None
    surgery: SurgeryInput | None = None
    visit_schedule: list[PlannedVisitInput] | None = None


class PatientUpdateRequest(BaseModel):
    hospital_id: str | None = None
    age_at_enrollment: int | None = None
    sex: SexEnum | None = None
    enrollment_date: date | None = None
    study_status: StudyStatusEnum | None = None
    consent: ConsentInput | None = None
    fracture: FractureInput | None = None
    surgery: SurgeryInput | None = None
    reason: str | None = None


def _serialize_patient_row(p: Patient, can_see_identifiers: bool) -> dict[str, Any]:
    visits = sorted(
        p.visits,
        key=lambda v: VISIT_STAGE_ORDER.index(v.visit_type) if v.visit_type in VISIT_STAGE_ORDER else 99,
    )
    completed_visits = [v for v in visits if v.status == VisitStatusEnum.COMPLETED]
    review_visits = [v for v in visits if v.status == VisitStatusEnum.REVIEW_REQUIRED]
    current_stage = completed_visits[-1].visit_type.value if completed_visits else (visits[0].visit_type.value if visits else "PreOperative")
    analysis_status = (
        "ReviewRequired"
        if review_visits
        else ("Completed" if completed_visits else "Pending")
    )
    consent = p.consents[0] if p.consents else None
    return {
        "id": str(p.id),
        "patient_code": p.patient_code,
        "hospital_id": p.hospital_id if can_see_identifiers else None,
        "age_at_enrollment": p.age_at_enrollment,
        "sex": p.sex.value if p.sex else "NotCollected",
        "fracture_side": p.fracture_detail.fracture_side.value if p.fracture_detail and p.fracture_detail.fracture_side else None,
        "fracture_type": p.fracture_detail.fracture_classification if p.fracture_detail else None,
        "fracture_location": p.fracture_detail.fracture_location if p.fracture_detail else None,
        "surgery_date": p.surgery_detail.surgery_date.isoformat() if p.surgery_detail and p.surgery_detail.surgery_date else None,
        "fixation_type": p.surgery_detail.fixation_type if p.surgery_detail else None,
        "surgeon_name": p.surgery_detail.surgeon_name if p.surgery_detail else None,
        "enrollment_date": p.enrollment_date.isoformat() if p.enrollment_date else None,
        "study_status": p.study_status.value,
        "consent_status": consent.consent_status.value if consent else "Pending",
        "current_follow_up_stage": current_stage,
        "completed_visits_count": len(completed_visits),
        "total_visits_count": len(visits),
        "analysis_status": analysis_status,
        "is_synthetic": p.is_synthetic,
        "updated_at": (p.updated_at or p.created_at).isoformat(),
    }


@router.get("")
async def list_patients(
    search: str | None = Query(default=None),
    fracture_side: str | None = Query(default=None),
    study_status: str | None = Query(default=None),
    analysis_status: str | None = Query(default=None),
    enrolled_from: date | None = Query(default=None),
    enrolled_to: date | None = Query(default=None),
    sort_by: str = Query(default="patient_code"),
    sort_dir: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Patient)
        .where(Patient.is_deleted.is_(False))
        .options(
            selectinload(Patient.consents),
            selectinload(Patient.fracture_detail),
            selectinload(Patient.surgery_detail),
            selectinload(Patient.visits),
        )
    )
    if search:
        stmt = stmt.where(Patient.patient_code.ilike(f"%{search.strip()}%"))
    if study_status:
        stmt = stmt.where(Patient.study_status == study_status)
    if enrolled_from:
        stmt = stmt.where(Patient.enrollment_date >= enrolled_from)
    if enrolled_to:
        stmt = stmt.where(Patient.enrollment_date <= enrolled_to)

    can_id = has_permission(current_user, P.PATIENT_IDENTIFIERS)
    rows = [_serialize_patient_row(p, can_id) for p in (await db.execute(stmt)).scalars().all()]

    if fracture_side:
        rows = [r for r in rows if r["fracture_side"] == fracture_side]
    if analysis_status:
        rows = [r for r in rows if r["analysis_status"] == analysis_status]

    reverse = sort_dir.lower() == "desc"
    rows.sort(key=lambda r: str(r.get(sort_by) or ""), reverse=reverse)

    total = len(rows)
    start = (page - 1) * page_size
    return paginated(rows[start : start + page_size], total, page, page_size)


@router.get("/export")
async def export_patients(
    format: str = Query(default="csv", pattern="^(csv|excel)$"),
    request: Request = None,  # type: ignore[assignment]
    current_user: Any = Depends(require_permissions(P.PATIENT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    stmt = (
        select(Patient)
        .where(Patient.is_deleted.is_(False))
        .options(
            selectinload(Patient.consents),
            selectinload(Patient.fracture_detail),
            selectinload(Patient.surgery_detail),
            selectinload(Patient.visits),
        )
        .order_by(Patient.patient_code.asc())
    )
    rows = [_serialize_patient_row(p, False) for p in (await db.execute(stmt)).scalars().all()]
    await record_audit(
        db,
        user=current_user,
        action="patient.export_listing",
        resource_type="patient",
        after={"format": format, "row_count": len(rows)},
        request=request,
    )
    if format == "excel":
        content = build_excel_bytes("Patients", rows, {"exported_by": current_user.email})
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="coded_patients_export.xlsx"'},
        )
    content = build_csv_bytes(rows)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="coded_patients_export.csv"'},
    )


@router.post("")
async def create_patient(
    payload: PatientCreateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.PATIENT_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    code = payload.patient_code.strip().upper()
    existing = (await db.execute(select(Patient).where(Patient.patient_code == code))).scalar_one_or_none()
    if existing is not None:
        raise conflict(f"Patient code '{code}' already exists")

    if not payload.is_draft and payload.consent.consent_status != ConsentStatusEnum.OBTAINED:
        raise bad_request("Participant informed consent must be Obtained before enrolling an active patient record.")

    proto = (
        await db.execute(select(ProtocolVersion).where(ProtocolVersion.is_current.is_(True)))
    ).scalars().first()

    enroll_dt = payload.enrollment_date or date.today()
    patient = Patient(
        patient_code=code,
        hospital_id=payload.hospital_id,
        date_of_birth=payload.date_of_birth,
        age_at_enrollment=payload.age_at_enrollment,
        sex=payload.sex or SexEnum.NOT_COLLECTED,
        enrollment_date=enroll_dt,
        study_status=StudyStatusEnum.DRAFT if payload.is_draft else StudyStatusEnum.ENROLLED,
        created_by=current_user.id,
        is_synthetic=payload.is_synthetic,
        protocol_version_id=proto.id if proto else None,
    )
    db.add(patient)
    await db.flush()

    db.add(
        PatientConsent(
            patient_id=patient.id,
            consent_status=payload.consent.consent_status,
            consent_date=payload.consent.consent_date or enroll_dt,
            consent_document_ref=payload.consent.consent_document_ref,
        )
    )
    if payload.fracture:
        db.add(
            FractureDetail(
                patient_id=patient.id,
                fracture_side=payload.fracture.fracture_side,
                fracture_classification=payload.fracture.fracture_classification,
                fracture_location=payload.fracture.fracture_location,
                injury_date=payload.fracture.injury_date,
                injury_mechanism=payload.fracture.injury_mechanism,
                associated_fractures=payload.fracture.associated_fractures,
                clinical_notes=payload.fracture.clinical_notes,
            )
        )
    surg_dt = payload.surgery.surgery_date if payload.surgery else enroll_dt
    if payload.surgery:
        db.add(
            SurgeryDetail(
                patient_id=patient.id,
                surgery_date=payload.surgery.surgery_date,
                fixation_type=payload.surgery.fixation_type,
                surgical_approach=payload.surgery.surgical_approach,
                plate_details=payload.surgery.plate_details,
                surgeon_name=payload.surgery.surgeon_name,
                operative_notes=payload.surgery.operative_notes,
            )
        )

    # Automatically generate the 5 study visits anchored to surgery_date
    custom_dates = {v.visit_type: v for v in (payload.visit_schedule or [])}
    visit_enums = [
        VisitTypeEnum.PRE_OPERATIVE,
        VisitTypeEnum.POST_OP_1_WEEK,
        VisitTypeEnum.POST_OP_6_WEEKS,
        VisitTypeEnum.POST_OP_3_MONTHS,
        VisitTypeEnum.POST_OP_6_MONTHS,
    ]
    created_visits = []
    for idx, sched in enumerate(VISIT_SCHEDULE):
        vt = visit_enums[idx]
        custom = custom_dates.get(vt)
        planned = (custom.planned_date if custom and custom.planned_date else (surg_dt + timedelta(days=sched["offset_days"])))
        actual = custom.actual_date if custom else None
        v = Visit(
            patient_id=patient.id,
            visit_type=vt,
            planned_date=planned,
            actual_date=actual,
            status=VisitStatusEnum.SCHEDULED if idx == 0 else VisitStatusEnum.PLANNED,
            protocol_version_id=proto.id if proto else None,
            notes=f"Auto-scheduled {sched['label']} visit",
        )
        db.add(v)
        created_visits.append(v)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="patient.create",
        resource_type="patient",
        resource_id=patient.id,
        after={"patient_code": patient.patient_code, "visits_created": len(created_visits)},
        request=request,
    )
    return ok(
        {
            "id": str(patient.id),
            "patient_code": patient.patient_code,
            "study_status": patient.study_status.value,
            "visits": [
                {
                    "id": str(v.id),
                    "visit_type": v.visit_type.value,
                    "planned_date": v.planned_date.isoformat() if v.planned_date else None,
                    "status": v.status.value,
                }
                for v in created_visits
            ],
        },
        message="Patient registered and 5 longitudinal visits scheduled",
    )


async def _load_full_patient(db: AsyncSession, patient_id: uuid.UUID) -> Patient:
    stmt = (
        select(Patient)
        .where(Patient.id == patient_id, Patient.is_deleted.is_(False))
        .options(
            selectinload(Patient.consents),
            selectinload(Patient.fracture_detail),
            selectinload(Patient.surgery_detail),
            selectinload(Patient.visits).selectinload(Visit.images).selectinload(VisitImage.quality_results),
            selectinload(Patient.visits).selectinload(Visit.measurements),
            selectinload(Patient.visits).selectinload(Visit.ai_jobs),
            selectinload(Patient.visits).selectinload(Visit.reconstruction_assets),
        )
    )
    p = (await db.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise not_found("Patient")
    return p


@router.get("/{patient_id}")
async def get_patient(
    patient_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    p = await _load_full_patient(db, patient_id)
    can_id = has_permission(current_user, P.PATIENT_IDENTIFIERS)
    consent = p.consents[0] if p.consents else None
    visits = sorted(
        p.visits,
        key=lambda v: VISIT_STAGE_ORDER.index(v.visit_type) if v.visit_type in VISIT_STAGE_ORDER else 99,
    )
    return ok(
        {
            **_serialize_patient_row(p, can_id),
            "consent": (
                {
                    "consent_status": consent.consent_status.value,
                    "consent_date": consent.consent_date.isoformat() if consent.consent_date else None,
                    "consent_document_ref": consent.consent_document_ref,
                }
                if consent
                else None
            ),
            "fracture_detail": (
                {
                    "fracture_side": p.fracture_detail.fracture_side.value if p.fracture_detail.fracture_side else None,
                    "fracture_classification": p.fracture_detail.fracture_classification,
                    "fracture_location": p.fracture_detail.fracture_location,
                    "injury_date": p.fracture_detail.injury_date.isoformat() if p.fracture_detail.injury_date else None,
                    "injury_mechanism": p.fracture_detail.injury_mechanism,
                    "associated_fractures": p.fracture_detail.associated_fractures,
                    "clinical_notes": p.fracture_detail.clinical_notes,
                }
                if p.fracture_detail
                else None
            ),
            "surgery_detail": (
                {
                    "surgery_date": p.surgery_detail.surgery_date.isoformat() if p.surgery_detail.surgery_date else None,
                    "fixation_type": p.surgery_detail.fixation_type,
                    "surgical_approach": p.surgery_detail.surgical_approach,
                    "plate_details": p.surgery_detail.plate_details,
                    "surgeon_name": p.surgery_detail.surgeon_name,
                    "operative_notes": p.surgery_detail.operative_notes,
                }
                if p.surgery_detail
                else None
            ),
            "visits": [
                {
                    "id": str(v.id),
                    "visit_type": v.visit_type.value,
                    "label": VISIT_LABELS.get(v.visit_type.value, v.visit_type.value),
                    "planned_date": v.planned_date.isoformat() if v.planned_date else None,
                    "actual_date": v.actual_date.isoformat() if v.actual_date else None,
                    "status": v.status.value,
                    "image_count": sum(1 for im in v.images if not im.is_deleted),
                    "measurement_count": sum(1 for m in v.measurements if m.is_current),
                    "approved_measurement_count": sum(1 for m in v.measurements if m.is_current and m.status.value == "Approved"),
                    "has_3d_mesh": len(v.reconstruction_assets) > 0,
                    "notes": v.notes,
                }
                for v in visits
            ],
        }
    )


@router.put("/{patient_id}")
async def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.PATIENT_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    p = await _load_full_patient(db, patient_id)
    before = {"study_status": p.study_status.value, "age": p.age_at_enrollment}
    if payload.hospital_id is not None:
        p.hospital_id = payload.hospital_id
    if payload.age_at_enrollment is not None:
        p.age_at_enrollment = payload.age_at_enrollment
    if payload.sex is not None:
        p.sex = payload.sex
    if payload.enrollment_date is not None:
        p.enrollment_date = payload.enrollment_date
    if payload.study_status is not None:
        p.study_status = payload.study_status
    if payload.fracture and p.fracture_detail:
        p.fracture_detail.fracture_side = payload.fracture.fracture_side
        p.fracture_detail.fracture_classification = payload.fracture.fracture_classification
        p.fracture_detail.fracture_location = payload.fracture.fracture_location
        p.fracture_detail.injury_date = payload.fracture.injury_date
        p.fracture_detail.injury_mechanism = payload.fracture.injury_mechanism
        p.fracture_detail.associated_fractures = payload.fracture.associated_fractures
        p.fracture_detail.clinical_notes = payload.fracture.clinical_notes
    if payload.surgery and p.surgery_detail:
        p.surgery_detail.surgery_date = payload.surgery.surgery_date
        p.surgery_detail.fixation_type = payload.surgery.fixation_type
        p.surgery_detail.surgical_approach = payload.surgery.surgical_approach
        p.surgery_detail.plate_details = payload.surgery.plate_details
        p.surgery_detail.surgeon_name = payload.surgery.surgeon_name
        p.surgery_detail.operative_notes = payload.surgery.operative_notes

    await record_audit(
        db,
        user=current_user,
        action="patient.update",
        resource_type="patient",
        resource_id=p.id,
        before=before,
        after={"study_status": p.study_status.value, "age": p.age_at_enrollment},
        reason=payload.reason or "Updated patient record",
        request=request,
    )
    return await get_patient(patient_id, current_user, db)


@router.get("/{patient_id}/overview")
async def get_patient_overview(
    patient_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    base_resp = await get_patient(patient_id, current_user, db)
    pdata = base_resp["data"]

    rpts = list(
        (
            await db.execute(
                select(Report).where(Report.patient_id == patient_id).order_by(Report.created_at.desc()).limit(10)
            )
        )
        .scalars()
        .all()
    )
    audits = list(
        (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.resource_id == patient_id)
                .order_by(AuditLog.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )

    pending_tasks = []
    for v in pdata["visits"]:
        if v["image_count"] < 4 and v["status"] in ("Planned", "Scheduled", "ImagesPending"):
            pending_tasks.append({"type": "image_upload", "visit_id": v["id"], "message": f"Upload remaining images for {v['label']}"})
        if v["status"] == "ReviewRequired":
            pending_tasks.append({"type": "examiner_review", "visit_id": v["id"], "message": f"Examiner review & measurement approval required for {v['label']}"})

    return ok(
        {
            **pdata,
            "pending_tasks": pending_tasks,
            "recent_reports": [
                {
                    "id": str(r.id),
                    "title": r.title,
                    "report_type": r.report_type.value,
                    "status": r.status.value,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rpts
            ],
            "audit_history": [
                {
                    "id": str(a.id),
                    "action": a.action,
                    "resource_type": a.resource_type,
                    "user_email": a.user.email if a.user else "system",
                    "reason": a.reason,
                    "created_at": a.created_at.isoformat(),
                }
                for a in audits
            ],
        }
    )


@router.get("/{patient_id}/follow-up-comparison")
async def get_follow_up_comparison(
    patient_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Longitudinal patient comparison across all 5 visits (Page 13).

    Never interpolates missing measurements. Clearly flags missing visit values.
    """
    p = await _load_full_patient(db, patient_id)
    m_defs = list(
        (await db.execute(select(MeasurementDefinition).order_by(MeasurementDefinition.display_order.asc())))
        .scalars()
        .all()
    )
    clin_rows = list(
        (await db.execute(select(ClinicalAssessment).where(ClinicalAssessment.patient_id == patient_id)))
        .scalars()
        .all()
    )
    clin_by_visit = {c.visit_id: c for c in clin_rows}

    visits_by_type = {v.visit_type: v for v in p.visits}
    timeline = []
    for vt in VISIT_STAGE_ORDER:
        v = visits_by_type.get(vt)
        label = VISIT_LABELS[vt.value]
        if v is None:
            timeline.append(
                {
                    "visit_type": vt.value,
                    "label": label,
                    "visit_id": None,
                    "status": "Missing",
                    "planned_date": None,
                    "actual_date": None,
                    "images": [],
                    "has_3d_mesh": False,
                    "clinical_assessment": None,
                    "measurements": {},
                }
            )
            continue

        ms_by_code = {}
        for m in v.measurements:
            if not m.is_current or not m.measurement_definition:
                continue
            code = m.measurement_definition.code
            ms_by_code[code] = {
                "measurement_id": str(m.id),
                "right_value": m.right_value,
                "left_value": m.left_value,
                "absolute_difference": m.absolute_difference,
                "asymmetry_index": m.asymmetry_index,
                "unit": m.unit,
                "method": m.method.value,
                "status": m.status.value,
                "is_unscaled": m.is_unscaled,
            }
        clin = clin_by_visit.get(v.id)
        timeline.append(
            {
                "visit_type": vt.value,
                "label": label,
                "visit_id": str(v.id),
                "status": v.status.value,
                "planned_date": v.planned_date.isoformat() if v.planned_date else None,
                "actual_date": v.actual_date.isoformat() if v.actual_date else None,
                "images": [
                    {
                        "id": str(im.id),
                        "image_type": im.image_type.value,
                        "acceptance_status": im.acceptance_status,
                    }
                    for im in v.images
                    if not im.is_deleted
                ],
                "has_3d_mesh": len(v.reconstruction_assets) > 0,
                "mesh_asset_id": str(v.reconstruction_assets[0].id) if v.reconstruction_assets else None,
                "clinical_assessment": (
                    {
                        "facial_swelling_grade": clin.facial_swelling_grade,
                        "occlusion_status": clin.occlusion_status,
                        "maximal_interincisal_opening_mm": clin.maximal_interincisal_opening_mm,
                        "neurosensory_status": clin.neurosensory_status,
                        "chin_deviation_mm": clin.chin_deviation_mm,
                        "pain_score_vas": clin.pain_score_vas,
                        "paired_physical_measurements": clin.paired_physical_measurements,
                    }
                    if clin
                    else None
                ),
                "measurements": ms_by_code,
            }
        )

    return ok(
        {
            "patient": {
                "id": str(p.id),
                "patient_code": p.patient_code,
                "fracture_side": p.fracture_detail.fracture_side.value if p.fracture_detail and p.fracture_detail.fracture_side else None,
                "surgery_date": p.surgery_detail.surgery_date.isoformat() if p.surgery_detail and p.surgery_detail.surgery_date else None,
                "study_status": p.study_status.value,
            },
            "measurement_definitions": [
                {
                    "code": d.code,
                    "name": d.name,
                    "unit": d.unit,
                    "measurement_type": d.measurement_type.value,
                }
                for d in m_defs
            ],
            "visits": timeline,
            "interpolation_notice": "Missing longitudinal measurements are never interpolated without explicit protocol authorization.",
        }
    )
