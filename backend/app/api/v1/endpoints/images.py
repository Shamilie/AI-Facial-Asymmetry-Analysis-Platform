"""
Image acquisition, validation, quality assessment and manual acceptance endpoints (Page 7).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import bad_request, conflict, not_found, ok, to_jsonable
from app.core.security import require_permissions
from app.models.calibration import CalibrationRecord, CalibrationTypeEnum
from app.models.image import (
    ImageQualityResult,
    ImageTypeEnum,
    ManualOverrideStatusEnum,
    QualityStatusEnum,
    UploadStatusEnum,
    VisitImage,
)
from app.models.patient import Patient
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum
from app.services.audit import record_audit
from app.services.image_processing import (
    ImageValidationError,
    assess_quality,
    sha256_bytes,
    validate_upload,
)
from app.services.storage import get_storage
from app.services.synthetic_images import frontal, lateral, opg, visit_asymmetry

router = APIRouter(tags=["Images"])


class QualityOverrideRequest(BaseModel):
    decision: ManualOverrideStatusEnum  # Accepted | Rejected
    reason: str | None = None


def _serialize_image(im: VisitImage) -> dict[str, Any]:
    latest_q = im.quality_results[-1] if im.quality_results else None
    return {
        "id": str(im.id),
        "visit_id": str(im.visit_id),
        "image_type": im.image_type.value,
        "original_filename": im.original_filename,
        "file_size": im.file_size,
        "mime_type": im.mime_type,
        "width": im.width,
        "height": im.height,
        "capture_date": im.capture_date.isoformat() if im.capture_date else None,
        "device_metadata": im.device_metadata,
        "upload_status": im.upload_status.value,
        "acceptance_status": im.acceptance_status,
        "is_synthetic": im.is_synthetic,
        "file_url": f"/api/v1/images/{im.id}/file",
        "created_at": im.created_at.isoformat(),
        "quality_result": (
            {
                "id": str(latest_q.id),
                "provider": latest_q.provider,
                "model_name": latest_q.model_name,
                "model_version": latest_q.model_version,
                "overall_score": latest_q.overall_score,
                "status": latest_q.status.value,
                "face_visibility": latest_q.face_visibility,
                "orientation_check": latest_q.orientation_check,
                "lighting_check": latest_q.lighting_check,
                "blur_check": latest_q.blur_check,
                "occlusion_check": latest_q.occlusion_check,
                "framing_check": latest_q.framing_check,
                "resolution_check": latest_q.resolution_check,
                "issues": latest_q.issues or [],
                "suggestions": latest_q.suggestions or [],
                "manual_override_status": (
                    latest_q.manual_override_status.value if latest_q.manual_override_status else None
                ),
                "manual_override_at": (
                    latest_q.manual_override_at.isoformat() if latest_q.manual_override_at else None
                ),
                "disclaimer": "Heuristic quality screening only; a Pass status does not establish clinical adequacy.",
            }
            if latest_q
            else None
        ),
    }


@router.get("/visits/{visit_id}/images")
async def list_visit_images(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(VisitImage)
        .where(VisitImage.visit_id == visit_id, VisitImage.is_deleted.is_(False))
        .options(selectinload(VisitImage.quality_results))
        .order_by(VisitImage.created_at.asc())
    )
    imgs = list((await db.execute(stmt)).scalars().all())
    return ok([_serialize_image(im) for im in imgs])


@router.post("/visits/{visit_id}/images")
async def upload_visit_image(
    visit_id: uuid.UUID,
    request: Request,
    image_type: ImageTypeEnum = Form(...),
    replace_existing: bool = Form(default=True),
    file: UploadFile = File(...),
    current_user: Any = Depends(require_permissions(P.IMAGE_UPLOAD)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    visit = (await db.execute(select(Visit).where(Visit.id == visit_id))).scalar_one_or_none()
    if visit is None:
        raise not_found("Visit")

    raw = await file.read()
    try:
        meta = validate_upload(raw, file.filename or "upload.png")
    except ImageValidationError as exc:
        raise bad_request(str(exc))

    content_hash = sha256_bytes(raw)
    # Check duplicate upload within the same visit unless replacing the same image_type
    dup_stmt = select(VisitImage).where(
        VisitImage.visit_id == visit_id,
        VisitImage.content_hash == content_hash,
        VisitImage.is_deleted.is_(False),
    )
    dup = (await db.execute(dup_stmt)).scalars().first()
    dup_view_warning = (
        f"Duplicate file content also present in {dup.image_type.value} view for this visit."
        if (dup is not None and dup.image_type != image_type)
        else None
    )

    # Soft-delete previous image of the same view if replacing
    if replace_existing:
        prev_stmt = select(VisitImage).where(
            VisitImage.visit_id == visit_id,
            VisitImage.image_type == image_type,
            VisitImage.is_deleted.is_(False),
        )
        for prev in (await db.execute(prev_stmt)).scalars().all():
            prev.is_deleted = True

    storage = get_storage()
    ext = meta["format"].lower()
    if ext == "jpeg":
        ext = "jpg"
    key = storage.save("originals", raw, ext, subdir=str(visit_id))

    is_synth = bool((meta.get("device_metadata") or {}).get("synthetic"))
    vim = VisitImage(
        visit_id=visit_id,
        image_type=image_type,
        original_filename=file.filename or f"{image_type.value}.{ext}",
        stored_path=key,
        file_size=len(raw),
        mime_type=meta["mime_type"],
        width=int(meta["width"]),
        height=int(meta["height"]),
        capture_date=meta.get("capture_date") or datetime.now(timezone.utc),
        device_metadata=to_jsonable(meta.get("device_metadata")),
        upload_status=UploadStatusEnum.COMPLETED,
        uploaded_by=current_user.id,
        content_hash=content_hash,
        acceptance_status="Pending",
        is_synthetic=is_synth,
    )
    db.add(vim)
    await db.flush()

    # Execute heuristic quality assessment immediately on upload
    q = assess_quality(raw, image_type.value)
    issues_list = list(q.get("issues") or [])
    if dup_view_warning:
        issues_list.append(dup_view_warning)
    qr = ImageQualityResult(
        image_id=vim.id,
        provider=q["provider"],
        model_name=q["model_name"],
        model_version=q["model_version"],
        overall_score=q["overall_score"],
        status=QualityStatusEnum(q["status"]),
        face_visibility=to_jsonable(q["face_visibility"]),
        orientation_check=to_jsonable(q["orientation_check"]),
        lighting_check=to_jsonable(q["lighting_check"]),
        blur_check=to_jsonable(q["blur_check"]),
        occlusion_check=to_jsonable(q["occlusion_check"]),
        framing_check=to_jsonable(q["framing_check"]),
        resolution_check=to_jsonable(q["resolution_check"]),
        issues=to_jsonable(issues_list),
        suggestions=to_jsonable(q["suggestions"]),
    )
    db.add(qr)
    if visit.status in (VisitStatusEnum.PLANNED, VisitStatusEnum.SCHEDULED):
        visit.status = VisitStatusEnum.IN_PROGRESS
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="image.upload",
        resource_type="visit_image",
        resource_id=vim.id,
        after={"visit_id": str(visit_id), "image_type": image_type.value, "quality": q["status"]},
        request=request,
    )
    stmt = (
        select(VisitImage)
        .where(VisitImage.id == vim.id)
        .options(selectinload(VisitImage.quality_results))
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return ok(_serialize_image(loaded), message=f"{image_type.value} uploaded and assessed")


@router.post("/visits/{visit_id}/images/generate-synthetic")
async def generate_synthetic_visit_images(
    visit_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.IMAGE_UPLOAD)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Convenience endpoint to populate all 4 views + physical calibrations with
    clearly-labelled SYNTHETIC demo images for any visit during demonstrations.
    """
    stmt = (
        select(Visit)
        .where(Visit.id == visit_id)
        .options(selectinload(Visit.patient).selectinload(Patient.fracture_detail))
    )
    visit = (await db.execute(stmt)).scalar_one_or_none()
    if visit is None:
        raise not_found("Visit")

    side = (
        visit.patient.fracture_detail.fracture_side.value
        if visit.patient and visit.patient.fracture_detail and visit.patient.fracture_detail.fracture_side
        else "Left"
    )
    v_order = [
        VisitTypeEnum.PRE_OPERATIVE,
        VisitTypeEnum.POST_OP_1_WEEK,
        VisitTypeEnum.POST_OP_6_WEEKS,
        VisitTypeEnum.POST_OP_3_MONTHS,
        VisitTypeEnum.POST_OP_6_MONTHS,
    ]
    v_idx = v_order.index(visit.visit_type) if visit.visit_type in v_order else 0
    asym = visit_asymmetry(side, v_idx, 1.0)

    # Soft-delete existing images for this visit
    for old in (
        await db.execute(select(VisitImage).where(VisitImage.visit_id == visit_id, VisitImage.is_deleted.is_(False)))
    ).scalars().all():
        old.is_deleted = True

    storage = get_storage()
    builders = [
        (ImageTypeEnum.FRONTAL, CalibrationTypeEnum.FRONTAL_PHOTO, frontal(asym["frontal"], seed=500 + v_idx)),
        (ImageTypeEnum.RIGHT_LATERAL, CalibrationTypeEnum.RIGHT_LATERAL_PHOTO, lateral("Right", asym["right"], seed=600 + v_idx)),
        (ImageTypeEnum.LEFT_LATERAL, CalibrationTypeEnum.LEFT_LATERAL_PHOTO, lateral("Left", asym["left"], seed=700 + v_idx)),
        (ImageTypeEnum.OPG, CalibrationTypeEnum.OPG, opg(asym["opg"], seed=800 + v_idx)),
    ]

    for img_type, cal_type, (png_bytes, meta) in builders:
        key = storage.save("originals", png_bytes, "png", subdir=str(visit_id))
        info = validate_upload(png_bytes, f"synthetic_{img_type.value}.png")
        vim = VisitImage(
            visit_id=visit_id,
            image_type=img_type,
            original_filename=f"SYNTHETIC_{visit.visit_type.value}_{img_type.value}.png",
            stored_path=key,
            file_size=len(png_bytes),
            mime_type="image/png",
            width=info["width"],
            height=info["height"],
            capture_date=datetime.now(timezone.utc),
            device_metadata={"synthetic": "SYNTHETIC DEMO IMAGE (fa-synthetic-1.0)"},
            upload_status=UploadStatusEnum.COMPLETED,
            uploaded_by=current_user.id,
            content_hash=sha256_bytes(png_bytes),
            acceptance_status="Accepted",
            is_synthetic=True,
        )
        db.add(vim)
        await db.flush()

        q = assess_quality(png_bytes, img_type.value)
        db.add(
            ImageQualityResult(
                image_id=vim.id,
                provider="Built-in",
                model_name=q["model_name"],
                model_version=q["model_version"],
                overall_score=None,
                status=QualityStatusEnum(q["status"]),
                face_visibility=q["face_visibility"],
                orientation_check=q["orientation_check"],
                lighting_check=q["lighting_check"],
                blur_check=q["blur_check"],
                occlusion_check=q["occlusion_check"],
                framing_check=q["framing_check"],
                resolution_check=q["resolution_check"],
                issues=q["issues"],
                suggestions=q["suggestions"],
                manual_override_status=ManualOverrideStatusEnum.ACCEPTED,
                manual_override_by=current_user.id,
                manual_override_at=datetime.now(timezone.utc),
            )
        )

        px_per_mm = float(meta["px_per_mm"])
        db.add(
            CalibrationRecord(
                visit_id=visit.id,
                image_id=vim.id,
                calibration_type=cal_type,
                reference_marker_type="10mm radiopaque ball" if img_type == ImageTypeEnum.OPG else "50mm fiducial ruler in anatomical plane",
                known_marker_length_mm=50.0,
                measured_marker_length_px=50.0 * px_per_mm,
                mm_per_pixel=1.0 / px_per_mm,
                marker_location="Anatomical reference plane",
                calibration_plane="Coronal / Mid-sagittal plane",
                calibration_method="Known fiducial marker",
                magnification_factor=1.25 if img_type == ImageTypeEnum.OPG else 1.0,
                is_physical=True,
                same_plane_confirmed=True,
                is_active=True,
                calibrated_by=current_user.id,
                calibration_date=datetime.now(timezone.utc).date(),
            )
        )

    visit.status = VisitStatusEnum.IN_PROGRESS
    await db.flush()
    await record_audit(
        db,
        user=current_user,
        action="image.generate_synthetic_set",
        resource_type="visit",
        resource_id=visit_id,
        after={"views": ["Frontal", "RightLateral", "LeftLateral", "OPG"], "is_synthetic": True},
        request=request,
    )
    return await list_visit_images(visit_id, current_user, db)


@router.post("/images/{image_id}/quality-check")
async def rerun_quality_check(
    image_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.IMAGE_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(VisitImage)
        .where(VisitImage.id == image_id, VisitImage.is_deleted.is_(False))
        .options(selectinload(VisitImage.quality_results))
    )
    im = (await db.execute(stmt)).scalar_one_or_none()
    if im is None:
        raise not_found("Image")
    raw = get_storage().read(im.stored_path)
    q = assess_quality(raw, im.image_type.value)
    qr = ImageQualityResult(
        image_id=im.id,
        provider=q["provider"],
        model_name=q["model_name"],
        model_version=q["model_version"],
        overall_score=q["overall_score"],
        status=QualityStatusEnum(q["status"]),
        face_visibility=q["face_visibility"],
        orientation_check=q["orientation_check"],
        lighting_check=q["lighting_check"],
        blur_check=q["blur_check"],
        occlusion_check=q["occlusion_check"],
        framing_check=q["framing_check"],
        resolution_check=q["resolution_check"],
        issues=q["issues"],
        suggestions=q["suggestions"],
    )
    db.add(qr)
    await db.flush()
    im.quality_results.append(qr)
    return ok(_serialize_image(im), message="Image quality assessment completed")


@router.post("/images/{image_id}/quality-override")
async def manual_quality_override(
    image_id: uuid.UUID,
    payload: QualityOverrideRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.IMAGE_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(VisitImage)
        .where(VisitImage.id == image_id, VisitImage.is_deleted.is_(False))
        .options(selectinload(VisitImage.quality_results))
    )
    im = (await db.execute(stmt)).scalar_one_or_none()
    if im is None:
        raise not_found("Image")
    before_status = im.acceptance_status
    im.acceptance_status = payload.decision.value
    if im.quality_results:
        latest = im.quality_results[-1]
        latest.manual_override_status = payload.decision
        latest.manual_override_by = current_user.id
        latest.manual_override_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        user=current_user,
        action="image.manual_quality_decision",
        resource_type="visit_image",
        resource_id=im.id,
        before={"acceptance_status": before_status},
        after={"acceptance_status": im.acceptance_status},
        reason=payload.reason or f"Examiner manually marked image {payload.decision.value}",
        request=request,
    )
    return ok(_serialize_image(im), message=f"Image marked {payload.decision.value}")


@router.delete("/images/{image_id}")
async def delete_image(
    image_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.IMAGE_DELETE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    im = (await db.execute(select(VisitImage).where(VisitImage.id == image_id))).scalar_one_or_none()
    if im is None:
        raise not_found("Image")
    im.is_deleted = True
    await record_audit(
        db,
        user=current_user,
        action="image.delete",
        resource_type="visit_image",
        resource_id=im.id,
        before={"image_type": im.image_type.value, "filename": im.original_filename},
        request=request,
    )
    return ok({"deleted": True, "id": str(image_id)}, message="Image removed")


@router.get("/images/{image_id}/file")
async def get_image_file(
    image_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    im = (
        await db.execute(select(VisitImage).where(VisitImage.id == image_id, VisitImage.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if im is None:
        raise not_found("Image")
    raw = get_storage().read(im.stored_path)
    return Response(content=raw, media_type=im.mime_type or "image/png")
