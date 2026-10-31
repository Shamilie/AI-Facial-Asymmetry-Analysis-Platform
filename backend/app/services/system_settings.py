"""
System Settings Service.
Provides database-backed configuration storage for API keys (e.g. GEMINI_API_KEY),
cloud storage credentials, and platform parameters with environment fallback and audit logging.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.system_setting import SystemSetting
from app.services.audit import record_audit

# Runtime in-memory cache for dynamic settings
_SETTINGS_CACHE: dict[str, str | None] = {}


def mask_secret_value(val: str | None) -> str:
    """Mask a secret key to prevent exposure in logs or UI (e.g. AIzaSy...****)."""
    if not val:
        return ""
    if len(val) <= 8:
        return "********"
    return f"{val[:6]}...{val[-4:]}"


async def get_setting_value(db: AsyncSession | None, key: str, default: str | None = None) -> str | None:
    """
    Resolve setting value in order of priority:
      1. In-memory cache
      2. Database table `system_settings`
      3. Environment variable (os.getenv)
      4. Default fallback from `app.core.config.settings`
    """
    if key in _SETTINGS_CACHE and _SETTINGS_CACHE[key] is not None:
        return _SETTINGS_CACHE[key]

    if db is not None:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        setting_row = (await db.execute(stmt)).scalar_one_or_none()
        if setting_row and setting_row.value:
            _SETTINGS_CACHE[key] = setting_row.value
            return setting_row.value

    # Fallback to os.getenv or settings
    env_val = os.getenv(key) or getattr(settings, key, None)
    if env_val is not None:
        return str(env_val)

    return default


def get_cached_setting_value(key: str, default: str | None = None) -> str | None:
    """Synchronous read from memory cache with fallback to os.getenv."""
    if key in _SETTINGS_CACHE and _SETTINGS_CACHE[key] is not None:
        return _SETTINGS_CACHE[key]
    return os.getenv(key) or getattr(settings, key, default)


async def set_setting_value(
    db: AsyncSession,
    key: str,
    value: str | None,
    current_user: Any,
    category: str = "General",
    description: str | None = None,
    is_secret: bool = False,
    request: Any = None,
) -> SystemSetting:
    """Create or update a system setting in the database and audit the change."""
    stmt = select(SystemSetting).where(SystemSetting.key == key)
    setting_row = (await db.execute(stmt)).scalar_one_or_none()

    before_val = mask_secret_value(setting_row.value) if (setting_row and setting_row.is_secret) else (setting_row.value if setting_row else None)

    if setting_row is None:
        setting_row = SystemSetting(
            key=key,
            value=value,
            category=category,
            description=description,
            is_secret=is_secret,
            is_editable=True,
        )
        db.add(setting_row)
    else:
        setting_row.value = value
        if category:
            setting_row.category = category
        if description:
            setting_row.description = description
        if is_secret is not None:
            setting_row.is_secret = is_secret

    await db.flush()

    # Update in-memory cache and os.environ
    _SETTINGS_CACHE[key] = value
    if value:
        os.environ[key] = value

    after_val = mask_secret_value(value) if is_secret else value

    await record_audit(
        db,
        user=current_user,
        action="config.update",
        resource_type="system_setting",
        resource_id=setting_row.id,
        before={"key": key, "value": before_val},
        after={"key": key, "value": after_val},
        request=request,
    )

    return setting_row


async def list_all_settings(db: AsyncSession, reveal_secrets: bool = False) -> list[dict[str, Any]]:
    """Return all system settings grouped and formatted for the admin configuration UI."""
    stmt = select(SystemSetting).order_by(SystemSetting.category.asc(), SystemSetting.key.asc())
    rows = list((await db.execute(stmt)).scalars().all())

    result = []
    for r in rows:
        val = r.value or ""
        display_val = val if (reveal_secrets or not r.is_secret) else mask_secret_value(val)
        result.append(
            {
                "id": str(r.id),
                "key": r.key,
                "value": display_val,
                "raw_value": val if reveal_secrets else None,
                "is_configured": bool(val and val.strip()),
                "category": r.category,
                "description": r.description or "",
                "is_secret": r.is_secret,
                "is_editable": r.is_editable,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
        )
    return result
