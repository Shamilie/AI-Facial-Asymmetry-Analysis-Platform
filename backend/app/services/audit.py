"""
Audit logging service. Audit records are append-only (see models/audit.py).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import to_jsonable
from app.models.audit import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    user: Any | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str | None = None,
    before: Any = None,
    after: Any = None,
    reason: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    rid: uuid.UUID | None
    if isinstance(resource_id, str):
        try:
            rid = uuid.UUID(resource_id)
        except ValueError:
            rid = None
    else:
        rid = resource_id
    entry = AuditLog(
        user_id=getattr(user, "id", None),
        action=action,
        resource_type=resource_type,
        resource_id=rid,
        before_value=to_jsonable(before) if before is not None else None,
        after_value=to_jsonable(after) if after is not None else None,
        reason=reason,
        ip_address=(request.client.host if request and request.client else None),
        user_agent=(request.headers.get("user-agent", "")[:500] if request else None),
    )
    db.add(entry)
    await db.flush()
    return entry
