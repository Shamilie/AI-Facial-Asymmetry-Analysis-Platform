"""
Authentication endpoints: login, logout, token refresh, current user profile,
and password reset.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.responses import ok
from app.core.security import (
    check_rate_limit,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    load_user_with_permissions,
    oauth2_scheme,
    revoke_token,
    verify_password,
    verify_token,
)
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=4)
    remember_me: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


def _normalize_email(email: str) -> str:
    cleaned = email.lower().strip()
    if cleaned.endswith("@facial-asymmetry-research.org"):
        cleaned = cleaned.replace("@facial-asymmetry-research.org", "@faplatform.org")
    return cleaned


def _serialize_user(user: Any) -> dict[str, Any]:
    roles = getattr(user, "role_names", [])
    perms = sorted(getattr(user, "permission_names", set()))
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "roles": roles,
        "primary_role": roles[0] if roles else ("System Administrator" if user.is_superuser else "Read-only Researcher"),
        "permissions": perms,
    }


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    client_ip = request.client.host if request.client else "local"
    check_rate_limit(f"login:{client_ip}", settings.LOGIN_RATE_LIMIT_PER_MINUTE, 60)

    stmt = select(User).where(User.email == _normalize_email(payload.email))
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        await record_audit(
            db,
            user=None,
            action="auth.login_failed",
            resource_type="user",
            after={"email": payload.email},
            request=request,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated")

    user = await load_user_with_permissions(db, user.id)
    access_token = create_access_token(user.id, {"roles": getattr(user, "role_names", [])})
    refresh_token = create_refresh_token(user.id)

    await record_audit(
        db,
        user=user,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        after={"email": user.email, "roles": getattr(user, "role_names", [])},
        request=request,
    )
    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": _serialize_user(user),
        },
        message="Signed in successfully",
    )


@router.post("/token", include_in_schema=False)
async def oauth2_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Standard OAuth2 password flow for Swagger UI Authorize button."""
    stmt = select(User).where(User.email == form_data.username.lower().strip())
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not verify_password(form_data.password, user.hashed_password) or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = await load_user_with_permissions(db, user.id)
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if token:
        revoke_token(token)
    await record_audit(
        db,
        user=current_user,
        action="auth.logout",
        resource_type="user",
        resource_id=current_user.id,
        request=request,
    )
    return ok({"logged_out": True}, message="Logged out")


@router.post("/refresh")
async def refresh_access_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> dict:
    decoded = verify_token(payload.refresh_token, expected_type="refresh")
    user = await load_user_with_permissions(db, uuid.UUID(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    access_token = create_access_token(user.id, {"roles": getattr(user, "role_names", [])})
    return ok(
        {
            "access_token": access_token,
            "refresh_token": payload.refresh_token,
            "token_type": "bearer",
            "user": _serialize_user(user),
        }
    )


@router.get("/me")
async def get_me(current_user: Any = Depends(get_current_user)) -> dict:
    return ok(_serialize_user(current_user))


@router.post("/reset-password")
async def reset_password(
    payload: PasswordResetRequest,
    request: Request,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Self password change or administrator reset
    if current_user.email.lower() != payload.email.lower() and "user:manage" not in current_user.permission_names:
        raise HTTPException(status_code=403, detail="Not authorized to reset another user's password")
    target = (await db.execute(select(User).where(User.email == payload.email.lower().strip()))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target.hashed_password = hash_password(payload.new_password)
    await record_audit(
        db,
        user=current_user,
        action="auth.password_reset",
        resource_type="user",
        resource_id=target.id,
        reason="Password updated",
        request=request,
    )
    return ok({"reset": True}, message="Password updated successfully")


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    target = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if target is None or not verify_password(payload.current_password, target.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    target.hashed_password = hash_password(payload.new_password)
    await record_audit(
        db,
        user=current_user,
        action="auth.change_password",
        resource_type="user",
        resource_id=target.id,
        reason="User changed own password",
        request=request,
    )
    return ok({"message": "Password updated successfully"})
