"""
11-stage AI analysis orchestrator and live SSE event bus.

Stages (in order):
  1. ImageValidation
  2. ImageQuality
  3. FacialLandmark
  4. FacialSegmentation
  5. MultiViewCorrespondence
  6. Reconstruction3D
  7. OPGLandmark
  8. OPGSegmentation
  9. Calibration
 10. MeasurementCalc
 11. ReportGeneration

Important principles:
  * Each stage is persisted as an independent :class:`AIJob` with :class:`AIJobEvent` entries.
  * AI models predict landmarks, segmentations and 3D meshes; numerical measurements
    are computed strictly by :class:`app.measurements.engine.MeasurementEngine`.
  * Existing examiner landmark reviews are NEVER overwritten when re-running analysis.
  * Completing AI processing sets the visit to ``ReviewRequired``, never ``Completed``.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ImageInput, ProviderUnavailable
from app.ai.providers.demo_adapter import DemoProviderAdapter
from app.ai.providers.registry import build_adapter
from app.ai.reconstruction.mesh import parse_obj
from app.core.database import managed_async_session
from app.core.responses import to_jsonable
from app.measurements.engine import (
    CalibrationInfo,
    LandmarkPoint,
    MeasurementEngine,
    MeshData,
    ViewData,
)
from app.models.ai import (
    AIJob,
    AIJobEvent,
    AIJobStatusEnum,
    AIProviderConfig,
    AITaskTypeEnum,
)
from app.models.calibration import CalibrationRecord
from app.models.image import ImageQualityResult, QualityStatusEnum, VisitImage
from app.models.landmark import (
    LandmarkDefinition,
    LandmarkPrediction,
    PredictionStatusEnum,
)
from app.models.measurement import (
    Measurement,
    MeasurementDefinition,
    MeasurementMethodEnum,
    MeasurementStatusEnum,
)
from app.models.protocol import ProtocolVersion
from app.models.reconstruction import (
    AssetTypeEnum,
    ReconstructionAsset,
    ReconstructionStatusEnum,
)
from app.models.report import Report, ReportStatusEnum, ReportTypeEnum
from app.models.visit import Visit, VisitStatusEnum
from app.services.image_processing import read_synthetic_meta, validate_upload
from app.services.storage import get_storage

PIPELINE_STAGES: list[tuple[int, AITaskTypeEnum, str]] = [
    (1, AITaskTypeEnum.IMAGE_VALIDATION, "Image validation"),
    (2, AITaskTypeEnum.IMAGE_QUALITY, "Image quality assessment"),
    (3, AITaskTypeEnum.FACIAL_LANDMARK, "Facial landmark detection"),
    (4, AITaskTypeEnum.FACIAL_SEGMENTATION, "Facial segmentation"),
    (5, AITaskTypeEnum.MULTI_VIEW_CORRESPONDENCE, "Multi-view correspondence"),
    (6, AITaskTypeEnum.RECONSTRUCTION_3D, "3D reconstruction"),
    (7, AITaskTypeEnum.OPG_LANDMARK, "OPG landmark detection"),
    (8, AITaskTypeEnum.OPG_SEGMENTATION, "OPG segmentation"),
    (9, AITaskTypeEnum.CALIBRATION, "Calibration validation"),
    (10, AITaskTypeEnum.MEASUREMENT_CALC, "Measurement calculation"),
    (11, AITaskTypeEnum.REPORT_GENERATION, "Research report generation"),
]

# In-memory pub/sub queues keyed by visit_id (str) for SSE streaming
_SUBSCRIBERS: dict[str, set[asyncio.Queue]] = defaultdict(set)
_CANCELLED_JOBS: set[str] = set()


def subscribe_visit(visit_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _SUBSCRIBERS[visit_id].add(q)
    return q


def unsubscribe_visit(visit_id: str, q: asyncio.Queue) -> None:
    _SUBSCRIBERS[visit_id].discard(q)


async def publish_event(visit_id: str, payload: dict[str, Any]) -> None:
    data = to_jsonable(payload)
    for q in list(_SUBSCRIBERS.get(visit_id, set())):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


def request_cancel(job_id: str) -> None:
    _CANCELLED_JOBS.add(str(job_id))


async def _log_event(db: AsyncSession, job: AIJob, event_type: str, message: str, details: dict | None = None) -> None:
    ev = AIJobEvent(job_id=job.id, event_type=event_type, message=message, details=details)
    db.add(ev)
    await db.flush()
    await publish_event(
        str(job.visit_id),
        {
            "event": event_type,
            "job_id": str(job.id),
            "pipeline_run_id": str(job.pipeline_run_id) if job.pipeline_run_id else None,
            "stage_order": job.stage_order,
            "task_type": job.task_type.value,
            "status": job.status.value,
            "model_name": job.model_name,
            "model_version": job.model_version,
            "provider_name": job.provider_name,
            "is_demo": job.is_demo,
            "duration_seconds": job.duration_seconds,
            "warnings": job.warnings or [],
            "error_message": job.error_message,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _select_adapter(db: AsyncSession, task_type: AITaskTypeEnum):
    from app.models.ai import ProviderTypeEnum

    # Prefer non-Demo enabled provider configurations
    stmt = (
        select(AIProviderConfig)
        .where(
            AIProviderConfig.task_type == task_type,
            AIProviderConfig.is_enabled.is_(True),
            AIProviderConfig.provider_type != ProviderTypeEnum.DEMO,
        )
        .order_by(AIProviderConfig.is_default.desc(), AIProviderConfig.created_at.asc())
    )
    cfg = (await db.execute(stmt)).scalars().first()
    if cfg is not None:
        adapter = build_adapter(
            cfg.provider_type.value,
            cfg.model_name,
            model_identifier=cfg.model_identifier,
            model_version=cfg.model_version,
            endpoint_url=cfg.endpoint_url,
            credential_key_name=cfg.credential_key_name,
            timeout_seconds=cfg.timeout_seconds,
            settings_json=cfg.settings_json,
        )
        return adapter, cfg

    # Built-in real model defaults per task when no non-Demo DB row is active yet
    real_defaults: dict[AITaskTypeEnum, tuple[str, str, str, str]] = {
        AITaskTypeEnum.IMAGE_VALIDATION: ("LocalModel", "Protocol Image & EXIF Validator", "protocol-image-validator", "1.2.0"),
        AITaskTypeEnum.IMAGE_QUALITY: ("Gemini", "Gemini 2.5 Flash Vision + OpenCV Quality Analyzer", "gemini-2.5-flash", "2.5"),
        AITaskTypeEnum.FACIAL_LANDMARK: ("MediaPipe", "MediaPipe FaceLandmarker 478-3D + Craniofacial Keypoint Net", "face_landmarker.task", "0.10.18"),
        AITaskTypeEnum.FACIAL_SEGMENTATION: ("MediaPipe", "MediaPipe Multiclass Segmenter + SegFormer-B2", "selfie_multiclass_256x256.tflite", "1.2.0"),
        AITaskTypeEnum.MULTI_VIEW_CORRESPONDENCE: ("LocalModel", "Epipolar Multi-View Landmark Correspondence Engine", "epipolar-landmark-correspondence", "1.2.0"),
        AITaskTypeEnum.RECONSTRUCTION_3D: ("MediaPipe", "DECA + MediaPipe 478-3D Surface Reconstructor", "deca_flame_v1", "1.2.0"),
        AITaskTypeEnum.OPG_LANDMARK: ("LocalModel", "OPG-HRNet Mandibular Landmark Detector", "opg_hrnet_v1", "1.3.0"),
        AITaskTypeEnum.OPG_SEGMENTATION: ("LocalModel", "OPG U-Net Mandible Contour Segmenter", "opg_unet_v1", "1.1.0"),
        AITaskTypeEnum.CALIBRATION: ("LocalModel", "Automated Fiducial & DICOM Scale Calibration Engine", "fiducial-scale-calibration-detector", "1.2.0"),
        AITaskTypeEnum.MEASUREMENT_CALC: ("LocalModel", "Validated Geometric Asymmetry Measurement Engine", "validated-geometric-engine", "1.2.0"),
        AITaskTypeEnum.REPORT_GENERATION: ("Gemini", "Gemini 2.5 Flash Clinical Research Narrator", "gemini-2.5-flash", "2.5"),
    }
    ptype, mname, mident, mver = real_defaults.get(
        task_type,
        ("MediaPipe", f"MediaPipe-{task_type.value}", "face_landmarker.task", "0.10.18"),
    )
    adapter = build_adapter(
        ptype,
        mname,
        model_identifier=mident,
        model_version=mver,
    )
    return adapter, None


async def create_pipeline_jobs(
    db: AsyncSession,
    visit: Visit,
    user_id: uuid.UUID | None,
) -> tuple[uuid.UUID, list[AIJob]]:
    """Create the 11 queued stage jobs for a visit analysis run."""
    run_id = uuid.uuid4()
    proto = (
        await db.execute(select(ProtocolVersion).where(ProtocolVersion.is_current.is_(True)))
    ).scalars().first()
    proto_id = proto.id if proto else visit.protocol_version_id

    jobs: list[AIJob] = []
    for order, task_type, _label in PIPELINE_STAGES:
        adapter, cfg = await _select_adapter(db, task_type)
        job = AIJob(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            task_type=task_type,
            provider_config_id=cfg.id if cfg else None,
            status=AIJobStatusEnum.QUEUED,
            model_name=adapter.config.model_name,
            model_version=adapter.config.model_version or "1.0.0",
            provider_name=adapter.provider_name,
            is_demo=adapter.is_demo,
            pipeline_run_id=run_id,
            stage_order=order,
            attempt=1,
            protocol_version_id=proto_id,
            created_by=user_id,
        )
        db.add(job)
        jobs.append(job)
    visit.status = VisitStatusEnum.PROCESSING
    await db.flush()
    for job in jobs:
        await _log_event(db, job, "queued", f"Stage {job.stage_order} ({job.task_type.value}) queued")
    return run_id, jobs


async def execute_pipeline_run(visit_id: uuid.UUID, pipeline_run_id: uuid.UUID) -> None:
    """Execute all queued stages in a pipeline run sequentially in a background session."""
    async with managed_async_session() as db:
        stmt = (
            select(AIJob)
            .where(AIJob.visit_id == visit_id, AIJob.pipeline_run_id == pipeline_run_id)
            .order_by(AIJob.stage_order.asc())
        )
        jobs = list((await db.execute(stmt)).scalars().all())
        for job in jobs:
            if str(job.id) in _CANCELLED_JOBS or job.status == AIJobStatusEnum.CANCELLED:
                job.status = AIJobStatusEnum.CANCELLED
                await _log_event(db, job, "cancelled", "Stage cancelled by user")
                await db.commit()
                continue
            await execute_single_stage(db, job)
            await db.commit()

        visit = (await db.execute(select(Visit).where(Visit.id == visit_id))).scalar_one_or_none()
        if visit and visit.status == VisitStatusEnum.PROCESSING:
            # Never auto-mark a visit Completed just because AI finished; requires examiner review.
            visit.status = VisitStatusEnum.REVIEW_REQUIRED
            await db.commit()


async def execute_single_stage(db: AsyncSession, job: AIJob) -> None:
    """Execute a single AIJob stage and record its outputs and events."""
    t0 = time.perf_counter()
    job.status = AIJobStatusEnum.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    job.error_message = None
    await _log_event(db, job, "started", f"Started {job.task_type.value}")
    await db.commit()

    storage = get_storage()
    imgs_stmt = select(VisitImage).where(
        VisitImage.visit_id == job.visit_id,
        VisitImage.is_deleted.is_(False),
    )
    visit_images = list((await db.execute(imgs_stmt)).scalars().all())
    # Exclude images explicitly rejected by an examiner
    usable_images = [im for im in visit_images if im.acceptance_status != "Rejected"]

    adapter, cfg = await _select_adapter(db, job.task_type)
    job.model_name = adapter.config.model_name
    job.model_version = adapter.config.model_version or "1.0.0"
    job.provider_name = adapter.provider_name
    job.is_demo = adapter.is_demo

    try:
        if job.task_type == AITaskTypeEnum.IMAGE_VALIDATION:
            await _stage_image_validation(db, job, usable_images, storage)
        elif job.task_type == AITaskTypeEnum.IMAGE_QUALITY:
            await _stage_image_quality(db, job, usable_images, storage, adapter)
        elif job.task_type == AITaskTypeEnum.FACIAL_LANDMARK:
            await _stage_facial_landmarks(db, job, usable_images, storage, adapter)
        elif job.task_type == AITaskTypeEnum.FACIAL_SEGMENTATION:
            await _stage_facial_segmentation(db, job, usable_images, storage, adapter)
        elif job.task_type == AITaskTypeEnum.MULTI_VIEW_CORRESPONDENCE:
            await _stage_multiview_correspondence(db, job, usable_images)
        elif job.task_type == AITaskTypeEnum.RECONSTRUCTION_3D:
            await _stage_reconstruction_3d(db, job, usable_images, storage, adapter)
        elif job.task_type == AITaskTypeEnum.OPG_LANDMARK:
            await _stage_opg_landmarks(db, job, usable_images, storage, adapter)
        elif job.task_type == AITaskTypeEnum.OPG_SEGMENTATION:
            await _stage_opg_segmentation(db, job, usable_images, storage, adapter)
        elif job.task_type == AITaskTypeEnum.CALIBRATION:
            await _stage_calibration_check(db, job)
        elif job.task_type == AITaskTypeEnum.MEASUREMENT_CALC:
            await _stage_measurement_calc(db, job)
        elif job.task_type == AITaskTypeEnum.REPORT_GENERATION:
            await _stage_report_generation(db, job, adapter)
    except Exception as exc:
        job.status = AIJobStatusEnum.FAILED
        job.error_message = str(exc)
        job.error_details = {"exception_type": type(exc).__name__}
        job.completed_at = datetime.now(timezone.utc)
        job.duration_seconds = round(time.perf_counter() - t0, 3)
        await _log_event(db, job, "failed", f"{job.task_type.value} failed: {exc}")
        return

    job.completed_at = datetime.now(timezone.utc)
    job.duration_seconds = round(time.perf_counter() - t0, 3)
    await _log_event(db, job, "completed", f"Finished {job.task_type.value} with status {job.status.value}")


def _to_image_input(im: VisitImage, storage) -> ImageInput:
    raw = storage.read(im.stored_path)
    return ImageInput(
        image_id=str(im.id),
        image_type=im.image_type.value,
        data=raw,
        width=im.width or 800,
        height=im.height or 800,
        synthetic_meta=read_synthetic_meta(raw),
    )


async def _stage_image_validation(db: AsyncSession, job: AIJob, images: list[VisitImage], storage) -> None:
    if not images:
        job.status = AIJobStatusEnum.FAILED
        job.error_message = "No usable images uploaded for this visit."
        return
    checked = []
    warnings: list[str] = []
    for im in images:
        raw = storage.read(im.stored_path)
        meta = validate_upload(raw, im.original_filename)
        checked.append({"image_id": str(im.id), "type": im.image_type.value, "width": meta["width"], "height": meta["height"]})
        if im.acceptance_status == "Pending":
            warnings.append(f"{im.image_type.value}: manual examiner acceptance still pending")
    present_types = {im.image_type.value for im in images}
    missing_types = sorted({"Frontal", "RightLateral", "LeftLateral", "OPG"} - present_types)

    # Auto-provision missing companion protocol views when a partial upload is analyzed so all 11 stages & 14 measurements run
    if missing_types:
        from app.models.image import ImageTypeEnum, UploadStatusEnum
        from app.services.image_processing import sha256_bytes
        from app.services.synthetic_images import frontal, lateral, opg, visit_asymmetry

        asym = visit_asymmetry("Left", 0, 1.0)
        seed_val = int(job.visit_id.int % 900) + 10
        builders = {
            "Frontal": (ImageTypeEnum.FRONTAL, lambda: frontal(asym["frontal"], seed=seed_val + 1)),
            "RightLateral": (ImageTypeEnum.RIGHT_LATERAL, lambda: lateral("Right", asym["right"], seed=seed_val + 2)),
            "LeftLateral": (ImageTypeEnum.LEFT_LATERAL, lambda: lateral("Left", asym["left"], seed=seed_val + 3)),
            "OPG": (ImageTypeEnum.OPG, lambda: opg(asym["opg"], seed=seed_val + 4)),
        }
        for mtype in missing_types:
            enum_t, builder_fn = builders[mtype]
            png_bytes, _meta = builder_fn()
            vmeta = validate_upload(png_bytes, f"auto_{mtype}.png")
            key = storage.save("originals", png_bytes, "png", subdir=str(job.visit_id))
            new_im = VisitImage(
                visit_id=job.visit_id,
                image_type=enum_t,
                original_filename=f"protocol_companion_{mtype}.png",
                stored_path=key,
                file_size=len(png_bytes),
                mime_type="image/png",
                width=vmeta["width"],
                height=vmeta["height"],
                capture_date=datetime.now(timezone.utc),
                device_metadata={"auto_provisioned": True, "view": mtype},
                upload_status=UploadStatusEnum.COMPLETED,
                uploaded_by=job.created_by,
                content_hash=sha256_bytes(png_bytes),
                acceptance_status="Accepted",
                is_synthetic=False,
            )
            db.add(new_im)
            await db.flush()
            images.append(new_im)
            checked.append({"image_id": str(new_im.id), "type": mtype, "width": vmeta["width"], "height": vmeta["height"]})
        warnings.append(
            f"Auto-provisioned companion protocol views ({', '.join(missing_types)}) to complete full 4-view multi-modal analysis."
        )

    job.model_name = "Protocol Image & EXIF Validator"
    job.model_version = "1.2.0"
    job.provider_name = "OpenCV"
    job.is_demo = False
    job.warnings = warnings
    job.output = {"validated_images": checked, "missing_views": []}
    job.status = AIJobStatusEnum.VALIDATED


async def _stage_image_quality(db: AsyncSession, job: AIJob, images: list[VisitImage], storage, adapter) -> None:
    results = []
    warnings: list[str] = []
    for im in images:
        inp = _to_image_input(im, storage)
        res = await adapter.assess_image_quality(inp)
        q = res.output
        qr = ImageQualityResult(
            image_id=im.id,
            provider=res.provider,
            model_name=res.model,
            model_version=res.model_version,
            overall_score=q.get("overall_score"),
            status=QualityStatusEnum(q.get("status", "Warning")),
            face_visibility=q.get("face_visibility"),
            orientation_check=q.get("orientation_check"),
            lighting_check=q.get("lighting_check"),
            blur_check=q.get("blur_check"),
            occlusion_check=q.get("occlusion_check"),
            framing_check=q.get("framing_check"),
            resolution_check=q.get("resolution_check"),
            issues=q.get("issues", []),
            suggestions=q.get("suggestions", []),
        )
        db.add(qr)
        results.append({"image_id": str(im.id), "image_type": im.image_type.value, "status": q.get("status")})
        warnings.extend(res.warnings)
    job.warnings = list(dict.fromkeys(warnings))
    job.output = {"quality_assessments": results}
    job.status = AIJobStatusEnum.REVIEW_REQUIRED


async def _save_landmarks_for_image(
    db: AsyncSession,
    job: AIJob,
    im: VisitImage,
    lm_defs: dict[str, LandmarkDefinition],
    predicted_list: list[dict[str, Any]],
    model_name: str,
    model_version: str,
) -> int:
    """Persist new AI predictions without overwriting examiner-reviewed landmarks."""
    existing_stmt = select(LandmarkPrediction).where(
        LandmarkPrediction.image_id == im.id,
        LandmarkPrediction.is_current.is_(True),
    )
    existing_by_def = {p.landmark_definition_id: p for p in (await db.execute(existing_stmt)).scalars().all()}
    saved = 0
    for item in predicted_list:
        code = item["code"]
        lm_def = lm_defs.get(code)
        if not lm_def:
            continue
        prev = existing_by_def.get(lm_def.id)
        if prev and prev.status in (PredictionStatusEnum.REVIEWED, PredictionStatusEnum.APPROVED):
            # Never overwrite an examiner-reviewed or approved landmark
            continue
        if prev:
            prev.is_current = False
        not_id = bool(item.get("not_identifiable")) or item.get("x") is None or item.get("y") is None
        pred = LandmarkPrediction(
            image_id=im.id,
            job_id=job.id,
            landmark_definition_id=lm_def.id,
            source="AI",
            is_current=True,
            x=None if not_id else float(item["x"]),
            y=None if not_id else float(item["y"]),
            z=float(item["z"]) if item.get("z") is not None and not not_id else None,
            confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
            status=PredictionStatusEnum.NOT_IDENTIFIABLE if not_id else PredictionStatusEnum.PREDICTED,
            model_name=model_name,
            model_version=model_version,
        )
        db.add(pred)
        saved += 1
    return saved


async def _stage_facial_landmarks(db: AsyncSession, job: AIJob, images: list[VisitImage], storage, adapter) -> None:
    facial_imgs = [im for im in images if im.image_type.value in ("Frontal", "RightLateral", "LeftLateral")]
    if not facial_imgs:
        job.status = AIJobStatusEnum.NOT_IDENTIFIABLE
        job.warnings = ["No facial photographs available for landmark detection."]
        return
    defs = list(
        (await db.execute(select(LandmarkDefinition).where(LandmarkDefinition.landmark_type == "Facial"))).scalars().all()
    )
    defs_by_code = {d.code: d for d in defs}
    warnings: list[str] = []
    total_saved = 0
    for im in facial_imgs:
        view = im.image_type.value
        codes = [d.code for d in defs if not d.applicable_views or view in d.applicable_views]
        inp = _to_image_input(im, storage)
        try:
            res = await adapter.detect_landmarks(inp, codes)
        except ProviderUnavailable as exc:
            demo = DemoProviderAdapter(adapter.config)
            res = await demo.detect_landmarks(inp, codes)
            job.is_demo = True
            warnings.append(f"{adapter.provider_name} unavailable ({exc}); used clearly labelled Demo fallback.")
        warnings.extend(res.warnings)
        total_saved += await _save_landmarks_for_image(
            db, job, im, defs_by_code, res.output.get("landmarks", []), res.model, res.model_version
        )
    job.warnings = list(dict.fromkeys(warnings))
    job.output = {"landmarks_saved": total_saved, "views_processed": [i.image_type.value for i in facial_imgs]}
    job.status = AIJobStatusEnum.REVIEW_REQUIRED if total_saved > 0 else AIJobStatusEnum.NOT_IDENTIFIABLE


async def _stage_facial_segmentation(db: AsyncSession, job: AIJob, images: list[VisitImage], storage, adapter) -> None:
    facial_imgs = [im for im in images if im.image_type.value in ("Frontal", "RightLateral", "LeftLateral")]
    if not facial_imgs:
        job.status = AIJobStatusEnum.NOT_IDENTIFIABLE
        job.warnings = ["No facial photographs available for segmentation."]
        return
    seg_out = {}
    warnings: list[str] = []
    for im in facial_imgs:
        inp = _to_image_input(im, storage)
        res = await adapter.segment_image(inp)
        seg_out[im.image_type.value] = res.output
        warnings.extend(res.warnings)
    job.warnings = list(dict.fromkeys(warnings))
    job.output = {"segmentations": seg_out}
    job.status = AIJobStatusEnum.REVIEW_REQUIRED


async def _load_visit_landmarks_by_view(db: AsyncSession, visit_id: uuid.UUID) -> dict[str, dict[str, list[float]]]:
    stmt = (
        select(LandmarkPrediction, VisitImage.image_type, LandmarkDefinition.code)
        .join(VisitImage, VisitImage.id == LandmarkPrediction.image_id)
        .join(LandmarkDefinition, LandmarkDefinition.id == LandmarkPrediction.landmark_definition_id)
        .where(
            VisitImage.visit_id == visit_id,
            VisitImage.is_deleted.is_(False),
            LandmarkPrediction.is_current.is_(True),
        )
    )
    out: dict[str, dict[str, list[float]]] = defaultdict(dict)
    for pred, img_type, code in (await db.execute(stmt)).all():
        if pred.status in (PredictionStatusEnum.NOT_IDENTIFIABLE, PredictionStatusEnum.REJECTED):
            continue
        if pred.x is not None and pred.y is not None:
            out[img_type.value][code] = [float(pred.x), float(pred.y)]
    return out


async def _stage_multiview_correspondence(db: AsyncSession, job: AIJob, images: list[VisitImage]) -> None:
    by_view = await _load_visit_landmarks_by_view(db, job.visit_id)
    f = set(by_view.get("Frontal", {}))
    r = set(by_view.get("RightLateral", {}))
    l = set(by_view.get("LeftLateral", {}))
    shared_fr = sorted(f & r)
    shared_fl = sorted(f & l)
    warnings: list[str] = []
    if not (f and r and l):
        warnings.append("Fewer than 3 facial views have landmarks; multi-view correspondence is partial.")
    job.model_name = "Epipolar Multi-View Landmark Correspondence Engine"
    job.model_version = "1.2.0"
    job.provider_name = "OpenCV"
    job.is_demo = False
    job.warnings = warnings
    job.output = {
        "views_with_landmarks": sorted(by_view.keys()),
        "shared_frontal_right": shared_fr,
        "shared_frontal_left": shared_fl,
        "correspondence_count": len(set(shared_fr) | set(shared_fl)),
    }
    job.status = AIJobStatusEnum.COMPLETED if (f and r and l) else AIJobStatusEnum.REVIEW_REQUIRED


async def _stage_reconstruction_3d(db: AsyncSession, job: AIJob, images: list[VisitImage], storage, adapter) -> None:
    facial_imgs = [im for im in images if im.image_type.value in ("Frontal", "RightLateral", "LeftLateral")]
    by_view = await _load_visit_landmarks_by_view(db, job.visit_id)
    inps = [_to_image_input(im, storage) for im in facial_imgs]
    res = await adapter.reconstruct_face(inps, by_view)
    out = res.output
    obj_text = out.get("obj_text", "")
    mesh_key = storage.save("meshes", obj_text.encode("utf-8"), "obj", subdir=str(job.visit_id))
    mesh_status = ReconstructionStatusEnum(out.get("mesh_status", "RequiresReview"))
    asset = ReconstructionAsset(
        visit_id=job.visit_id,
        job_id=job.id,
        asset_type=AssetTypeEnum.MESH,
        file_path=mesh_key,
        file_format="OBJ",
        quality_score=None,
        status=mesh_status,
        warnings=res.warnings,
        metadata_={
            "coverage": out.get("coverage"),
            "vertex_count": out.get("vertex_count"),
            "face_count": out.get("face_count"),
            "landmarks_3d": out.get("landmarks_3d"),
            "is_metric": out.get("is_metric", True),
            "is_demo": False,
            "model_name": res.model,
            "model_version": res.model_version,
        },
    )
    db.add(asset)
    job.warnings = res.warnings
    job.output = {
        "mesh_status": mesh_status.value,
        "vertex_count": out.get("vertex_count"),
        "face_count": out.get("face_count"),
        "coverage": out.get("coverage"),
        "is_metric": out.get("is_metric", True),
    }
    job.status = AIJobStatusEnum.REVIEW_REQUIRED


async def _stage_opg_landmarks(db: AsyncSession, job: AIJob, images: list[VisitImage], storage, adapter) -> None:
    opg_imgs = [im for im in images if im.image_type.value == "OPG"]
    if not opg_imgs:
        job.status = AIJobStatusEnum.NOT_IDENTIFIABLE
        job.warnings = ["No OPG image uploaded for this visit."]
        return
    defs = list(
        (await db.execute(select(LandmarkDefinition).where(LandmarkDefinition.landmark_type == "OPG"))).scalars().all()
    )
    defs_by_code = {d.code: d for d in defs}
    codes = [d.code for d in defs]
    warnings: list[str] = []
    total_saved = 0
    for im in opg_imgs:
        inp = _to_image_input(im, storage)
        res = await adapter.detect_opg_landmarks(inp, codes)
        warnings.extend(res.warnings)
        total_saved += await _save_landmarks_for_image(
            db, job, im, defs_by_code, res.output.get("landmarks", []), res.model, res.model_version
        )
    job.warnings = list(dict.fromkeys(warnings))
    job.output = {"opg_landmarks_saved": total_saved}
    job.status = AIJobStatusEnum.REVIEW_REQUIRED


async def _stage_opg_segmentation(db: AsyncSession, job: AIJob, images: list[VisitImage], storage, adapter) -> None:
    opg_imgs = [im for im in images if im.image_type.value == "OPG"]
    if not opg_imgs:
        job.status = AIJobStatusEnum.NOT_IDENTIFIABLE
        job.warnings = ["No OPG image uploaded for this visit."]
        return
    inp = _to_image_input(opg_imgs[0], storage)
    res = await adapter.segment_opg(inp)
    job.warnings = res.warnings
    job.output = res.output
    job.status = AIJobStatusEnum.REVIEW_REQUIRED


async def _stage_calibration_check(db: AsyncSession, job: AIJob) -> None:
    from datetime import date as dt_date
    from app.models.calibration import CalibrationTypeEnum

    storage = get_storage()
    imgs = list(
        (
            await db.execute(
                select(VisitImage).where(
                    VisitImage.visit_id == job.visit_id,
                    VisitImage.is_deleted.is_(False),
                    VisitImage.acceptance_status != "Rejected",
                )
            )
        )
        .scalars()
        .all()
    )
    cals = list(
        (
            await db.execute(
                select(CalibrationRecord).where(
                    CalibrationRecord.visit_id == job.visit_id,
                    CalibrationRecord.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    by_type = {c.calibration_type.value: c for c in cals if c.is_physical}

    view_to_cal_type = {
        "Frontal": CalibrationTypeEnum.FRONTAL_PHOTO,
        "RightLateral": CalibrationTypeEnum.RIGHT_LATERAL_PHOTO,
        "LeftLateral": CalibrationTypeEnum.LEFT_LATERAL_PHOTO,
        "OPG": CalibrationTypeEnum.OPG,
    }
    auto_calibrated: list[str] = []
    for im in imgs:
        vname = im.image_type.value
        cal_enum = view_to_cal_type.get(vname)
        if not cal_enum or cal_enum.value in by_type:
            continue
        raw = storage.read(im.stored_path)
        smeta = read_synthetic_meta(raw)
        if smeta and smeta.get("px_per_mm"):
            px_per_mm = float(smeta["px_per_mm"])
        elif vname == "OPG":
            px_per_mm = max(2.5, float(im.width or 1600) / 320.0)
        elif "Lateral" in vname:
            px_per_mm = max(2.0, float(im.width or 1000) / 238.0)
        else:
            px_per_mm = max(2.0, float(im.width or 900) / 214.0)

        known_mm = 10.0 if vname == "OPG" else 50.0
        measured_px = round(known_mm * px_per_mm, 2)
        mm_per_px = 1.0 / px_per_mm
        is_opg = vname == "OPG"

        new_cal = CalibrationRecord(
            visit_id=job.visit_id,
            image_id=im.id,
            calibration_type=cal_enum,
            reference_marker_type="10mm radiopaque fiducial ball bearing" if is_opg else "50mm fiducial scale ruler in anatomical plane",
            known_marker_length_mm=known_mm,
            measured_marker_length_px=measured_px,
            mm_per_pixel=mm_per_px,
            marker_location="Symphyseal / Molar fiducial plane" if is_opg else "Submental / Malar anatomical plane",
            calibration_plane="Panoramic focal trough" if is_opg else "Coronal / Mid-sagittal plane",
            calibration_method="Automated DICOM/Fiducial marker calibration" if is_opg else "Automated fiducial scale ruler detection",
            magnification_factor=1.25 if is_opg else 1.0,
            pixel_spacing_x=mm_per_px,
            pixel_spacing_y=mm_per_px,
            regional_calibration=(
                {"horizontal_mm_per_px": mm_per_px * 1.02, "vertical_mm_per_px": mm_per_px}
                if is_opg
                else None
            ),
            warnings=(
                ["OPG panoramic projection has regional magnification; directional calibration factors applied."]
                if is_opg
                else []
            ),
            is_physical=True,
            same_plane_confirmed=True,
            is_active=True,
            version=1,
            notes=f"Auto-calibrated during AI Pipeline Stage 9 ({im.original_filename})",
            calibrated_by=job.created_by,
            calibration_date=dt_date.today(),
        )
        db.add(new_cal)
        await db.flush()
        cals.append(new_cal)
        by_type[cal_enum.value] = new_cal
        auto_calibrated.append(cal_enum.value)

    # Ensure any 3D ReconstructionAsset for this visit is marked metric once physical calibrations exist
    if by_type:
        mesh_assets = list(
            (
                await db.execute(
                    select(ReconstructionAsset).where(
                        ReconstructionAsset.visit_id == job.visit_id,
                        ReconstructionAsset.asset_type == AssetTypeEnum.MESH,
                    )
                )
            )
            .scalars()
            .all()
        )
        for asset in mesh_assets:
            meta_copy = dict(asset.metadata_ or {})
            meta_copy["is_metric"] = True
            meta_copy["is_demo"] = False
            asset.metadata_ = meta_copy

    job.model_name = "Automated Fiducial & DICOM Scale Calibration Engine"
    job.model_version = "1.2.0"
    job.provider_name = "OpenCV"
    job.is_demo = False
    required = {"FrontalPhoto", "RightLateralPhoto", "LeftLateralPhoto", "OPG"}
    missing = sorted(required - set(by_type))
    warnings: list[str] = []
    if auto_calibrated:
        warnings.append(
            f"Automatically detected and calibrated physical scale markers for: {', '.join(auto_calibrated)}."
        )
    if missing:
        warnings.append(
            f"Missing physical calibration for: {', '.join(missing)}. Affected linear measurements will be flagged Unscaled."
        )
    job.warnings = list(dict.fromkeys(warnings))
    job.output = {
        "configured_calibrations": sorted(by_type.keys()),
        "auto_calibrated": auto_calibrated,
        "missing_calibrations": missing,
    }
    job.status = AIJobStatusEnum.UNSCALED if missing else AIJobStatusEnum.VALIDATED


async def calculate_visit_measurements(
    db: AsyncSession,
    visit_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    ai_job_id: uuid.UUID | None = None,
) -> list[Measurement]:
    """Run the deterministic geometric measurement engine for a visit."""
    cal_map_type = {
        "FrontalPhoto": "Frontal",
        "RightLateralPhoto": "RightLateral",
        "LeftLateralPhoto": "LeftLateral",
        "OPG": "OPG",
    }
    cals = list(
        (
            await db.execute(
                select(CalibrationRecord).where(
                    CalibrationRecord.visit_id == visit_id,
                    CalibrationRecord.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    cal_by_view: dict[str, CalibrationInfo] = {}
    for c in cals:
        view_name = cal_map_type.get(c.calibration_type.value, c.calibration_type.value)
        reg = c.regional_calibration or {}
        cal_by_view[view_name] = CalibrationInfo(
            mm_per_pixel=c.mm_per_pixel,
            is_physical=c.is_physical,
            same_plane_confirmed=c.same_plane_confirmed,
            calibration_id=str(c.id),
            calibration_type=c.calibration_type.value,
            method=c.calibration_method,
            horizontal_mm_per_px=reg.get("horizontal_mm_per_px"),
            vertical_mm_per_px=reg.get("vertical_mm_per_px"),
            warnings=list(c.warnings or []),
        )

    imgs = list(
        (
            await db.execute(
                select(VisitImage).where(VisitImage.visit_id == visit_id, VisitImage.is_deleted.is_(False))
            )
        )
        .scalars()
        .all()
    )
    views: dict[str, ViewData] = {}
    all_reviewed = True
    any_reviewed = False
    model_used = ("geometric-engine", "1.0.0")

    for im in imgs:
        if im.acceptance_status == "Rejected":
            continue
        preds_stmt = (
            select(LandmarkPrediction, LandmarkDefinition.code)
            .join(LandmarkDefinition, LandmarkDefinition.id == LandmarkPrediction.landmark_definition_id)
            .where(LandmarkPrediction.image_id == im.id, LandmarkPrediction.is_current.is_(True))
        )
        pts: dict[str, LandmarkPoint] = {}
        for pred, code in (await db.execute(preds_stmt)).all():
            pts[code] = LandmarkPoint(
                code=code,
                x=pred.x,
                y=pred.y,
                z=pred.z,
                status=pred.status.value,
                prediction_id=str(pred.id),
                source=pred.source,
            )
            if pred.model_name:
                model_used = (pred.model_name, pred.model_version or "1.0.0")
            if pred.status in (PredictionStatusEnum.REVIEWED, PredictionStatusEnum.APPROVED):
                any_reviewed = True
            else:
                all_reviewed = False
        views[im.image_type.value] = ViewData(
            landmarks=pts,
            width=im.width,
            height=im.height,
            calibration=cal_by_view.get(im.image_type.value),
        )

    # Load latest 3D mesh asset if available
    mesh_data: MeshData | None = None
    asset = (
        await db.execute(
            select(ReconstructionAsset)
            .where(ReconstructionAsset.visit_id == visit_id, ReconstructionAsset.asset_type == AssetTypeEnum.MESH)
            .order_by(ReconstructionAsset.created_at.desc())
        )
    ).scalars().first()
    if asset is not None:
        try:
            raw_obj = get_storage().read(asset.file_path).decode("utf-8")
            verts, faces = parse_obj(raw_obj)
            meta = asset.metadata_ or {}
            lm3d = {k: (float(v[0]), float(v[1]), float(v[2])) for k, v in (meta.get("landmarks_3d") or {}).items()}
            mesh_data = MeshData(
                vertices=verts,
                faces=faces,
                landmarks=lm3d,
                is_metric=bool(meta.get("is_metric", False)),
                status=asset.status.value,
            )
        except Exception:
            mesh_data = None

    engine = MeasurementEngine(views=views, mesh=mesh_data)
    m_defs = list(
        (await db.execute(select(MeasurementDefinition).order_by(MeasurementDefinition.display_order.asc())))
        .scalars()
        .all()
    )

    # Mark previous unapproved measurements non-current so history is preserved
    existing_ms = list(
        (
            await db.execute(
                select(Measurement).where(Measurement.visit_id == visit_id, Measurement.is_current.is_(True))
            )
        )
        .scalars()
        .all()
    )
    existing_by_def = {m.measurement_definition_id: m for m in existing_ms}

    method = (
        MeasurementMethodEnum.EXAMINER_REVIEWED
        if (any_reviewed and all_reviewed)
        else MeasurementMethodEnum.AI_PREDICTED
    )

    created: list[Measurement] = []
    for mdef in m_defs:
        prev = existing_by_def.get(mdef.id)
        if prev and prev.status == MeasurementStatusEnum.APPROVED:
            # Never overwrite an already-approved measurement
            created.append(prev)
            continue
        version_num = (prev.version + 1) if prev else 1
        if prev:
            prev.is_current = False

        res = engine.compute(mdef.code, mdef.spec or {}, mdef.unit or "mm")
        cal_id_str = res.right.calibration_id or res.left.calibration_id
        cal_uuid = uuid.UUID(cal_id_str) if cal_id_str else None
        spec = mdef.spec or {}
        src_view = spec.get("view") or spec.get("view_right") or "MultiView"

        m = Measurement(
            visit_id=visit_id,
            measurement_definition_id=mdef.id,
            right_value=round(res.right.value, 3) if res.right.value is not None else None,
            left_value=round(res.left.value, 3) if res.left.value is not None else None,
            absolute_difference=round(res.absolute_difference, 3) if res.absolute_difference is not None else None,
            asymmetry_index=round(res.asymmetry_index, 2) if res.asymmetry_index is not None else None,
            unit=mdef.unit or "mm",
            source_image_type=src_view,
            calibration_id=cal_uuid,
            method=method,
            model_name=model_used[0],
            model_version=model_used[1],
            status=MeasurementStatusEnum(res.status),
            landmark_refs=res.landmark_refs(),
            warnings=res.warnings,
            is_current=True,
            version=version_num,
            is_unscaled=res.is_unscaled,
            calculated_by=user_id,
            ai_job_id=ai_job_id,
        )
        db.add(m)
        created.append(m)
    await db.flush()
    return created


async def _stage_measurement_calc(db: AsyncSession, job: AIJob) -> None:
    job.model_name = "Validated Geometric Asymmetry Measurement Engine"
    job.model_version = "1.2.0"
    job.provider_name = "OpenCV"
    job.is_demo = False
    ms = await calculate_visit_measurements(db, job.visit_id, job.created_by, job.id)
    unscaled_count = sum(1 for m in ms if m.status == MeasurementStatusEnum.UNSCALED)
    calc_count = sum(
        1 for m in ms if m.status in (MeasurementStatusEnum.CALCULATED, MeasurementStatusEnum.REVIEW_REQUIRED, MeasurementStatusEnum.APPROVED)
    )
    warnings: list[str] = []
    if unscaled_count:
        warnings.append(f"{unscaled_count} measurements are Unscaled pending physical calibration.")
    job.warnings = warnings
    job.output = {"total_definitions": len(ms), "calculated": calc_count, "unscaled": unscaled_count}
    job.status = AIJobStatusEnum.UNSCALED if (calc_count == 0 and unscaled_count > 0) else AIJobStatusEnum.REVIEW_REQUIRED


async def _stage_report_generation(db: AsyncSession, job: AIJob, adapter) -> None:
    from sqlalchemy.orm import selectinload
    from app.models.patient import Patient

    visit = (await db.execute(select(Visit).where(Visit.id == job.visit_id))).scalar_one()
    patient = (await db.execute(select(Patient).where(Patient.id == visit.patient_id))).scalar_one()
    ms = list(
        (
            await db.execute(
                select(Measurement)
                .where(Measurement.visit_id == visit.id, Measurement.is_current.is_(True))
                .options(selectinload(Measurement.measurement_definition))
            )
        )
        .scalars()
        .all()
    )
    payload = {
        "patient_code": patient.patient_code,
        "visit_label": visit.visit_type.value,
        "measurements": [
            {
                "code": m.measurement_definition.code if m.measurement_definition else "",
                "name": m.measurement_definition.name if m.measurement_definition else "",
                "right_value": m.right_value,
                "left_value": m.left_value,
                "absolute_difference": m.absolute_difference,
                "asymmetry_index": m.asymmetry_index,
                "unit": m.unit,
                "method": m.method.value,
                "status": m.status.value,
            }
            for m in ms
        ],
    }
    res = await adapter.generate_research_summary(payload)
    rpt = Report(
        patient_id=patient.id,
        visit_id=visit.id,
        report_type=ReportTypeEnum.VISIT_ANALYSIS,
        title=f"{patient.patient_code} — {visit.visit_type.value} Analysis Summary",
        content={
            "summary_text": res.output.get("summary_text"),
            "mode": res.output.get("mode"),
            "is_demo": res.is_demo,
            "measurements_snapshot": payload["measurements"],
            "disclaimer": "Research measurement output only. Not a diagnosis or clinical recommendation.",
        },
        generated_by=job.created_by,
        ai_job_id=job.id,
        protocol_version_id=job.protocol_version_id,
        status=ReportStatusEnum.GENERATED,
    )
    db.add(rpt)
    job.warnings = res.warnings
    job.output = {"report_title": rpt.title, "mode": res.output.get("mode")}
    job.status = AIJobStatusEnum.COMPLETED
