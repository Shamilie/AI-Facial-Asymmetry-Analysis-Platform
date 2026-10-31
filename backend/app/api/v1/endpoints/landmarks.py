"""
Landmark Review Workspace endpoints (Page 9):
  * GET   /analysis/{visit_id}/landmarks         — images, definitions, AI predictions & examiner reviews separated
  * PATCH /landmarks/{prediction_id}/review      — save examiner correction / confirmation / approval (preserves AI coords)
  * POST  /landmarks/{prediction_id}/not-identifiable — mark a landmark NotIdentifiable with reason
  * POST  /landmarks                             — add a permitted protocol landmark to an image
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import bad_request, not_found, ok
from app.core.security import require_permissions
from app.models.image import VisitImage
from app.models.landmark import (
    LandmarkDefinition,
    LandmarkPrediction,
    LandmarkReview,
    PredictionStatusEnum,
    ReviewStatusEnum,
)
from app.services.audit import record_audit

router = APIRouter(tags=["Landmarks"])


class LandmarkReviewRequest(BaseModel):
    corrected_x: float | None = None
    corrected_y: float | None = None
    review_status: ReviewStatusEnum = ReviewStatusEnum.CORRECTED
    approve: bool = False
    correction_reason: str = Field(default="Examiner manual verification", min_length=2)


class NotIdentifiableRequest(BaseModel):
    reason: str = Field(default="Anatomical landmark obscured or not identifiable in this view", min_length=2)


class AddLandmarkRequest(BaseModel):
    image_id: uuid.UUID
    landmark_code: str
    x: float
    y: float
    reason: str = Field(default="Manually placed permitted protocol landmark", min_length=2)


def _serialize_prediction(pred: LandmarkPrediction) -> dict[str, Any]:
    d = pred.landmark_definition
    reviews = sorted(pred.reviews, key=lambda r: r.reviewed_at)
    latest_rev = reviews[-1] if reviews else None

    # Original AI prediction is ALWAYS preserved in original_x / original_y:
    original_ai_x = reviews[0].original_x if reviews and reviews[0].original_x is not None else pred.x
    original_ai_y = reviews[0].original_y if reviews and reviews[0].original_y is not None else pred.y

    examiner_x = latest_rev.corrected_x if latest_rev and latest_rev.corrected_x is not None else None
    examiner_y = latest_rev.corrected_y if latest_rev and latest_rev.corrected_y is not None else None

    effective_x = examiner_x if examiner_x is not None else pred.x
    effective_y = examiner_y if examiner_y is not None else pred.y

    state_category = (
        "Approved"
        if pred.status == PredictionStatusEnum.APPROVED
        else (
            "ExaminerReviewed"
            if (pred.status == PredictionStatusEnum.REVIEWED or latest_rev is not None)
            else "AIPredicted"
        )
    )

    return {
        "id": str(pred.id),
        "image_id": str(pred.image_id),
        "landmark_definition_id": str(pred.landmark_definition_id),
        "code": d.code if d else "",
        "name": d.name if d else "",
        "side": d.side if d else "Midline",
        "anatomical_region": d.anatomical_region if d else "",
        "landmark_type": d.landmark_type.value if d else "Facial",
        "source": pred.source,
        "predicted_x": original_ai_x,
        "predicted_y": original_ai_y,
        "examiner_x": examiner_x,
        "examiner_y": examiner_y,
        "effective_x": effective_x,
        "effective_y": effective_y,
        "z": pred.z,
        "confidence": pred.confidence,
        "status": pred.status.value,
        "state_category": state_category,
        "model_name": pred.model_name,
        "model_version": pred.model_version,
        "reviews": [
            {
                "id": str(r.id),
                "reviewer_email": r.reviewer.email if r.reviewer else "examiner",
                "original_x": r.original_x,
                "original_y": r.original_y,
                "corrected_x": r.corrected_x,
                "corrected_y": r.corrected_y,
                "review_status": r.review_status.value,
                "correction_reason": r.correction_reason,
                "reviewed_at": r.reviewed_at.isoformat(),
            }
            for r in reviews
        ],
    }


@router.get("/analysis/{visit_id}/landmarks")
async def get_visit_landmarks(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    imgs = list(
        (
            await db.execute(
                select(VisitImage)
                .where(VisitImage.visit_id == visit_id, VisitImage.is_deleted.is_(False))
                .order_by(VisitImage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    defs = list(
        (await db.execute(select(LandmarkDefinition).order_by(LandmarkDefinition.display_order.asc())))
        .scalars()
        .all()
    )

    views_out = []
    for im in imgs:
        preds_stmt = (
            select(LandmarkPrediction)
            .where(LandmarkPrediction.image_id == im.id, LandmarkPrediction.is_current.is_(True))
            .options(
                selectinload(LandmarkPrediction.landmark_definition),
                selectinload(LandmarkPrediction.reviews).selectinload(LandmarkReview.reviewer),
            )
        )
        preds = list((await db.execute(preds_stmt)).scalars().all())
        preds.sort(key=lambda p: p.landmark_definition.display_order if p.landmark_definition else 999)
        views_out.append(
            {
                "image_id": str(im.id),
                "image_type": im.image_type.value,
                "original_filename": im.original_filename,
                "width": im.width,
                "height": im.height,
                "acceptance_status": im.acceptance_status,
                "is_synthetic": im.is_synthetic,
                "file_url": f"/api/v1/images/{im.id}/file",
                "landmarks": [_serialize_prediction(p) for p in preds],
            }
        )

    return ok(
        {
            "visit_id": str(visit_id),
            "views": views_out,
            "permitted_definitions": [
                {
                    "id": str(d.id),
                    "code": d.code,
                    "name": d.name,
                    "side": d.side,
                    "landmark_type": d.landmark_type.value,
                    "anatomical_region": d.anatomical_region,
                    "applicable_views": d.applicable_views or [],
                }
                for d in defs
            ],
        }
    )


@router.patch("/landmarks/{prediction_id}/review")
async def review_landmark(
    prediction_id: uuid.UUID,
    payload: LandmarkReviewRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.LANDMARK_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(LandmarkPrediction)
        .where(LandmarkPrediction.id == prediction_id)
        .options(
            selectinload(LandmarkPrediction.landmark_definition),
            selectinload(LandmarkPrediction.reviews).selectinload(LandmarkReview.reviewer),
            selectinload(LandmarkPrediction.image),
        )
    )
    pred = (await db.execute(stmt)).scalar_one_or_none()
    if pred is None:
        raise not_found("LandmarkPrediction")

    # Preserve the initial AI coordinate in LandmarkReview.original_x/original_y
    first_orig_x = pred.reviews[0].original_x if pred.reviews and pred.reviews[0].original_x is not None else pred.x
    first_orig_y = pred.reviews[0].original_y if pred.reviews and pred.reviews[0].original_y is not None else pred.y

    new_x = payload.corrected_x if payload.corrected_x is not None else pred.x
    new_y = payload.corrected_y if payload.corrected_y is not None else pred.y

    if pred.image and pred.image.width and pred.image.height and new_x is not None and new_y is not None:
        if not (0 <= new_x <= pred.image.width and 0 <= new_y <= pred.image.height):
            raise bad_request("Adjusted coordinates are outside the image boundaries.")

    rev = LandmarkReview(
        prediction_id=pred.id,
        reviewer_id=current_user.id,
        original_x=first_orig_x,
        original_y=first_orig_y,
        corrected_x=new_x,
        corrected_y=new_y,
        review_status=payload.review_status,
        correction_reason=payload.correction_reason,
    )
    db.add(rev)

    if payload.review_status == ReviewStatusEnum.REJECTED:
        pred.status = PredictionStatusEnum.REJECTED
    elif payload.review_status == ReviewStatusEnum.NOT_IDENTIFIABLE:
        pred.status = PredictionStatusEnum.NOT_IDENTIFIABLE
    elif payload.approve:
        pred.status = PredictionStatusEnum.APPROVED
    else:
        pred.status = PredictionStatusEnum.REVIEWED

    await db.flush()
    pred.reviews.append(rev)

    await record_audit(
        db,
        user=current_user,
        action="landmark.review",
        resource_type="landmark_prediction",
        resource_id=pred.id,
        before={"original_x": first_orig_x, "original_y": first_orig_y},
        after={
            "code": pred.landmark_definition.code if pred.landmark_definition else None,
            "corrected_x": new_x,
            "corrected_y": new_y,
            "status": pred.status.value,
        },
        reason=payload.correction_reason,
        request=request,
    )
    return ok(_serialize_prediction(pred), message="Landmark review recorded (original AI prediction preserved)")


@router.post("/landmarks/{prediction_id}/not-identifiable")
async def mark_landmark_not_identifiable(
    prediction_id: uuid.UUID,
    payload: NotIdentifiableRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.LANDMARK_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(LandmarkPrediction)
        .where(LandmarkPrediction.id == prediction_id)
        .options(
            selectinload(LandmarkPrediction.landmark_definition),
            selectinload(LandmarkPrediction.reviews).selectinload(LandmarkReview.reviewer),
        )
    )
    pred = (await db.execute(stmt)).scalar_one_or_none()
    if pred is None:
        raise not_found("LandmarkPrediction")

    first_orig_x = pred.reviews[0].original_x if pred.reviews and pred.reviews[0].original_x is not None else pred.x
    first_orig_y = pred.reviews[0].original_y if pred.reviews and pred.reviews[0].original_y is not None else pred.y

    rev = LandmarkReview(
        prediction_id=pred.id,
        reviewer_id=current_user.id,
        original_x=first_orig_x,
        original_y=first_orig_y,
        corrected_x=None,
        corrected_y=None,
        review_status=ReviewStatusEnum.NOT_IDENTIFIABLE,
        correction_reason=payload.reason,
    )
    db.add(rev)
    pred.status = PredictionStatusEnum.NOT_IDENTIFIABLE
    await db.flush()
    pred.reviews.append(rev)

    await record_audit(
        db,
        user=current_user,
        action="landmark.not_identifiable",
        resource_type="landmark_prediction",
        resource_id=pred.id,
        before={"original_x": first_orig_x, "original_y": first_orig_y},
        after={"status": "NotIdentifiable"},
        reason=payload.reason,
        request=request,
    )
    return ok(_serialize_prediction(pred), message="Landmark marked Not Identifiable")


@router.post("/landmarks")
async def add_permitted_landmark(
    payload: AddLandmarkRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.LANDMARK_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    im = (await db.execute(select(VisitImage).where(VisitImage.id == payload.image_id))).scalar_one_or_none()
    if im is None:
        raise not_found("Image")
    ld = (
        await db.execute(select(LandmarkDefinition).where(LandmarkDefinition.code == payload.landmark_code))
    ).scalar_one_or_none()
    if ld is None:
        raise bad_request(f"Landmark '{payload.landmark_code}' is not in the approved research protocol.")

    # Deactivate any previous prediction for this definition on this image
    for prev in (
        await db.execute(
            select(LandmarkPrediction).where(
                LandmarkPrediction.image_id == im.id,
                LandmarkPrediction.landmark_definition_id == ld.id,
                LandmarkPrediction.is_current.is_(True),
            )
        )
    ).scalars().all():
        prev.is_current = False

    pred = LandmarkPrediction(
        image_id=im.id,
        job_id=None,
        landmark_definition_id=ld.id,
        source="Manual",
        is_current=True,
        x=payload.x,
        y=payload.y,
        confidence=1.0,
        status=PredictionStatusEnum.REVIEWED,
        model_name="examiner-manual-annotation",
        model_version="1.0.0",
    )
    db.add(pred)
    await db.flush()
    rev = LandmarkReview(
        prediction_id=pred.id,
        reviewer_id=current_user.id,
        original_x=payload.x,
        original_y=payload.y,
        corrected_x=payload.x,
        corrected_y=payload.y,
        review_status=ReviewStatusEnum.CONFIRMED,
        correction_reason=payload.reason,
    )
    db.add(rev)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="landmark.manual_add",
        resource_type="landmark_prediction",
        resource_id=pred.id,
        after={"code": ld.code, "x": payload.x, "y": payload.y},
        reason=payload.reason,
        request=request,
    )
    stmt = (
        select(LandmarkPrediction)
        .where(LandmarkPrediction.id == pred.id)
        .options(
            selectinload(LandmarkPrediction.landmark_definition),
            selectinload(LandmarkPrediction.reviews).selectinload(LandmarkReview.reviewer),
        )
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return ok(_serialize_prediction(loaded), message=f"Added landmark {ld.code}")
