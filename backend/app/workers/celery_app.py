"""
Celery worker configuration and task definitions.

When ``settings.TASK_BACKEND == "celery"`` and Redis is running, AI pipeline
runs are dispatched to Celery workers. When ``settings.TASK_BACKEND == "inline"``
(default for zero-dependency Windows local development), tasks run via
``asyncio.create_task`` in the FastAPI process while still emitting live SSE events.
"""

from __future__ import annotations

import asyncio
import uuid

from app.core.config import settings

try:
    from celery import Celery  # type: ignore

    celery_app = Celery(
        "fa_platform",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )

    @celery_app.task(name="fa_platform.run_pipeline")
    def run_pipeline_celery_task(visit_id: str, pipeline_run_id: str) -> None:
        from app.ai.orchestrator import execute_pipeline_run

        asyncio.run(execute_pipeline_run(uuid.UUID(visit_id), uuid.UUID(pipeline_run_id)))

except Exception:  # pragma: no cover
    celery_app = None  # type: ignore


def dispatch_pipeline(visit_id: uuid.UUID, pipeline_run_id: uuid.UUID) -> None:
    """Dispatch a pipeline run via Celery or in-process asyncio task."""
    from app.ai.orchestrator import execute_pipeline_run

    if settings.TASK_BACKEND == "celery" and celery_app is not None:
        try:
            run_pipeline_celery_task.delay(str(visit_id), str(pipeline_run_id))
            return
        except Exception:
            pass
    asyncio.create_task(execute_pipeline_run(visit_id, pipeline_run_id))
