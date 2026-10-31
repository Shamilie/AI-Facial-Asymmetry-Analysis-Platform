"""
Calibration configuration endpoints (Page 11):
  * POST /calibration                    — create view-specific facial or OPG calibration record
  * GET  /calibration                    — list calibration records
  * GET  /visits/{visit_id}/calibration  — calibration records for a specific visit
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import bad_request, ok
from app.core.security import require_permissions
from app.measurements.engine import calibration_mm_per_pixel
from app.models.calibration import CalibrationRecord, CalibrationTypeEnum
from app.services.audit import record_audit

router = APIRouter(tags=["Calibration"])


class CalibrationCreateRequest(BaseModel):
    visit_id: uuid.UUID
    image_id: uuid.UUID | None = None
    calibration_type: CalibrationTypeEnum
    reference_marker_type: str = Field(..., min_length=2)
    known_marker_length_mm: float = Field(..., gt=0)
    measured_marker_length_px: float = Field(..., gt=0)
    marker_location: str = Field(default="Anatomical reference plane")
    calibration_plane: str = Field(default="Coronal / Mid-sagittal plane")
    calibration_method: str = Field(default="Known reference marker")
    magnification_factor: float | None = Field(default=None, gt=0)
    pixel_spacing_x: float | None = Field(default=None, gt=0)
    pixel_spacing_y: float | None = Field(default=None, gt=0)
    horizontal_mm_per_px: float | None = Field(default=None, gt=0)
    vertical_mm_per_px: float | None = Field(default=None, gt=0)
    is_physical: bool = True
    same_plane_confirmed: bool = True
    calibration_date: date | None = None
    notes: str | None = None


def _serialize_cal(c: CalibrationRecord) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "visit_id": str(c.visit_id) if c.visit_id else None,
        "image_id": str(c.image_id) if c.image_id else None,
        "calibration_type": c.calibration_type.value,
        "reference_marker_type": c.reference_marker_type,
        "known_marker_length_mm": c.known_marker_length_mm,
        "measured_marker_length_px": c.measured_marker_length_px,
        "mm_per_pixel": round(c.mm_per_pixel, 6),
        "pixels_per_mm": round(1.0 / c.mm_per_pixel, 4) if c.mm_per_pixel else None,
        "marker_location": c.marker_location,
        "calibration_plane": c.calibration_plane,
        "calibration_method": c.calibration_method,
        "magnification_factor": c.magnification_factor,
        "pixel_spacing_x": c.pixel_spacing_x,
        "pixel_spacing_y": c.pixel_spacing_y,
        "regional_calibration": c.regional_calibration,
        "is_physical": c.is_physical,
        "same_plane_confirmed": c.same_plane_confirmed,
        "is_active": c.is_active,
        "version": c.version,
        "warnings": c.warnings or [],
        "calibrated_by_email": c.calibrator.email if c.calibrator else None,
        "calibration_date": c.calibration_date.isoformat() if c.calibration_date else None,
        "notes": c.notes,
        "created_at": c.created_at.isoformat(),
    }


@router.post("/calibration")
async def create_calibration(
    payload: CalibrationCreateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CALIBRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        mm_per_px = calibration_mm_per_pixel(
            payload.known_marker_length_mm,
            payload.measured_marker_length_px,
        )
    except ValueError as exc:
        raise bad_request(str(exc))

    warnings: list[str] = []
    if not payload.is_physical or "display" in payload.calibration_method.lower() or "ppi" in payload.calibration_method.lower():
        payload.is_physical = False
        warnings.append(
            "Generic display/PPI assumption (e.g. 1 mm = 3.78 px) is NOT physical calibration; affected measurements will be flagged Unscaled."
        )
    if not payload.same_plane_confirmed:
        warnings.append(
            "Calibration marker is not confirmed to lie in the same plane as the measured anatomical feature; perspective foreshortening error may occur."
        )
    if payload.measured_marker_length_px < 20:
        warnings.append(
            "Measured marker length is under 20 pixels; discretization uncertainty is elevated."
        )
    if payload.calibration_type == CalibrationTypeEnum.OPG:
        warnings.append(
            "OPG panoramic radiographs exhibit regional magnification and horizontal distortion; DICOM pixel spacing alone does not correct all distortion."
        )

    # Version previous active calibrations of the same view on this visit
    prev_stmt = select(CalibrationRecord).where(
        CalibrationRecord.visit_id == payload.visit_id,
        CalibrationRecord.calibration_type == payload.calibration_type,
        CalibrationRecord.is_active.is_(True),
    )
    prev_list = list((await db.execute(prev_stmt)).scalars().all())
    next_ver = (max(p.version for p in prev_list) + 1) if prev_list else 1
    for p in prev_list:
        p.is_active = False

    reg_cal = None
    if payload.horizontal_mm_per_px or payload.vertical_mm_per_px:
        reg_cal = {
            "horizontal_mm_per_px": payload.horizontal_mm_per_px or mm_per_px,
            "vertical_mm_per_px": payload.vertical_mm_per_px or mm_per_px,
        }

    rec = CalibrationRecord(
        visit_id=payload.visit_id,
        image_id=payload.image_id,
        calibration_type=payload.calibration_type,
        reference_marker_type=payload.reference_marker_type,
        known_marker_length_mm=payload.known_marker_length_mm,
        measured_marker_length_px=payload.measured_marker_length_px,
        mm_per_pixel=mm_per_px,
        marker_location=payload.marker_location,
        calibration_plane=payload.calibration_plane,
        calibration_method=payload.calibration_method,
        magnification_factor=payload.magnification_factor,
        pixel_spacing_x=payload.pixel_spacing_x,
        pixel_spacing_y=payload.pixel_spacing_y,
        regional_calibration=reg_cal,
        warnings=warnings,
        is_physical=payload.is_physical,
        same_plane_confirmed=payload.same_plane_confirmed,
        is_active=True,
        version=next_ver,
        notes=payload.notes,
        calibrated_by=current_user.id,
        calibration_date=payload.calibration_date or date.today(),
    )
    db.add(rec)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="calibration.create",
        resource_type="calibration_record",
        resource_id=rec.id,
        after={
            "visit_id": str(payload.visit_id),
            "calibration_type": payload.calibration_type.value,
            "mm_per_pixel": round(mm_per_px, 6),
            "is_physical": payload.is_physical,
            "version": next_ver,
        },
        request=request,
    )
    return ok(_serialize_cal(rec), message=f"Saved {payload.calibration_type.value} calibration (v{next_ver})")


@router.get("/calibration")
async def list_calibrations(
    visit_id: uuid.UUID | None = Query(default=None),
    active_only: bool = Query(default=True),
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(CalibrationRecord).order_by(CalibrationRecord.created_at.desc())
    if visit_id:
        stmt = stmt.where(CalibrationRecord.visit_id == visit_id)
    if active_only:
        stmt = stmt.where(CalibrationRecord.is_active.is_(True))
    rows = list((await db.execute(stmt)).scalars().all())
    return ok([_serialize_cal(c) for c in rows])


@router.get("/visits/{visit_id}/calibration")
async def get_visit_calibrations(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(CalibrationRecord)
        .where(CalibrationRecord.visit_id == visit_id)
        .order_by(CalibrationRecord.is_active.desc(), CalibrationRecord.created_at.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return ok([_serialize_cal(c) for c in rows])
