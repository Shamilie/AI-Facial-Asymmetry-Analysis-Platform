"""
Measurement Results endpoints (Page 12):
  * GET   /visits/{visit_id}/measurements  — measurements for a visit, grouped by provenance
  * GET   /measurements                    — study-wide measurement listing
  * POST  /measurements/calculate          — run validated geometric measurement engine for a visit
  * PATCH /measurements/{measurement_id}/review  — save reviewer notes / method update
  * POST  /measurements/{measurement_id}/approve — approve or reject a measurement
  * POST  /visits/{visit_id}/measurements/approve-all — batch approve eligible measurements
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.orchestrator import calculate_visit_measurements
from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import bad_request, not_found, ok
from app.core.security import require_permissions
from app.models.measurement import (
    ApprovalStatusEnum,
    Measurement,
    MeasurementApproval,
    MeasurementMethodEnum,
    MeasurementStatusEnum,
)
from app.models.visit import Visit
from app.services.audit import record_audit
from app.services.report_exporter import build_csv_bytes, build_excel_bytes

router = APIRouter(tags=["Measurements"])


class CalculateMeasurementsRequest(BaseModel):
    visit_id: uuid.UUID


class MeasurementReviewRequest(BaseModel):
    reviewer_notes: str | None = None
    method: MeasurementMethodEnum | None = None
    status: MeasurementStatusEnum | None = None


class MeasurementApproveRequest(BaseModel):
    approval_status: ApprovalStatusEnum = ApprovalStatusEnum.APPROVED
    comments: str | None = "Verified landmarks, calibration plane and bilateral calculation."


def _serialize_measurement(m: Measurement) -> dict[str, Any]:
    d = m.measurement_definition
    cal = m.calibration
    approvals = sorted(m.approvals, key=lambda a: a.approved_at)
    latest_app = approvals[-1] if approvals else None
    return {
        "id": str(m.id),
        "visit_id": str(m.visit_id),
        "measurement_definition_id": str(m.measurement_definition_id),
        "code": d.code if d else "",
        "name": d.name if d else "",
        "description": d.description if d else "",
        "measurement_type": d.measurement_type.value if d else "Linear",
        "formula": d.formula if d else "|Right - Left| / (Right + Left) × 100",
        "right_value": m.right_value,
        "left_value": m.left_value,
        "absolute_difference": m.absolute_difference,
        "asymmetry_index": m.asymmetry_index,
        "unit": m.unit,
        "source_image_type": m.source_image_type,
        "calibration_id": str(m.calibration_id) if m.calibration_id else None,
        "calibration_reference": (
            f"{cal.calibration_type.value}: {cal.mm_per_pixel:.4f} mm/px ({cal.reference_marker_type})"
            if cal
            else ("Not required (angular)" if (d and d.measurement_type.value == "Angular") else "Unscaled / Missing")
        ),
        "landmark_refs": m.landmark_refs or {},
        "method": m.method.value,
        "model_name": m.model_name,
        "model_version": m.model_version,
        "status": m.status.value,
        "is_unscaled": m.is_unscaled,
        "version": m.version,
        "warnings": m.warnings or [],
        "notes": m.notes,
        "reviewer_notes": m.reviewer_notes,
        "latest_approval": (
            {
                "approver_email": latest_app.approver.email if latest_app.approver else "examiner",
                "approval_status": latest_app.approval_status.value,
                "comments": latest_app.comments,
                "approved_at": latest_app.approved_at.isoformat(),
            }
            if latest_app
            else None
        ),
        "updated_at": (m.updated_at or m.created_at).isoformat(),
    }


@router.get("/visits/{visit_id}/measurements")
async def list_visit_measurements(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Measurement)
        .where(Measurement.visit_id == visit_id, Measurement.is_current.is_(True))
        .options(
            selectinload(Measurement.measurement_definition),
            selectinload(Measurement.calibration),
            selectinload(Measurement.approvals).selectinload(MeasurementApproval.approver),
        )
    )
    rows = list((await db.execute(stmt)).scalars().all())
    rows.sort(key=lambda m: m.measurement_definition.display_order if m.measurement_definition else 999)
    serialized = [_serialize_measurement(m) for m in rows]

    return ok(
        {
            "visit_id": str(visit_id),
            "measurements": serialized,
            "by_provenance": {
                "ai_predicted": [m for m in serialized if m["method"] == "AIPredicted"],
                "examiner_reviewed": [m for m in serialized if m["method"] == "ExaminerReviewed"],
                "validated": [m for m in serialized if m["method"] == "Validated" or m["status"] == "Approved"],
            },
            "summary": {
                "total": len(serialized),
                "approved": sum(1 for m in serialized if m["status"] == "Approved"),
                "review_required": sum(1 for m in serialized if m["status"] in ("Calculated", "ReviewRequired")),
                "unscaled": sum(1 for m in serialized if m["status"] == "Unscaled"),
                "missing_or_not_identifiable": sum(
                    1 for m in serialized if m["status"] in ("MissingData", "NotIdentifiable", "Invalid")
                ),
            },
        }
    )


@router.get("/measurements")
async def list_all_measurements(
    visit_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    method: str | None = Query(default=None),
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Measurement)
        .where(Measurement.is_current.is_(True))
        .options(
            selectinload(Measurement.measurement_definition),
            selectinload(Measurement.calibration),
            selectinload(Measurement.approvals).selectinload(MeasurementApproval.approver),
        )
        .order_by(Measurement.created_at.desc())
        .limit(250)
    )
    if visit_id:
        stmt = stmt.where(Measurement.visit_id == visit_id)
    if status:
        stmt = stmt.where(Measurement.status == status)
    if method:
        stmt = stmt.where(Measurement.method == method)

    rows = list((await db.execute(stmt)).scalars().all())
    return ok([_serialize_measurement(m) for m in rows])


@router.post("/measurements/calculate")
async def calculate_measurements_endpoint(
    payload: CalculateMeasurementsRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_CALCULATE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    visit = (await db.execute(select(Visit).where(Visit.id == payload.visit_id))).scalar_one_or_none()
    if visit is None:
        raise not_found("Visit")

    await calculate_visit_measurements(db, payload.visit_id, current_user.id)
    await record_audit(
        db,
        user=current_user,
        action="measurement.calculate",
        resource_type="visit",
        resource_id=payload.visit_id,
        after={"visit_id": str(payload.visit_id)},
        request=request,
    )
    return await list_visit_measurements(payload.visit_id, current_user, db)


@router.patch("/measurements/{measurement_id}/review")
async def review_measurement(
    measurement_id: uuid.UUID,
    payload: MeasurementReviewRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_CALCULATE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Measurement)
        .where(Measurement.id == measurement_id)
        .options(
            selectinload(Measurement.measurement_definition),
            selectinload(Measurement.calibration),
            selectinload(Measurement.approvals).selectinload(MeasurementApproval.approver),
        )
    )
    m = (await db.execute(stmt)).scalar_one_or_none()
    if m is None:
        raise not_found("Measurement")
    before = {"method": m.method.value, "status": m.status.value, "reviewer_notes": m.reviewer_notes}
    if payload.reviewer_notes is not None:
        m.reviewer_notes = payload.reviewer_notes
    if payload.method is not None:
        m.method = payload.method
    else:
        m.method = MeasurementMethodEnum.EXAMINER_REVIEWED
    if payload.status is not None:
        m.status = payload.status
    await record_audit(
        db,
        user=current_user,
        action="measurement.review",
        resource_type="measurement",
        resource_id=m.id,
        before=before,
        after={"method": m.method.value, "status": m.status.value, "reviewer_notes": m.reviewer_notes},
        request=request,
    )
    return ok(_serialize_measurement(m), message="Measurement review saved")


@router.post("/measurements/{measurement_id}/approve")
async def approve_measurement(
    measurement_id: uuid.UUID,
    payload: MeasurementApproveRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Measurement)
        .where(Measurement.id == measurement_id)
        .options(
            selectinload(Measurement.measurement_definition),
            selectinload(Measurement.calibration),
            selectinload(Measurement.approvals).selectinload(MeasurementApproval.approver),
        )
    )
    m = (await db.execute(stmt)).scalar_one_or_none()
    if m is None:
        raise not_found("Measurement")

    if payload.approval_status == ApprovalStatusEnum.APPROVED:
        if m.right_value is None or m.left_value is None or m.is_unscaled:
            raise bad_request(
                "Cannot approve a measurement with missing bilateral values or unscaled calibration."
            )
        m.status = MeasurementStatusEnum.APPROVED
        m.method = MeasurementMethodEnum.VALIDATED
    elif payload.approval_status == ApprovalStatusEnum.REJECTED:
        m.status = MeasurementStatusEnum.REJECTED
    else:
        m.status = MeasurementStatusEnum.REVIEW_REQUIRED

    app_rec = MeasurementApproval(
        measurement_id=m.id,
        approver_id=current_user.id,
        approval_status=payload.approval_status,
        comments=payload.comments,
    )
    if payload.comments:
        m.reviewer_notes = payload.comments
    db.add(app_rec)
    await db.flush()
    m.approvals.append(app_rec)

    await record_audit(
        db,
        user=current_user,
        action="measurement.approve",
        resource_type="measurement",
        resource_id=m.id,
        after={
            "code": m.measurement_definition.code if m.measurement_definition else None,
            "approval_status": payload.approval_status.value,
            "status": m.status.value,
        },
        reason=payload.comments,
        request=request,
    )
    return ok(_serialize_measurement(m), message=f"Measurement {payload.approval_status.value}")


@router.post("/visits/{visit_id}/measurements/approve-all")
async def approve_all_eligible_visit_measurements(
    visit_id: uuid.UUID,
    payload: MeasurementApproveRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Measurement)
        .where(Measurement.visit_id == visit_id, Measurement.is_current.is_(True))
        .options(selectinload(Measurement.measurement_definition))
    )
    ms = list((await db.execute(stmt)).scalars().all())
    approved_count = 0
    for m in ms:
        if m.right_value is not None and m.left_value is not None and not m.is_unscaled:
            m.status = MeasurementStatusEnum.APPROVED
            m.method = MeasurementMethodEnum.VALIDATED
            m.reviewer_notes = payload.comments
            db.add(
                MeasurementApproval(
                    measurement_id=m.id,
                    approver_id=current_user.id,
                    approval_status=ApprovalStatusEnum.APPROVED,
                    comments=payload.comments,
                )
            )
            approved_count += 1
    await db.flush()
    await record_audit(
        db,
        user=current_user,
        action="measurement.approve_batch",
        resource_type="visit",
        resource_id=visit_id,
        after={"approved_count": approved_count},
        reason=payload.comments,
        request=request,
    )
    return await list_visit_measurements(visit_id, current_user, db)


@router.get("/visits/{visit_id}/measurements/export")
async def export_visit_measurements(
    visit_id: uuid.UUID,
    format: str = Query(default="csv", pattern="^(csv|excel)$"),
    request: Request = None,  # type: ignore[assignment]
    current_user: Any = Depends(require_permissions(P.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    res = await list_visit_measurements(visit_id, current_user, db)
    rows = [
        {
            "code": m["code"],
            "name": m["name"],
            "right_value": m["right_value"],
            "left_value": m["left_value"],
            "absolute_difference": m["absolute_difference"],
            "asymmetry_index_pct": m["asymmetry_index"],
            "unit": m["unit"],
            "source_view": m["source_image_type"],
            "calibration": m["calibration_reference"],
            "method": m["method"],
            "status": m["status"],
            "model_version": m["model_version"],
            "reviewer_notes": m["reviewer_notes"],
        }
        for m in res["data"]["measurements"]
    ]
    await record_audit(
        db,
        user=current_user,
        action="measurement.export",
        resource_type="visit",
        resource_id=visit_id,
        after={"format": format, "count": len(rows)},
        request=request,
    )
    if format == "excel":
        return Response(
            content=build_excel_bytes("Measurements", rows, {"visit_id": str(visit_id)}),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="measurements_{visit_id}.xlsx"'},
        )
    return Response(
        content=build_csv_bytes(rows),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="measurements_{visit_id}.csv"'},
    )
