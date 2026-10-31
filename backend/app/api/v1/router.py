"""
API v1 master router aggregating all domain endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    ai,
    analytics,
    auth,
    calibration,
    dashboard,
    images,
    landmarks,
    measurements,
    patients,
    reconstruction,
    reports,
    visits,
    workspace_compat,
)

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(patients.router)
api_v1_router.include_router(visits.router)
api_v1_router.include_router(images.router)
api_v1_router.include_router(ai.router)
api_v1_router.include_router(landmarks.router)
api_v1_router.include_router(reconstruction.router)
api_v1_router.include_router(calibration.router)
api_v1_router.include_router(measurements.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(workspace_compat.router)
