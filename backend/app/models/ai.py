"""
AI job orchestration models — jobs, events, provider configs, model registry.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AITaskTypeEnum(str, enum.Enum):
    IMAGE_VALIDATION = "ImageValidation"
    IMAGE_QUALITY = "ImageQuality"
    FACIAL_LANDMARK = "FacialLandmark"
    FACIAL_SEGMENTATION = "FacialSegmentation"
    MULTI_VIEW_CORRESPONDENCE = "MultiViewCorrespondence"
    RECONSTRUCTION_3D = "Reconstruction3D"
    OPG_LANDMARK = "OPGLandmark"
    OPG_SEGMENTATION = "OPGSegmentation"
    CALIBRATION = "Calibration"
    MEASUREMENT_CALC = "MeasurementCalc"
    REPORT_GENERATION = "ReportGeneration"


class AIJobStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    QUEUED = "Queued"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    REVIEW_REQUIRED = "ReviewRequired"
    NOT_IDENTIFIABLE = "NotIdentifiable"
    UNSCALED = "Unscaled"
    VALIDATED = "Validated"
    SKIPPED = "Skipped"


class ProviderTypeEnum(str, enum.Enum):
    DEMO = "Demo"
    MEDIAPIPE = "MediaPipe"
    OPENAI = "OpenAI"
    GEMINI = "Gemini"
    NVIDIA = "NVIDIA"
    CUSTOM_GPU = "CustomGPU"
    LOCAL_MODEL = "LocalModel"


class EnvironmentEnum(str, enum.Enum):
    DEVELOPMENT = "Development"
    STAGING = "Staging"
    PRODUCTION = "Production"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AIJob(TimestampMixin, Base):
    """A single AI processing task (e.g. landmark detection on an image)."""

    __tablename__ = "ai_jobs"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[AITaskTypeEnum] = mapped_column(
        Enum(AITaskTypeEnum, name="ai_task_type_enum", native_enum=False),
        nullable=False,
    )
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
    )
    status: Mapped[AIJobStatusEnum] = mapped_column(
        Enum(AIJobStatusEnum, name="ai_job_status_enum", native_enum=False),
        default=AIJobStatusEnum.PENDING,
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict | None] = mapped_column(JSON)
    model_name: Mapped[str | None] = mapped_column(String(200))
    model_version: Mapped[str | None] = mapped_column(String(50))
    provider_name: Mapped[str | None] = mapped_column(String(100))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    stage_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    warnings: Mapped[list | None] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON)
    protocol_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("protocol_versions.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # --- relationships ---
    visit: Mapped["Visit"] = relationship(  # type: ignore[name-defined]
        "Visit", back_populates="ai_jobs"
    )
    patient: Mapped["Patient"] = relationship("Patient", lazy="selectin")  # type: ignore[name-defined]
    provider_config: Mapped[AIProviderConfig | None] = relationship(
        "AIProviderConfig", foreign_keys=[provider_config_id], lazy="selectin"
    )
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[created_by], lazy="selectin"
    )
    events: Mapped[list[AIJobEvent]] = relationship(
        "AIJobEvent", back_populates="job", cascade="all, delete-orphan"
    )
    landmark_predictions: Mapped[list["LandmarkPrediction"]] = relationship(  # type: ignore[name-defined]
        "LandmarkPrediction", back_populates="job", cascade="all, delete-orphan"
    )
    reconstruction_assets: Mapped[list["ReconstructionAsset"]] = relationship(  # type: ignore[name-defined]
        "ReconstructionAsset", back_populates="job", cascade="all, delete-orphan"
    )


class AIJobEvent(Base):
    """Timestamped event emitted during an AI job's lifecycle."""

    __tablename__ = "ai_job_events"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    job: Mapped[AIJob] = relationship("AIJob", back_populates="events")


class AIProviderConfig(TimestampMixin, Base):
    """Configuration for a specific AI provider / model combination."""

    __tablename__ = "ai_provider_configs"

    provider_type: Mapped[ProviderTypeEnum] = mapped_column(
        Enum(ProviderTypeEnum, name="provider_type_enum", native_enum=False),
        nullable=False,
    )
    task_type: Mapped[AITaskTypeEnum] = mapped_column(
        Enum(AITaskTypeEnum, name="ai_task_type_enum", native_enum=False, create_constraint=False),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_identifier: Mapped[str | None] = mapped_column(String(500))
    model_version: Mapped[str | None] = mapped_column(String(50))
    display_name: Mapped[str | None] = mapped_column(String(200))
    endpoint_url: Mapped[str | None] = mapped_column(String(1000))
    settings_json: Mapped[dict | None] = mapped_column(JSON)
    last_health_message: Mapped[str | None] = mapped_column(Text)
    credential_key_name: Mapped[str | None] = mapped_column(String(200))
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    environment: Mapped[EnvironmentEnum] = mapped_column(
        Enum(EnvironmentEnum, name="environment_enum", native_enum=False),
        default=EnvironmentEnum.DEVELOPMENT,
        nullable=False,
    )
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_health_status: Mapped[str | None] = mapped_column(String(50))


class AIModelRegistry(Base):
    """Registry of known AI models and their capabilities."""

    __tablename__ = "ai_model_registry"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_type: Mapped[ProviderTypeEnum] = mapped_column(
        Enum(ProviderTypeEnum, name="provider_type_enum", native_enum=False, create_constraint=False),
        nullable=False,
    )
    supported_tasks: Mapped[list | None] = mapped_column(JSON)
    version: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict | None] = mapped_column(JSON)
    output_schema: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
