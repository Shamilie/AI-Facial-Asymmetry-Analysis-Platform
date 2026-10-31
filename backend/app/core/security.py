"""
Authentication & authorisation utilities.

* Password hashing (bcrypt)
* JWT access / refresh token creation & verification
* FastAPI dependencies: ``get_current_user``, ``require_permissions``
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(subject: str | uuid.UUID, extra_claims: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire, "type": "access", "jti": uuid.uuid4().hex}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(subject), "exp": expire, "type": "refresh", "jti": uuid.uuid4().hex}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_reset_token(subject: str | uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    payload = {"sub": str(subject), "exp": expire, "type": "reset"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# In-memory token revocation list (logout). Replace with Redis in multi-instance deployments.
_REVOKED_JTIS: set[str] = set()


def revoke_token(token: str) -> None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("jti"):
            _REVOKED_JTIS.add(payload["jti"])
    except JWTError:
        pass


def verify_token(token: str, *, expected_type: str = "access") -> dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired", headers={"WWW-Authenticate": "Bearer"})
    except JWTError:
        raise credentials_exception
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise credentials_exception
    if payload.get("jti") in _REVOKED_JTIS:
        raise HTTPException(status_code=401, detail="Session has been logged out")
    return payload


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter (per key, sliding window)
# ---------------------------------------------------------------------------

_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    now = time.monotonic()
    bucket = _RATE_BUCKETS[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")
    bucket.append(now)


# ---------------------------------------------------------------------------
# Current user dependencies
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def load_user_with_permissions(db: AsyncSession, user_id: uuid.UUID) -> Any:
    from app.models.user import Role, RolePermission, User, UserRole

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.user_roles)
            .selectinload(UserRole.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        return None
    perms: set[str] = set()
    roles: list[str] = []
    for ur in user.user_roles:
        roles.append(ur.role.name)
        for rp in ur.role.role_permissions:
            perms.add(rp.permission.name)
    if user.is_superuser:
        from app.core.permissions import ALL_PERMISSIONS

        perms = set(ALL_PERMISSIONS)
    user.permission_names = perms  # type: ignore[attr-defined]
    user.role_names = roles  # type: ignore[attr-defined]
    return user


async def _user_from_token(token: str | None, db: AsyncSession) -> Any:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    payload = verify_token(token, expected_type="access")
    user = await load_user_with_permissions(db, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Query(default=None, include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return the authenticated user.

    A ``?access_token=`` query parameter is accepted only for GET requests to
    support EventSource (SSE) streams and <img> file previews, which cannot set headers.
    """
    if not token and access_token and request.method == "GET":
        token = access_token
    return await _user_from_token(token, db)


def require_permissions(*permission_names: str):
    """Dependency factory: user must hold *all* listed permissions."""

    async def _checker(current_user: Any = Depends(get_current_user)) -> Any:
        missing = set(permission_names) - current_user.permission_names
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: requires {', '.join(sorted(missing))}",
            )
        return current_user

    return _checker


def has_permission(user: Any, permission: str) -> bool:
    return permission in getattr(user, "permission_names", set())
