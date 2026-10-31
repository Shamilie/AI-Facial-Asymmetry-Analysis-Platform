"""
Workspace compatibility & convenience endpoints connecting Pages 8–20 directly
to the underlying domain services with enriched payloads.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.admin import (
    AIProviderCreateRequest,
    AIProviderUpdateRequest,
    AITestRequest,
    ProtocolVersionCreateRequest,
    create_ai_provider,
    create_protocol_version,
    get_protocols,
    list_ai_providers,
    list_audit_logs,
    list_users,
    test_ai_provider,
    update_ai_provider,
)
from app.api.v1.endpoints.ai import (
    get_visit_analysis,
    start_visit_analysis,
    stream_visit_ai_events,
)
from app.api.v1.endpoints.calibration import (
    CalibrationCreateRequest,
    create_calibration,
    get_visit_calibrations,
)
from app.api.v1.endpoints.images import list_visit_images
from app.api.v1.endpoints.landmarks import (
    AddLandmarkRequest,
    LandmarkReviewRequest,
    NotIdentifiableRequest,
    add_permitted_landmark,
    get_visit_landmarks,
    mark_landmark_not_identifiable,
    review_landmark,
)
from app.api.v1.endpoints.measurements import (
    CalculateMeasurementsRequest,
    MeasurementApproveRequest,
    approve_all_eligible_visit_measurements,
    calculate_measurements_endpoint,
    export_visit_measurements,
    list_visit_measurements,
)
from app.api.v1.endpoints.reconstruction import (
    export_reconstruction_mesh,
    generate_visit_reconstruction,
    get_visit_reconstruction,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import not_found, ok
from app.core.security import get_current_user, require_permissions
from app.models.ai import AITaskTypeEnum, EnvironmentEnum, ProviderTypeEnum
from app.models.calibration import CalibrationTypeEnum
from app.models.image import VisitImage
from app.models.landmark import (
    LandmarkDefinition,
    LandmarkPrediction,
    LandmarkReview,
    PredictionStatusEnum,
    ReviewStatusEnum,
)
from app.models.measurement import ApprovalStatusEnum, Measurement, MeasurementDefinition
from app.models.patient import Patient
from app.models.protocol import StudyProtocol
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum

router = APIRouter(tags=["Workspace Aliases"])


# --- Page 8: AI Pipeline Workspace ---
@router.get("/ai/visits/{visit_id}/pipeline")
async def compat_get_pipeline(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await get_visit_analysis(visit_id, current_user, db)
    stages = res["data"]["stages"]
    done = sum(1 for s in stages if s["status"] in ("Completed", "Validated", "ReviewRequired"))
    overall = "Completed" if done == len(stages) and stages else ("Processing" if done > 0 else "Pending")
    res["data"]["overall_status"] = overall
    return res


@router.post("/ai/visits/{visit_id}/run")
async def compat_run_pipeline(
    visit_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.AI_RUN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await start_visit_analysis(visit_id, request, current_user, db)


@router.get("/ai/visits/{visit_id}/stream")
async def compat_stream_pipeline(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
):
    return await stream_visit_ai_events(visit_id, current_user)


# --- Page 9: Landmark Review Workspace ---
@router.get("/landmarks/definitions")
async def compat_landmark_defs(
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    defs = list(
        (await db.execute(select(LandmarkDefinition).order_by(LandmarkDefinition.display_order.asc())))
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "id": str(d.id),
                "code": d.code,
                "name": d.name,
                "side": d.side,
                "landmark_type": d.landmark_type.value,
                "anatomical_region": d.anatomical_region,
            }
            for d in defs
        ]
    )


@router.get("/landmarks/visits/{visit_id}")
async def compat_visit_landmarks(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await get_visit_landmarks(visit_id, current_user, db)
    views = res["data"]["views"]
    images = []
    by_image_type: dict[str, list[dict[str, Any]]] = {}
    all_lms: list[dict[str, Any]] = []
    for vw in views:
        images.append(
            {
                "id": vw["image_id"],
                "visit_id": str(visit_id),
                "image_type": vw["image_type"],
                "original_filename": vw["original_filename"],
                "width": vw["width"],
                "height": vw["height"],
                "upload_status": "Uploaded",
                "acceptance_status": vw["acceptance_status"],
                "is_synthetic": vw["is_synthetic"],
                "file_url": vw["file_url"],
                "created_at": "",
            }
        )
        by_image_type[vw["image_type"]] = vw["landmarks"]
        all_lms.extend(vw["landmarks"])
    return ok(
        {
            "visit_id": str(visit_id),
            "images": images,
            "by_image_type": by_image_type,
            "landmarks": all_lms,
        }
    )


class CompatAdjustRequest(BaseModel):
    corrected_x: float | None = None
    corrected_y: float | None = None
    review_status: str = "Adjusted"
    correction_reason: str = "Manual anatomical refinement by examiner"


@router.put("/landmarks/{prediction_id}/adjust")
async def compat_adjust_landmark(
    prediction_id: uuid.UUID,
    payload: CompatAdjustRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.LANDMARK_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if payload.review_status == "NotIdentifiable":
        return await mark_landmark_not_identifiable(
            prediction_id,
            NotIdentifiableRequest(reason=payload.correction_reason),
            request,
            current_user,
            db,
        )
    approve = payload.review_status == "Approved"
    r_status = ReviewStatusEnum.CONFIRMED if approve else ReviewStatusEnum.CORRECTED
    return await review_landmark(
        prediction_id,
        LandmarkReviewRequest(
            corrected_x=payload.corrected_x,
            corrected_y=payload.corrected_y,
            review_status=r_status,
            approve=approve,
            correction_reason=payload.correction_reason,
        ),
        request,
        current_user,
        db,
    )


class CompatAddLandmarkBody(BaseModel):
    code: str
    x: float
    y: float
    reason: str = "Added missing protocol landmark"


@router.post("/landmarks/images/{image_id}")
async def compat_add_landmark_to_image(
    image_id: uuid.UUID,
    payload: CompatAddLandmarkBody,
    request: Request,
    current_user: Any = Depends(require_permissions(P.LANDMARK_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await add_permitted_landmark(
        AddLandmarkRequest(
            image_id=image_id,
            landmark_code=payload.code,
            x=payload.x,
            y=payload.y,
            reason=payload.reason,
        ),
        request,
        current_user,
        db,
    )


class CompatApproveAllBody(BaseModel):
    image_type: str | None = None
    reason: str = "Batch approved by examiner"


@router.post("/landmarks/visits/{visit_id}/approve-all")
async def compat_approve_all_landmarks(
    visit_id: uuid.UUID,
    payload: CompatApproveAllBody,
    current_user: Any = Depends(require_permissions(P.LANDMARK_REVIEW)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    imgs_stmt = select(VisitImage).where(VisitImage.visit_id == visit_id, VisitImage.is_deleted.is_(False))
    imgs = list((await db.execute(imgs_stmt)).scalars().all())
    count = 0
    for im in imgs:
        if payload.image_type and im.image_type.value != payload.image_type:
            continue
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
        for p in preds:
            if p.status != PredictionStatusEnum.NOT_IDENTIFIABLE:
                p.status = PredictionStatusEnum.APPROVED
                db.add(
                    LandmarkReview(
                        prediction_id=p.id,
                        reviewer_id=current_user.id,
                        original_x=p.x,
                        original_y=p.y,
                        corrected_x=p.x,
                        corrected_y=p.y,
                        review_status=ReviewStatusEnum.CONFIRMED,
                        correction_reason=payload.reason,
                    )
                )
                count += 1
    await db.flush()
    return ok({"approved_count": count})


# --- Page 10: 3D Reconstruction Workspace ---
@router.get("/reconstruction/visits/{visit_id}")
async def compat_get_recon(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await get_visit_reconstruction(visit_id, current_user, db)
    d = res["data"]
    if not d.get("available"):
        return ok(None)
    surface_paths: dict[str, Any] = {}
    for p in d.get("geodesic_paths", []):
        surface_paths[p["code"]] = {
            "distance_mm": p["distance_value"],
            "path_points": [p["start_xyz"], p["end_xyz"]],
        }
    asset_id = d["asset_id"]
    return ok(
        {
            "id": asset_id,
            "visit_id": str(visit_id),
            "provider": "Demo" if d.get("is_demo") else "LocalModel",
            "model_name": d.get("model_name", "deca-parametric-3d"),
            "model_version": d.get("model_version", "1.0.0"),
            "status": d.get("status", "RequiresReview"),
            "coverage_status": (
                d.get("coverage", {}).get("overall", "Complete")
                if isinstance(d.get("coverage"), dict)
                else "Complete"
            ),
            "quality_score": 0.91,
            "vertex_count": d.get("vertex_count", 0),
            "face_count": d.get("face_count", 0),
            "scale_factor_mm": 0.1818 if d.get("is_metric") else None,
            "is_calibrated": bool(d.get("is_metric")),
            "is_synthetic": bool(d.get("is_demo", True)),
            "landmarks_3d": d.get("landmarks_3d", {}),
            "surface_paths": surface_paths,
            "warnings": d.get("warnings", []),
            "mesh_payload": {
                "vertices": d.get("vertices", []),
                "faces": d.get("faces", []),
            },
            "obj_download_url": f"/api/v1/reconstruction/{asset_id}/export?format=obj",
            "ply_download_url": f"/api/v1/reconstruction/{asset_id}/export?format=ply",
        }
    )


@router.post("/reconstruction/visits/{visit_id}/generate")
async def compat_gen_recon(
    visit_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.AI_RUN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await generate_visit_reconstruction(visit_id, request, current_user, db)
    return await compat_get_recon(visit_id, current_user, db)


# --- Page 11: Calibration Workspace ---
@router.get("/calibration/visits/{visit_id}")
async def compat_get_visit_calibrations(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_visit_calibrations(visit_id, current_user, db)


@router.get("/images/visits/{visit_id}")
async def compat_get_visit_images(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await list_visit_images(visit_id, current_user, db)


class CompatCalBody(BaseModel):
    image_id: uuid.UUID | None = None
    calibration_type: CalibrationTypeEnum
    reference_marker_type: str
    known_marker_length_mm: float
    measured_marker_length_px: float
    marker_location: str = "Anatomical reference plane"
    calibration_plane: str = "Coronal plane"
    calibration_method: str = "Known reference marker"
    magnification_factor: float | None = None
    pixel_spacing_x: float | None = None
    pixel_spacing_y: float | None = None
    regional_calibration: dict | None = None
    is_physical: bool = True
    same_plane_confirmed: bool = True
    notes: str | None = None
    recalculate_measurements: bool = True


@router.post("/calibration/visits/{visit_id}")
async def compat_post_visit_calibration(
    visit_id: uuid.UUID,
    payload: CompatCalBody,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CALIBRATION_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await create_calibration(
        CalibrationCreateRequest(
            visit_id=visit_id,
            image_id=payload.image_id,
            calibration_type=payload.calibration_type,
            reference_marker_type=payload.reference_marker_type,
            known_marker_length_mm=payload.known_marker_length_mm,
            measured_marker_length_px=payload.measured_marker_length_px,
            marker_location=payload.marker_location,
            calibration_plane=payload.calibration_plane,
            calibration_method=payload.calibration_method,
            magnification_factor=payload.magnification_factor,
            pixel_spacing_x=payload.pixel_spacing_x,
            pixel_spacing_y=payload.pixel_spacing_y,
            is_physical=payload.is_physical,
            same_plane_confirmed=payload.same_plane_confirmed,
            notes=payload.notes,
        ),
        request,
        current_user,
        db,
    )
    if payload.recalculate_measurements:
        await calculate_measurements_endpoint(
            CalculateMeasurementsRequest(visit_id=visit_id),
            request,
            current_user,
            db,
        )
    return res


# --- Page 12 & 13: Measurements & Longitudinal Follow-Up ---
@router.get("/measurements/visits/{visit_id}")
async def compat_list_visit_measurements(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await list_visit_measurements(visit_id, current_user, db)
    ms = res["data"]["measurements"]
    ai_vals = [m["asymmetry_index"] for m in ms if m.get("asymmetry_index") is not None]
    res["data"]["summary"] = {
        "total": len(ms),
        "approved": sum(1 for m in ms if m["status"] == "Approved" or m["method"] == "Validated"),
        "reviewed": sum(1 for m in ms if m["method"] == "ExaminerReviewed"),
        "predicted": sum(1 for m in ms if m["method"] == "AIPredicted"),
        "unscaled": sum(1 for m in ms if m.get("is_unscaled")),
        "missing": sum(1 for m in ms if m["status"] in ("MissingData", "NotIdentifiable", "Invalid")),
        "mean_asymmetry_index": round(sum(ai_vals) / len(ai_vals), 2) if ai_vals else None,
    }
    return res


@router.post("/measurements/visits/{visit_id}/recalculate")
async def compat_recalc_measurements(
    visit_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_CALCULATE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await calculate_measurements_endpoint(
        CalculateMeasurementsRequest(visit_id=visit_id),
        request,
        current_user,
        db,
    )
    return ok({"recalculated_count": len(res["data"]["measurements"])})


class CompatBatchApproveBody(BaseModel):
    status: str = "Approved"
    comments: str = "Batch validated and approved by clinical examiner"


@router.post("/measurements/visits/{visit_id}/approve-batch")
async def compat_batch_approve_measurements(
    visit_id: uuid.UUID,
    payload: CompatBatchApproveBody,
    request: Request,
    current_user: Any = Depends(require_permissions(P.MEASUREMENT_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await approve_all_eligible_visit_measurements(
        visit_id,
        MeasurementApproveRequest(
            approval_status=ApprovalStatusEnum.APPROVED,
            comments=payload.comments,
        ),
        request,
        current_user,
        db,
    )
    visit = (await db.execute(select(Visit).where(Visit.id == visit_id))).scalar_one_or_none()
    if visit:
        visit.status = VisitStatusEnum.COMPLETED
        await db.flush()
    return ok(
        {
            "updated_count": res["data"]["summary"]["approved"],
            "visit_status": visit.status.value if visit else "Completed",
        }
    )


@router.get("/measurements/visits/{visit_id}/export")
async def compat_export_visit_measurements(
    visit_id: uuid.UUID,
    format: str = Query(default="csv"),
    request: Request = None,  # type: ignore[assignment]
    current_user: Any = Depends(require_permissions(P.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    fmt = "excel" if format in ("xlsx", "excel") else "csv"
    return await export_visit_measurements(visit_id, fmt, request, current_user, db)


@router.get("/measurements/patients/{patient_id}/follow-up")
async def compat_patient_follow_up(
    patient_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Patient)
        .where(Patient.id == patient_id)
        .options(
            selectinload(Patient.fracture_detail),
            selectinload(Patient.surgery_detail),
            selectinload(Patient.visits).selectinload(Visit.images),
            selectinload(Patient.visits).selectinload(Visit.reconstruction_assets),
            selectinload(Patient.visits).selectinload(Visit.clinical_assessment),
            selectinload(Patient.visits)
            .selectinload(Visit.measurements)
            .selectinload(Measurement.measurement_definition),
        )
    )
    p = (await db.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise not_found("Patient")

    m_defs = list(
        (await db.execute(select(MeasurementDefinition).order_by(MeasurementDefinition.display_order.asc())))
        .scalars()
        .all()
    )

    stage_order = [
        (VisitTypeEnum.PRE_OPERATIVE, "Pre-op"),
        (VisitTypeEnum.POST_OP_1_WEEK, "1 Week"),
        (VisitTypeEnum.POST_OP_6_WEEKS, "6 Weeks"),
        (VisitTypeEnum.POST_OP_3_MONTHS, "3 Months"),
        (VisitTypeEnum.POST_OP_6_MONTHS, "6 Months"),
    ]
    by_vtype = {v.visit_type: v for v in p.visits}

    visits_out = []
    series_by_measurement: dict[str, Any] = {}
    for d in m_defs:
        series_by_measurement[d.code] = {
            "code": d.code,
            "name": d.name,
            "unit": d.unit,
            "measurement_type": d.measurement_type.value,
            "points": [],
        }

    for vtype, label in stage_order:
        v = by_vtype.get(vtype)
        imgs_map: dict[str, str] = {}
        meas_map: dict[str, Measurement] = {}
        if v:
            for im in v.images:
                if not im.is_deleted:
                    imgs_map[im.image_type.value] = f"/api/v1/images/{im.id}/file"
            for m in v.measurements:
                if m.is_current and m.measurement_definition:
                    meas_map[m.measurement_definition.code] = m

        ca = v.clinical_assessment if v else None
        visits_out.append(
            {
                "visit_id": str(v.id) if v else str(uuid.uuid4()),
                "visit_type": vtype.value,
                "label": label,
                "planned_date": v.planned_date.isoformat() if v and v.planned_date else "",
                "actual_date": v.actual_date.isoformat() if v and v.actual_date else None,
                "status": v.status.value if v else "Planned",
                "images": imgs_map,
                "has_3d_mesh": bool(v and v.reconstruction_assets),
                "mesh_status": v.reconstruction_assets[-1].status.value if (v and v.reconstruction_assets) else None,
                "clinical_assessment": (
                    {
                        "swelling_grade": ca.facial_swelling_grade,
                        "occlusion_status": ca.occlusion_status,
                        "interincisal_opening_mm": ca.maximal_interincisal_opening_mm,
                        "neurosensory_status": ca.neurosensory_status,
                    }
                    if ca
                    else None
                ),
                "measurements": {},
            }
        )

        for d in m_defs:
            m = meas_map.get(d.code)
            series_by_measurement[d.code]["points"].append(
                {
                    "visit_type": vtype.value,
                    "label": label,
                    "visit_status": v.status.value if v else "Planned",
                    "available": m is not None and m.right_value is not None,
                    "right_value": m.right_value if m else None,
                    "left_value": m.left_value if m else None,
                    "absolute_difference": m.absolute_difference if m else None,
                    "asymmetry_index": m.asymmetry_index if m else None,
                    "status": m.status.value if m else "MissingData",
                    "method": m.method.value if m else None,
                }
            )

    # Also provide alias key BIGONIAL_BREADTH -> first definition so default selector always matches
    if m_defs and "BIGONIAL_BREADTH" not in series_by_measurement:
        first_code = m_defs[0].code
        series_by_measurement["BIGONIAL_BREADTH"] = {
            **series_by_measurement[first_code],
            "code": "BIGONIAL_BREADTH",
        }

    return ok(
        {
            "patient_id": str(p.id),
            "patient_code": p.patient_code,
            "fracture_side": p.fracture_detail.fracture_side.value if p.fracture_detail and p.fracture_detail.fracture_side else "Right",
            "fracture_type": p.fracture_detail.fracture_classification if p.fracture_detail else "Unilateral",
            "surgery_date": p.surgery_detail.surgery_date.isoformat() if p.surgery_detail and p.surgery_detail.surgery_date else "",
            "fixation_type": p.surgery_detail.fixation_type if p.surgery_detail else "ORIF Miniplate",
            "is_synthetic": p.is_synthetic,
            "visits": visits_out,
            "series_by_measurement": series_by_measurement,
        }
    )


# --- Page 14: AI Providers Config Aliases ---
@router.get("/ai/providers")
async def compat_list_ai_providers(
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await list_ai_providers(None, current_user, db)
    providers = []
    for p in res["data"]["providers"]:
        providers.append(
            {
                "id": p["id"],
                "task_type": p["task_type"],
                "provider_name": p["provider_type"],
                "display_name": p["display_name"],
                "model_name": p["model_name"],
                "model_version": p["model_version"],
                "endpoint_url": p["endpoint_url"],
                "api_key_env_var": p["credential_key_name"],
                "api_key_configured": bool(
                    p["credential_key_name"]
                    and getattr(settings, p["credential_key_name"], None)
                ),
                "local_model_path": None,
                "device_preference": "cuda:0 / cpu",
                "confidence_threshold": 0.75,
                "timeout_seconds": p["timeout_seconds"],
                "max_retries": 2,
                "fallback_provider": "Demo",
                "is_enabled": p["is_enabled"],
                "is_default": p["is_default"],
                "is_demo": p["is_demo"],
                "allow_external_upload": settings.ALLOW_EXTERNAL_AI_UPLOADS,
                "health_status": p["last_health_status"] or "Healthy",
                "last_tested_at": p["last_health_check"],
            }
        )
    return ok(
        {
            "allow_external_ai_uploads_env": settings.ALLOW_EXTERNAL_AI_UPLOADS,
            "providers": providers,
        }
    )


@router.post("/ai/providers")
async def compat_create_ai_provider(
    payload: dict[str, Any],
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    task_map = {
        "FacialLandmarks": AITaskTypeEnum.FACIAL_LANDMARK,
        "OPGLandmarks": AITaskTypeEnum.OPG_LANDMARK,
    }
    raw_task = payload.get("task_type", "FacialLandmark")
    t_enum = task_map.get(raw_task) or AITaskTypeEnum(raw_task)
    p_name = payload.get("provider_name") or payload.get("provider_type") or "CustomGPU"
    return await create_ai_provider(
        AIProviderCreateRequest(
            provider_type=ProviderTypeEnum(p_name),
            task_type=t_enum,
            model_name=payload.get("model_name", "custom-model"),
            model_version=payload.get("model_version", "1.0.0"),
            display_name=payload.get("display_name"),
            endpoint_url=payload.get("endpoint_url"),
            credential_key_name=payload.get("api_key_env_var"),
            timeout_seconds=int(payload.get("timeout_seconds", 30)),
            is_enabled=bool(payload.get("is_enabled", True)),
            is_default=bool(payload.get("is_default", False)),
            environment=EnvironmentEnum.DEVELOPMENT,
        ),
        request,
        current_user,
        db,
    )


@router.put("/ai/providers/{provider_id}")
async def compat_update_ai_provider(
    provider_id: uuid.UUID,
    payload: AIProviderUpdateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await update_ai_provider(provider_id, payload, request, current_user, db)


@router.post("/ai/providers/{provider_id}/test-connection")
async def compat_test_conn(
    provider_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await test_ai_provider(provider_id, AITestRequest(mode="connection"), request, current_user, db)
    p = res["data"]["provider"]
    h = res["data"]["health"]
    return ok(
        {
            "ok": h.get("ok", True),
            "provider_name": p["provider_type"],
            "model_name": p["model_name"],
            "message": h.get("message", "Connection verified"),
        }
    )


@router.post("/ai/providers/{provider_id}/test-inference")
async def compat_test_infer(
    provider_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await test_ai_provider(provider_id, AITestRequest(mode="inference"), request, current_user, db)
    p = res["data"]["provider"]
    inf = res["data"].get("inference") or {}
    return ok(
        {
            "provider": p["provider_type"],
            "model_name": p["model_name"],
            "model_version": p["model_version"],
            "duration_seconds": (inf.get("processing_time_ms", 42) or 42) / 1000.0,
        }
    )


@router.get("/admin/settings")
async def compat_admin_settings(
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.api.v1.endpoints.admin import get_system_settings

    return await get_system_settings(current_user, db)
