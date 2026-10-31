"""
Image models — uploaded visit images and AI quality-check results.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ImageTypeEnum(str, enum.Enum):
    FRONTAL = "Frontal"
    RIGHT_LATERAL = "RightLateral"
    LEFT_LATERAL = "LeftLateral"
    OPG = "OPG"


class UploadStatusEnum(str, enum.Enum):
    UPLOADING = "Uploading"
    COMPLETED = "Completed"
    FAILED = "Failed"


class QualityStatusEnum(str, enum.Enum):
    PASS = "Pass"
    WARNING = "Warning"
    FAIL = "Fail"


class ManualOverrideStatusEnum(str, enum.Enum):
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class VisitImage(TimestampMixin, Base):
    """An image captured during a visit."""

    __tablename__ = "visit_images"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_type: Mapped[ImageTypeEnum] = mapped_column(
        Enum(ImageTypeEnum, name="image_type_enum", native_enum=False),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    capture_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device_metadata: Mapped[dict | None] = mapped_column(JSON)
    upload_status: Mapped[UploadStatusEnum] = mapped_column(
        Enum(UploadStatusEnum, name="upload_status_enum", native_enum=False),
        default=UploadStatusEnum.UPLOADING,
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    # Effective acceptance decision for analysis: Pending | Accepted | Rejected
    acceptance_status: Mapped[str] = mapped_column(String(20), default="Pending", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- relationships ---
    visit: Mapped["Visit"] = relationship(  # type: ignore[name-defined]
        "Visit", back_populates="images"
    )
    uploader: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[uploaded_by], lazy="selectin"
    )
    quality_results: Mapped[list[ImageQualityResult]] = relationship(
        "ImageQualityResult", back_populates="image", cascade="all, delete-orphan"
    )
    landmark_predictions: Mapped[list["LandmarkPrediction"]] = relationship(  # type: ignore[name-defined]
        "LandmarkPrediction", back_populates="image", cascade="all, delete-orphan"
    )


class ImageQualityResult(Base):
    """Result of an AI image-quality assessment."""

    __tablename__ = "image_quality_results"

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visit_images.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(200))
    model_version: Mapped[str | None] = mapped_column(String(50))
    overall_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[QualityStatusEnum] = mapped_column(
        Enum(QualityStatusEnum, name="quality_status_enum", native_enum=False),
        nullable=False,
    )

    # Individual check payloads (JSON blobs)
    face_visibility: Mapped[dict | None] = mapped_column(JSON)
    orientation_check: Mapped[dict | None] = mapped_column(JSON)
    lighting_check: Mapped[dict | None] = mapped_column(JSON)
    blur_check: Mapped[dict | None] = mapped_column(JSON)
    occlusion_check: Mapped[dict | None] = mapped_column(JSON)
    framing_check: Mapped[dict | None] = mapped_column(JSON)
    resolution_check: Mapped[dict | None] = mapped_column(JSON)

    issues: Mapped[list | None] = mapped_column(JSON)
    suggestions: Mapped[list | None] = mapped_column(JSON)

    # Manual override
    manual_override_status: Mapped[ManualOverrideStatusEnum | None] = mapped_column(
        Enum(ManualOverrideStatusEnum, name="manual_override_status_enum", native_enum=False)
    )
    manual_override_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    manual_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    image: Mapped[VisitImage] = relationship(
        "VisitImage", back_populates="quality_results"
    )
    overrider: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[manual_override_by], lazy="selectin"
    )
