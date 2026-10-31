"""
FastAPI application entrypoint for the AI Facial Asymmetry Analysis Platform.

Includes:
  * Lifespan startup hook that creates database tables and seeds demo data
  * Consistent JSON error handling
  * CORS middleware
  * OpenAPI / Swagger documentation at /docs and /redoc
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.models  # noqa: F401 - register all SQLAlchemy models
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import (
    ACTIVE_DATABASE_LABEL,
    Base,
    engine,
    get_db,
    managed_async_session,
)
from app.services.seed import ensure_seeded
from app.services.storage import get_database_storage_stats, migrate_files_to_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with managed_async_session() as session:
        await ensure_seeded(session)
        await migrate_files_to_database(session)
    yield


app = FastAPI(
    title="AI Facial Asymmetry Analysis Platform API",
    version="1.0.0",
    description=(
        "Medical research platform API for longitudinal quantitative facial asymmetry analysis "
        "in patients with unilateral mandibular fractures treated by fixation. "
        "Outputs are strictly for research measurement and documentation — not clinical diagnosis."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def _http_exception_handler(_req: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": exc.detail,
            "error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)},
        },
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(_req: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "detail": "Validation error",
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "One or more fields failed validation",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(_req: Request, exc: Exception) -> JSONResponse:
    import traceback

    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "detail": f"Internal server error: {exc}",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
            },
        },
    )


@app.get("/health", tags=["Health"])
async def health() -> dict:
    async with managed_async_session() as session:
        blob_stats = await get_database_storage_stats(session)
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "database_engine": ACTIVE_DATABASE_LABEL,
        "storage_backend": settings.STORAGE_BACKEND,
        "database_blob_storage": blob_stats,
        "external_ai_uploads_enabled": settings.ALLOW_EXTERNAL_AI_UPLOADS,
    }


@app.get("/api/v1/system/database-status", tags=["Health"])
async def database_status() -> dict:
    async with managed_async_session() as session:
        blob_stats = await get_database_storage_stats(session)
    return {
        "success": True,
        "data": {
            "database_engine": ACTIVE_DATABASE_LABEL,
            "storage_backend": settings.STORAGE_BACKEND,
            "total_tables": len(Base.metadata.tables),
            "blob_storage": blob_stats,
        },
    }


app.include_router(api_v1_router)
