"""
Administration endpoints:
  * Page 14 — AI Model Configuration (/admin/ai-providers, /admin/ai-models)
  * Page 18 — User Management (/admin/users, /admin/roles)
  * Page 19 — Audit Logs (/admin/audit-logs)
  * Page 20 — Protocol Configuration (/admin/protocols)
  * Notifications (/notifications)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.base import ImageInput
from app.ai.providers.registry import build_adapter
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import ALL_PERMISSIONS, P
from app.core.responses import bad_request, conflict, not_found, ok
from app.core.security import (
    get_current_user,
    hash_password,
    require_permissions,
)
from app.models.ai import (
    AIJob,
    AIModelRegistry,
    AIProviderConfig,
    AITaskTypeEnum,
    EnvironmentEnum,
    ProviderTypeEnum,
)
from app.models.audit import AuditLog
from app.models.landmark import LandmarkDefinition
from app.models.measurement import MeasurementDefinition
from app.models.notification import Notification
from app.models.protocol import ProtocolVersion, StudyProtocol
from app.models.user import Role, RolePermission, User, UserRole
from app.services.audit import record_audit
from app.services.synthetic_images import frontal

router = APIRouter(tags=["Administration"])


# ---------------------------------------------------------------------------
# PAGE 14 — AI Model Configuration
# ---------------------------------------------------------------------------


class AIProviderCreateRequest(BaseModel):
    provider_type: ProviderTypeEnum
    task_type: AITaskTypeEnum
    model_name: str = Field(..., min_length=2)
    model_identifier: str | None = None
    model_version: str = "1.0.0"
    display_name: str | None = None
    endpoint_url: str | None = None
    credential_key_name: str | None = None  # Name of backend env var, NEVER raw key
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    is_enabled: bool = True
    is_default: bool = False
    environment: EnvironmentEnum = EnvironmentEnum.DEVELOPMENT


class AIProviderUpdateRequest(BaseModel):
    model_name: str | None = None
    model_identifier: str | None = None
    model_version: str | None = None
    endpoint_url: str | None = None
    credential_key_name: str | None = None
    timeout_seconds: int | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None
    environment: EnvironmentEnum | None = None


class AITestRequest(BaseModel):
    mode: str = "connection"  # connection | inference


def _serialize_provider(c: AIProviderConfig) -> dict[str, Any]:
    adapter = build_adapter(
        c.provider_type.value,
        c.model_name,
        model_identifier=c.model_identifier,
        model_version=c.model_version,
        endpoint_url=c.endpoint_url,
        credential_key_name=c.credential_key_name,
        timeout_seconds=c.timeout_seconds,
    )
    return {
        "id": str(c.id),
        "provider_type": c.provider_type.value,
        "task_type": c.task_type.value,
        "model_name": c.model_name,
        "model_identifier": c.model_identifier,
        "model_version": c.model_version,
        "display_name": c.display_name or f"{c.provider_type.value} — {c.model_name}",
        "endpoint_url": c.endpoint_url,
        "credential_key_name": c.credential_key_name,  # Only the env var reference name is returned
        "timeout_seconds": c.timeout_seconds,
        "is_enabled": c.is_enabled,
        "is_default": c.is_default,
        "is_demo": adapter.is_demo,
        "task_compatible": adapter.supports(c.task_type.value),
        "supported_tasks": sorted(adapter.supported_tasks),
        "environment": c.environment.value,
        "last_health_check": c.last_health_check.isoformat() if c.last_health_check else None,
        "last_health_status": c.last_health_status,
        "last_health_message": c.last_health_message,
        "updated_at": (c.updated_at or c.created_at).isoformat(),
    }


@router.get("/admin/ai-providers")
async def list_ai_providers(
    task_type: str | None = Query(default=None),
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(AIProviderConfig).order_by(
        AIProviderConfig.task_type.asc(),
        AIProviderConfig.is_default.desc(),
        AIProviderConfig.created_at.asc(),
    )
    if task_type:
        stmt = stmt.where(AIProviderConfig.task_type == task_type)
    configs = list((await db.execute(stmt)).scalars().all())

    reg = list((await db.execute(select(AIModelRegistry).order_by(AIModelRegistry.name.asc()))).scalars().all())
    recent_jobs = list(
        (await db.execute(select(AIJob).order_by(AIJob.created_at.desc()).limit(30))).scalars().all()
    )
    return ok(
        {
            "providers": [_serialize_provider(c) for c in configs],
            "registry": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "provider_type": r.provider_type.value,
                    "supported_tasks": r.supported_tasks or [],
                    "version": r.version,
                    "description": r.description,
                    "is_active": r.is_active,
                }
                for r in reg
            ],
            "execution_history": [
                {
                    "id": str(j.id),
                    "task_type": j.task_type.value,
                    "provider": j.provider_name,
                    "model_name": j.model_name,
                    "model_version": j.model_version,
                    "status": j.status.value,
                    "duration_seconds": j.duration_seconds,
                    "created_at": j.created_at.isoformat(),
                }
                for j in recent_jobs
            ],
        }
    )


@router.post("/admin/ai-providers")
async def create_ai_provider(
    payload: AIProviderCreateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    adapter = build_adapter(
        payload.provider_type.value,
        payload.model_name,
        model_identifier=payload.model_identifier,
        model_version=payload.model_version,
        endpoint_url=payload.endpoint_url,
        credential_key_name=payload.credential_key_name,
        timeout_seconds=payload.timeout_seconds,
    )
    if not adapter.supports(payload.task_type.value):
        raise bad_request(
            f"Provider '{payload.provider_type.value}' does not support task '{payload.task_type.value}'. "
            f"Supported tasks: {', '.join(sorted(adapter.supported_tasks))}"
        )

    if payload.is_default:
        for prev in (
            await db.execute(
                select(AIProviderConfig).where(AIProviderConfig.task_type == payload.task_type)
            )
        ).scalars().all():
            prev.is_default = False

    cfg = AIProviderConfig(
        provider_type=payload.provider_type,
        task_type=payload.task_type,
        model_name=payload.model_name,
        model_identifier=payload.model_identifier,
        model_version=payload.model_version,
        display_name=payload.display_name,
        endpoint_url=payload.endpoint_url,
        credential_key_name=payload.credential_key_name,
        timeout_seconds=payload.timeout_seconds,
        is_enabled=payload.is_enabled,
        is_default=payload.is_default,
        environment=payload.environment,
    )
    db.add(cfg)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="ai_config.create",
        resource_type="ai_provider_config",
        resource_id=cfg.id,
        after=_serialize_provider(cfg),
        request=request,
    )
    return ok(_serialize_provider(cfg), message="AI model configuration created")


@router.put("/admin/ai-providers/{provider_id}")
async def update_ai_provider(
    provider_id: uuid.UUID,
    payload: AIProviderUpdateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cfg = (
        await db.execute(select(AIProviderConfig).where(AIProviderConfig.id == provider_id))
    ).scalar_one_or_none()
    if cfg is None:
        raise not_found("AIProviderConfig")

    before = _serialize_provider(cfg)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)

    adapter = build_adapter(
        cfg.provider_type.value,
        cfg.model_name,
        model_identifier=cfg.model_identifier,
        model_version=cfg.model_version,
        endpoint_url=cfg.endpoint_url,
        credential_key_name=cfg.credential_key_name,
        timeout_seconds=cfg.timeout_seconds,
    )
    if cfg.is_enabled and not adapter.supports(cfg.task_type.value):
        raise bad_request(
            f"Cannot enable incompatible task '{cfg.task_type.value}' on provider '{cfg.provider_type.value}'."
        )

    if payload.is_default:
        for other in (
            await db.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.task_type == cfg.task_type,
                    AIProviderConfig.id != cfg.id,
                )
            )
        ).scalars().all():
            other.is_default = False
        cfg.is_enabled = True

    await record_audit(
        db,
        user=current_user,
        action="ai_config.update",
        resource_type="ai_provider_config",
        resource_id=cfg.id,
        before=before,
        after=_serialize_provider(cfg),
        request=request,
    )
    return ok(_serialize_provider(cfg), message="AI model configuration updated")


@router.post("/admin/ai-providers/{provider_id}/test")
async def test_ai_provider(
    provider_id: uuid.UUID,
    payload: AITestRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cfg = (
        await db.execute(select(AIProviderConfig).where(AIProviderConfig.id == provider_id))
    ).scalar_one_or_none()
    if cfg is None:
        raise not_found("AIProviderConfig")

    adapter = build_adapter(
        cfg.provider_type.value,
        cfg.model_name,
        model_identifier=cfg.model_identifier,
        model_version=cfg.model_version,
        endpoint_url=cfg.endpoint_url,
        credential_key_name=cfg.credential_key_name,
        timeout_seconds=cfg.timeout_seconds,
    )
    health = await adapter.health_check()
    inference_res = None

    if payload.mode == "inference":
        try:
            png_bytes, meta = frontal(seed=999)
            sample = ImageInput(
                image_id="synthetic-test",
                image_type="Frontal",
                data=png_bytes,
                width=900,
                height=1150,
                synthetic_meta=meta,
            )
            if cfg.task_type == AITaskTypeEnum.IMAGE_QUALITY:
                r = await adapter.assess_image_quality(sample)
                inference_res = {"status": r.status, "processing_time_ms": r.processing_time_ms, "warnings": r.warnings}
            elif cfg.task_type == AITaskTypeEnum.FACIAL_LANDMARK:
                r = await adapter.detect_landmarks(sample, ["N", "PRN", "SN", "PG", "GO_R", "GO_L"])
                inference_res = {
                    "status": r.status,
                    "landmarks_detected": len(r.output.get("landmarks", [])),
                    "processing_time_ms": r.processing_time_ms,
                    "warnings": r.warnings,
                }
            elif cfg.task_type == AITaskTypeEnum.REPORT_GENERATION:
                r = await adapter.generate_research_summary({"patient_code": "SYNTH-TEST", "measurements": []})
                inference_res = {"status": r.status, "processing_time_ms": r.processing_time_ms, "warnings": r.warnings}
            else:
                inference_res = {
                    "status": "Checked",
                    "message": f"Task compatibility verified ({cfg.task_type.value})",
                }
        except Exception as exc:
            inference_res = {"status": "Failed", "error": str(exc)}

    cfg.last_health_check = datetime.now(timezone.utc)
    cfg.last_health_status = "Healthy" if health.get("ok") else "Unreachable"
    cfg.last_health_message = str(health.get("message", ""))

    await record_audit(
        db,
        user=current_user,
        action=f"ai_config.test_{payload.mode}",
        resource_type="ai_provider_config",
        resource_id=cfg.id,
        after={"health": health, "inference": inference_res},
        request=request,
    )
    return ok(
        {
            "provider": _serialize_provider(cfg),
            "health": health,
            "inference": inference_res,
        },
        message=health.get("message", "Health check completed"),
    )


# ---------------------------------------------------------------------------
# PAGE 18 — User Management
# ---------------------------------------------------------------------------


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(default="Research@2026", min_length=8)
    first_name: str = Field(default="Researcher")
    last_name: str = Field(default="User")
    role_names: list[str] | None = None
    roles: list[str] | None = None
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None
    role_names: list[str] | None = None


class ResetAccessRequest(BaseModel):
    new_password: str = Field(default="Research@2026", min_length=8)


def _serialize_admin_user(u: User) -> dict[str, Any]:
    rnames = [ur.role.name for ur in u.user_roles if ur.role]
    perms = sorted(
        {
            rp.permission.name
            for ur in u.user_roles
            if ur.role
            for rp in ur.role.role_permissions
            if rp.permission
        }
    )
    return {
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "full_name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
        "is_active": u.is_active,
        "is_superuser": u.is_superuser,
        "roles": rnames,
        "primary_role": rnames[0] if rnames else "Researcher",
        "permissions": perms,
        "last_login_at": (u.updated_at or u.created_at).isoformat(),
        "created_at": u.created_at.isoformat(),
    }


@router.get("/admin/users")
async def list_users(
    current_user: Any = Depends(require_permissions(P.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(User)
        .options(
            selectinload(User.user_roles)
            .selectinload(UserRole.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )
        .order_by(User.created_at.asc())
    )
    users = list((await db.execute(stmt)).scalars().all())
    roles = list(
        (
            await db.execute(
                select(Role)
                .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
                .order_by(Role.name.asc())
            )
        )
        .scalars()
        .all()
    )
    roles_serialized = [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "permissions": sorted([rp.permission.name for rp in r.role_permissions if rp.permission]),
        }
        for r in roles
    ]
    return ok(
        {
            "users": [_serialize_admin_user(u) for u in users],
            "roles": roles_serialized,
            "available_roles": roles_serialized,
            "all_permissions": [{"name": k, "description": v} for k, v in ALL_PERMISSIONS.items()],
        }
    )


@router.post("/admin/users")
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    email = payload.email.lower().strip()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise conflict(f"User with email '{email}' already exists")

    req_roles = payload.role_names or payload.roles or ["Clinician / Examiner"]
    roles = list(
        (await db.execute(select(Role).where(Role.name.in_(req_roles)))).scalars().all()
    )
    if not roles:
        raise bad_request("Specify at least one valid role")

    u = User(
        email=email,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_active=True,
        is_superuser=False,
    )
    db.add(u)
    await db.flush()
    for r in roles:
        db.add(UserRole(user_id=u.id, role_id=r.id))
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="user.create",
        resource_type="user",
        resource_id=u.id,
        after={"email": u.email, "roles": req_roles},
        request=request,
    )
    return ok(_serialize_admin_user(u), message="User created")


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(User).where(User.id == user_id).options(selectinload(User.user_roles).selectinload(UserRole.role))
    u = (await db.execute(stmt)).scalar_one_or_none()
    if u is None:
        raise not_found("User")

    if u.id == current_user.id and payload.is_active is False:
        raise bad_request("You cannot deactivate your own active administrator account.")

    before = {"first_name": u.first_name, "last_name": u.last_name, "is_active": u.is_active}
    if payload.first_name is not None:
        u.first_name = payload.first_name
    if payload.last_name is not None:
        u.last_name = payload.last_name
    if payload.is_active is not None:
        u.is_active = payload.is_active

    if payload.role_names is not None:
        roles = list((await db.execute(select(Role).where(Role.name.in_(payload.role_names)))).scalars().all())
        if not roles:
            raise bad_request("At least one valid role is required")
        for ur in list(u.user_roles):
            await db.delete(ur)
        await db.flush()
        for r in roles:
            db.add(UserRole(user_id=u.id, role_id=r.id))

    await record_audit(
        db,
        user=current_user,
        action="user.update",
        resource_type="user",
        resource_id=u.id,
        before=before,
        after=payload.model_dump(exclude_unset=True),
        request=request,
    )
    return await list_users(current_user, db)


@router.post("/admin/users/{user_id}/reset-access")
async def reset_user_access(
    user_id: uuid.UUID,
    payload: ResetAccessRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if u is None:
        raise not_found("User")
    u.hashed_password = hash_password(payload.new_password)
    u.is_active = True
    await record_audit(
        db,
        user=current_user,
        action="user.reset_access",
        resource_type="user",
        resource_id=u.id,
        after={"email": u.email, "is_active": True},
        request=request,
    )
    return ok(
        {
            "id": str(u.id),
            "email": u.email,
            "temporary_password": payload.new_password,
        },
        message="User access and password reset",
    )


# ---------------------------------------------------------------------------
# PAGE 19 — Audit Logs
# ---------------------------------------------------------------------------


@router.get("/admin/audit-logs")
async def list_audit_logs(
    action: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=150, ge=1, le=500),
    current_user: Any = Depends(require_permissions(P.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.created_at.desc()).limit(limit)
    act = action or action_type
    rtype = resource_type or entity_type
    if act:
        stmt = stmt.where(AuditLog.action.ilike(f"%{act}%"))
    if rtype:
        stmt = stmt.where(AuditLog.resource_type.ilike(f"%{rtype}%"))
    logs = list((await db.execute(stmt)).scalars().all())
    items = [
        {
            "id": str(a.id),
            "user_id": str(a.user_id) if a.user_id else None,
            "user_email": a.user.email if a.user else "system",
            "action": a.action,
            "action_type": a.action,
            "resource_type": a.resource_type,
            "entity_type": a.resource_type,
            "resource_id": str(a.resource_id) if a.resource_id else None,
            "entity_id": str(a.resource_id) if a.resource_id else None,
            "description": a.reason or f"{a.action} on {a.resource_type}",
            "before_value": a.before_value,
            "before_json": a.before_value,
            "after_value": a.after_value,
            "after_json": a.after_value,
            "reason": a.reason,
            "ip_address": a.ip_address,
            "created_at": a.created_at.isoformat(),
        }
        for a in logs
    ]
    return ok({"total": len(items), "items": items})


# ---------------------------------------------------------------------------
# PAGE 20 — Protocol Configuration
# ---------------------------------------------------------------------------


class ProtocolVersionCreateRequest(BaseModel):
    version_number: str = Field(..., min_length=1)
    title: str | None = None
    description: str | None = None
    visit_schedule: dict | None = None
    required_image_types: list[str] | None = None
    calibration_rules: dict | None = None
    review_requirements: dict | None = None
    reason: str = Field(default="Published new protocol version (historical approved results preserved)", min_length=3)


@router.get("/admin/protocols")
async def get_protocols(
    current_user: Any = Depends(require_permissions(P.PROTOCOL_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(StudyProtocol)
        .options(selectinload(StudyProtocol.versions))
        .order_by(StudyProtocol.created_at.asc())
    )
    protocols = list((await db.execute(stmt)).scalars().all())
    lms = list(
        (await db.execute(select(LandmarkDefinition).order_by(LandmarkDefinition.display_order.asc())))
        .scalars()
        .all()
    )
    ms = list(
        (await db.execute(select(MeasurementDefinition).order_by(MeasurementDefinition.display_order.asc())))
        .scalars()
        .all()
    )
    proto_list = []
    for p in protocols:
        sorted_vs = sorted(p.versions, key=lambda x: x.created_at, reverse=True)
        cur_v = next((v for v in sorted_vs if v.is_current), sorted_vs[0] if sorted_vs else None)
        raw_sched = cur_v.visit_schedule if cur_v else []
        if isinstance(raw_sched, dict) and isinstance(raw_sched.get("visits"), list):
            sched_list = [
                {
                    **item,
                    "day_offset": item.get("day_offset", item.get("offset_days", 0)),
                    "offset_days": item.get("offset_days", item.get("day_offset", 0)),
                    "window_days": item.get("window_days", 7),
                }
                for item in raw_sched["visits"]
                if isinstance(item, dict)
            ]
        elif isinstance(raw_sched, dict):
            sched_list = [
                {
                    "visit_type": k,
                    "label": (v.get("label", k) if isinstance(v, dict) else k),
                    "day_offset": (v.get("day_offset", v.get("offset_days", 0)) if isinstance(v, dict) else 0),
                    "offset_days": (v.get("offset_days", v.get("day_offset", 0)) if isinstance(v, dict) else 0),
                    "window_days": (v.get("window_days", 7) if isinstance(v, dict) else 7),
                }
                for k, v in raw_sched.items()
            ]
        elif isinstance(raw_sched, list):
            sched_list = [
                {
                    **item,
                    "day_offset": item.get("day_offset", item.get("offset_days", 0)),
                    "offset_days": item.get("offset_days", item.get("day_offset", 0)),
                    "window_days": item.get("window_days", 7),
                }
                for item in raw_sched
                if isinstance(item, dict)
            ]
        else:
            sched_list = []

        proto_list.append(
            {
                "id": str(p.id),
                "title": p.title,
                "identifier": p.identifier,
                "protocol_code": p.identifier,
                "version": cur_v.version_number if cur_v else "1.0",
                "description": p.description,
                "is_active": p.is_active,
                "visit_schedule": sched_list,
                "required_image_views": (cur_v.required_image_types if cur_v else []) or ["Frontal", "RightLateral", "LeftLateral", "OPG"],
                "calibration_rules": cur_v.calibration_rules if cur_v else {},
                "review_rules": cur_v.review_requirements if cur_v else {},
                "versions": [
                    {
                        "id": str(v.id),
                        "version_number": v.version_number,
                        "visit_schedule": v.visit_schedule,
                        "required_image_types": v.required_image_types,
                        "landmark_set": v.landmark_set,
                        "measurement_set": v.measurement_set,
                        "calibration_rules": v.calibration_rules,
                        "review_requirements": v.review_requirements,
                        "is_current": v.is_current,
                        "effective_date": v.effective_date.isoformat() if v.effective_date else None,
                        "created_at": v.created_at.isoformat(),
                    }
                    for v in sorted_vs
                ],
            }
        )

    return ok(
        {
            "protocols": proto_list,
            "landmark_definitions": [
                {
                    "id": str(d.id),
                    "code": d.code,
                    "name": d.name,
                    "side": d.side,
                    "landmark_type": d.landmark_type.value,
                    "anatomical_region": d.anatomical_region,
                    "description": d.description or d.name,
                    "applicable_views": d.applicable_views or [],
                }
                for d in lms
            ],
            "measurement_definitions": [
                {
                    "id": str(m.id),
                    "code": m.code,
                    "name": m.name,
                    "measurement_type": m.measurement_type.value,
                    "unit": m.unit,
                    "source_view": "Frontal / Lateral / OPG",
                    "formula": m.formula,
                    "description": m.description,
                }
                for m in ms
            ],
        }
    )


@router.post("/admin/protocols")
async def compat_create_protocol(
    payload: dict[str, Any],
    request: Request,
    current_user: Any = Depends(require_permissions(P.PROTOCOL_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    proto = (await db.execute(select(StudyProtocol).order_by(StudyProtocol.created_at.asc()))).scalars().first()
    if proto is None:
        raise not_found("StudyProtocol")
    ver = payload.get("version") or payload.get("version_number") or "1.1"
    await create_protocol_version(
        proto.id,
        ProtocolVersionCreateRequest(
            version_number=ver,
            title=payload.get("title"),
            description=payload.get("description"),
        ),
        request,
        current_user,
        db,
    )
    return ok({"protocol_code": proto.identifier, "version": ver})


@router.post("/admin/protocols/{protocol_id}/versions")
async def create_protocol_version(
    protocol_id: uuid.UUID,
    payload: ProtocolVersionCreateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.PROTOCOL_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new immutable protocol version without altering historical analyses."""
    stmt = (
        select(StudyProtocol)
        .where(StudyProtocol.id == protocol_id)
        .options(selectinload(StudyProtocol.versions))
    )
    proto = (await db.execute(stmt)).scalar_one_or_none()
    if proto is None:
        raise not_found("StudyProtocol")

    if any(v.version_number == payload.version_number for v in proto.versions):
        raise conflict(f"Protocol version '{payload.version_number}' already exists")

    if payload.title:
        proto.title = payload.title
    if payload.description:
        proto.description = payload.description

    current = next((v for v in proto.versions if v.is_current), proto.versions[0] if proto.versions else None)
    for v in proto.versions:
        v.is_current = False

    new_v = ProtocolVersion(
        protocol_id=proto.id,
        version_number=payload.version_number,
        visit_schedule=payload.visit_schedule or (current.visit_schedule if current else {}),
        required_image_types=payload.required_image_types or (current.required_image_types if current else []),
        landmark_set=current.landmark_set if current else [],
        measurement_set=current.measurement_set if current else [],
        calibration_rules=payload.calibration_rules or (current.calibration_rules if current else {}),
        review_requirements=payload.review_requirements or (current.review_requirements if current else {}),
        is_current=True,
        effective_date=date.today(),
    )
    db.add(new_v)
    await db.flush()

    await record_audit(
        db,
        user=current_user,
        action="protocol.create_version",
        resource_type="protocol_version",
        resource_id=new_v.id,
        after={"protocol": proto.identifier, "version_number": new_v.version_number},
        reason=payload.reason,
        request=request,
    )
    return await get_protocols(current_user, db)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@router.get("/notifications")
async def list_notifications(
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(25)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return ok(
        [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "notification_type": n.notification_type.value,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in items
        ]
    )


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    n = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    return ok({"id": str(n.id), "is_read": True})


# ---------------------------------------------------------------------------
# Dynamic System Settings & Database-Backed Credentials
# ---------------------------------------------------------------------------


class SettingUpdateRequest(BaseModel):
    value: str | None = None
    category: str | None = None
    description: str | None = None
    is_secret: bool | None = None


@router.get("/admin/settings")
async def get_system_settings(
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.core.database import ACTIVE_DATABASE_LABEL, Base
    from app.services.storage import get_database_storage_stats
    from app.services.system_settings import list_all_settings

    db_settings = await list_all_settings(db, reveal_secrets=False)
    blob_stats = await get_database_storage_stats(db)

    return ok(
        {
            "settings": db_settings,
            "governance": {
                "app_name": settings.APP_NAME,
                "environment": settings.ENVIRONMENT,
                "database_engine": ACTIVE_DATABASE_LABEL,
                "total_database_tables": len(Base.metadata.tables),
                "storage_backend": settings.STORAGE_BACKEND,
                "database_blob_storage": blob_stats,
                "task_backend": settings.TASK_BACKEND,
                "allow_external_ai_uploads": settings.ALLOW_EXTERNAL_AI_UPLOADS,
                "display_px_per_mm_assumption_rejected_for_physical_scale": True,
                "mandatory_examiner_sign_off_for_visit_completion": True,
                "immutable_audit_log_listeners_enabled": True,
            },
        }
    )


@router.put("/admin/settings/{key}")
async def update_system_setting(
    key: str,
    payload: SettingUpdateRequest,
    request: Request,
    current_user: Any = Depends(require_permissions(P.CONFIG_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.system_settings import set_setting_value

    setting = await set_setting_value(
        db,
        key=key,
        value=payload.value,
        current_user=current_user,
        category=payload.category or "General",
        description=payload.description,
        is_secret=bool(payload.is_secret if payload.is_secret is not None else ("KEY" in key or "SECRET" in key)),
        request=request,
    )
    return ok({"key": setting.key, "updated": True, "category": setting.category})

