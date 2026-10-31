"""
3D Reconstruction Workspace endpoints (Page 10):
  * GET  /visits/{visit_id}/reconstruction         — 3D mesh, landmarks, geodesic paths, coverage & warnings
  * POST /visits/{visit_id}/reconstruction/generate — generate / refresh 3D reconstruction for a visit
  * GET  /reconstruction/{asset_id}/export         — export 3D mesh as OBJ or PLY
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import _load_visit_landmarks_by_view
from app.ai.providers.demo_adapter import DemoProviderAdapter
from app.ai.reconstruction.mesh import parse_obj, to_ply
from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import not_found, ok
from app.core.security import require_permissions
from app.measurements.engine import MeshData, mesh_geodesic
from app.models.ai import AIJob, AIJobStatusEnum, AITaskTypeEnum
from app.models.image import VisitImage
from app.models.reconstruction import (
    AssetTypeEnum,
    ReconstructionAsset,
    ReconstructionStatusEnum,
)
from app.models.visit import Visit
from app.services.audit import record_audit
from app.services.storage import get_storage

router = APIRouter(tags=["3D Reconstruction"])


def _compute_geodesic_paths(
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    landmarks_3d: dict[str, list[float]],
    is_metric: bool,
    status: str,
) -> list[dict[str, Any]]:
    pairs = [
        ("T_PG_R", "Right Tragion – Pogonion Geodesic", "T_R", "PG", "Right"),
        ("T_PG_L", "Left Tragion – Pogonion Geodesic", "T_L", "PG", "Left"),
        ("T_GO_R", "Right Tragion – Gonion Geodesic", "T_R", "GO_R", "Right"),
        ("T_GO_L", "Left Tragion – Gonion Geodesic", "T_L", "GO_L", "Left"),
        ("GO_PG_R", "Right Gonion – Pogonion Geodesic", "GO_R", "PG", "Right"),
        ("GO_PG_L", "Left Gonion – Pogonion Geodesic", "GO_L", "PG", "Left"),
    ]
    lm_tuples = {k: (float(v[0]), float(v[1]), float(v[2])) for k, v in landmarks_3d.items()}
    mesh = MeshData(vertices=verts, faces=faces, landmarks=lm_tuples, is_metric=is_metric, status=status)
    out = []
    for code, label, a, b, side in pairs:
        if a in lm_tuples and b in lm_tuples:
            try:
                dist = mesh_geodesic(mesh, lm_tuples[a], lm_tuples[b])
                out.append(
                    {
                        "code": code,
                        "label": label,
                        "side": side,
                        "start_landmark": a,
                        "end_landmark": b,
                        "start_xyz": list(lm_tuples[a]),
                        "end_xyz": list(lm_tuples[b]),
                        "distance_value": round(dist, 2),
                        "unit": "mm (approx)" if is_metric else "mesh units (unscaled)",
                        "is_metric": is_metric,
                        "validation_note": "Surface geodesic approximates a flexible tape measurement; requires paired physical validation before claiming equivalence.",
                    }
                )
            except Exception:
                pass
    return out


@router.get("/visits/{visit_id}/reconstruction")
async def get_visit_reconstruction(
    visit_id: uuid.UUID,
    current_user: Any = Depends(require_permissions(P.VISIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = (
        await db.execute(
            select(ReconstructionAsset)
            .where(ReconstructionAsset.visit_id == visit_id, ReconstructionAsset.asset_type == AssetTypeEnum.MESH)
            .order_by(ReconstructionAsset.created_at.desc())
        )
    ).scalars().first()
    if asset is None:
        return ok(
            {
                "available": False,
                "visit_id": str(visit_id),
                "status": "NotGenerated",
                "warnings": [
                    "No 3D reconstruction has been generated for this visit yet. Run AI Analysis or click Generate 3D Mesh."
                ],
            }
        )

    raw_obj = get_storage().read(asset.file_path).decode("utf-8")
    verts, faces = parse_obj(raw_obj)
    meta = asset.metadata_ or {}
    lm3d = meta.get("landmarks_3d") or {}
    is_metric = bool(meta.get("is_metric", False))
    paths = _compute_geodesic_paths(verts, faces, lm3d, is_metric, asset.status.value)

    return ok(
        {
            "available": True,
            "asset_id": str(asset.id),
            "visit_id": str(visit_id),
            "status": asset.status.value,
            "file_format": asset.file_format,
            "vertex_count": len(verts),
            "face_count": len(faces),
            "is_metric": is_metric,
            "is_demo": bool(meta.get("is_demo", False)),
            "model_name": meta.get("model_name", "DECA + MediaPipe 478-3D Surface Reconstructor"),
            "model_version": meta.get("model_version", "1.2.0"),
            "coverage": meta.get("coverage"),
            "warnings": asset.warnings or [],
            "vertices": verts,
            "faces": faces,
            "landmarks_3d": lm3d,
            "geodesic_paths": paths,
            "created_at": asset.created_at.isoformat(),
        }
    )


@router.post("/visits/{visit_id}/reconstruction/generate")
async def generate_visit_reconstruction(
    visit_id: uuid.UUID,
    request: Request,
    current_user: Any = Depends(require_permissions(P.AI_RUN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    visit = (await db.execute(select(Visit).where(Visit.id == visit_id))).scalar_one_or_none()
    if visit is None:
        raise not_found("Visit")

    imgs = list(
        (
            await db.execute(
                select(VisitImage).where(VisitImage.visit_id == visit_id, VisitImage.is_deleted.is_(False))
            )
        )
        .scalars()
        .all()
    )
    from app.ai.base import ImageInput
    from app.ai.orchestrator import _select_adapter

    storage = get_storage()
    inps = [
        ImageInput(
            image_id=str(im.id),
            image_type=im.image_type.value,
            data=storage.read(im.stored_path),
            width=im.width or 900,
            height=im.height or 1100,
        )
        for im in imgs
        if im.image_type.value in ("Frontal", "RightLateral", "LeftLateral")
    ]
    by_view = await _load_visit_landmarks_by_view(db, visit_id)
    adapter, _cfg = await _select_adapter(db, AITaskTypeEnum.RECONSTRUCTION_3D)
    res = await adapter.reconstruct_face(inps, by_view)
    out = res.output

    job = AIJob(
        visit_id=visit.id,
        patient_id=visit.patient_id,
        task_type=AITaskTypeEnum.RECONSTRUCTION_3D,
        status=AIJobStatusEnum.REVIEW_REQUIRED,
        model_name=res.model,
        model_version=res.model_version,
        provider_name=res.provider,
        is_demo=False,
        stage_order=6,
        warnings=res.warnings,
        created_by=current_user.id,
    )
    db.add(job)
    await db.flush()

    mesh_key = storage.save("meshes", out["obj_text"].encode("utf-8"), "obj", subdir=str(visit_id))
    asset = ReconstructionAsset(
        visit_id=visit_id,
        job_id=job.id,
        asset_type=AssetTypeEnum.MESH,
        file_path=mesh_key,
        file_format="OBJ",
        status=ReconstructionStatusEnum(out.get("mesh_status", "RequiresReview")),
        warnings=res.warnings,
        metadata_={
            "coverage": out.get("coverage"),
            "vertex_count": out.get("vertex_count"),
            "face_count": out.get("face_count"),
            "landmarks_3d": out.get("landmarks_3d"),
            "is_metric": True,
            "is_demo": False,
            "model_name": res.model,
            "model_version": res.model_version,
        },
    )
    db.add(asset)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="reconstruction.generate",
        resource_type="reconstruction_asset",
        resource_id=asset.id,
        after={"visit_id": str(visit_id), "status": asset.status.value},
        request=request,
    )
    return await get_visit_reconstruction(visit_id, current_user, db)


@router.get("/reconstruction/{asset_id}/export")
async def export_reconstruction_mesh(
    asset_id: uuid.UUID,
    format: str = Query(default="obj", pattern="^(obj|ply)$"),
    request: Request = None,  # type: ignore[assignment]
    current_user: Any = Depends(require_permissions(P.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    asset = (await db.execute(select(ReconstructionAsset).where(ReconstructionAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise not_found("ReconstructionAsset")
    raw_obj = get_storage().read(asset.file_path).decode("utf-8")
    await record_audit(
        db,
        user=current_user,
        action="reconstruction.export_mesh",
        resource_type="reconstruction_asset",
        resource_id=asset.id,
        after={"format": format.upper()},
        request=request,
    )
    if format.lower() == "ply":
        verts, faces = parse_obj(raw_obj)
        ply_text = to_ply(verts, faces, comment="SYNTHETIC DEMO 3D MESH - RESEARCH USE ONLY")
        return Response(
            content=ply_text.encode("utf-8"),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="mesh_{asset.id}.ply"'},
        )
    return Response(
        content=raw_obj.encode("utf-8"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="mesh_{asset.id}.obj"'},
    )
