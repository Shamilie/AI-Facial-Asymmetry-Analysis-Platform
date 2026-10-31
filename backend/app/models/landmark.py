"""
Landmark models — definitions, AI predictions, and expert reviews.
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
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class LandmarkTypeEnum(str, enum.Enum):
    FACIAL = "Facial"
    OPG = "OPG"


class PredictionStatusEnum(str, enum.Enum):
    PREDICTED = "Predicted"
    REVIEWED = "Reviewed"
    APPROVED = "Approved"
    NOT_IDENTIFIABLE = "NotIdentifiable"
    REJECTED = "Rejected"


class ReviewStatusEnum(str, enum.Enum):
    CONFIRMED = "Confirmed"
    CORRECTED = "Corrected"
    REJECTED = "Rejected"
    NOT_IDENTIFIABLE = "NotIdentifiable"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LandmarkDefinition(Base):
    """Anatomical landmark catalogue entry."""

    __tablename__ = "landmark_definitions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    side: Mapped[str] = mapped_column(String(10), default="Midline", nullable=False)  # Right|Left|Midline
    applicable_views: Mapped[list | None] = mapped_column(JSON)
    landmark_type: Mapped[LandmarkTypeEnum] = mapped_column(
        Enum(LandmarkTypeEnum, name="landmark_type_enum", native_enum=False),
        nullable=False,
    )
    anatomical_region: Mapped[str | None] = mapped_column(String(200))
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_bilateral: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    protocol_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("protocol_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    protocol_version: Mapped["ProtocolVersion"] = relationship(  # type: ignore[name-defined]
        "ProtocolVersion", foreign_keys=[protocol_version_id], lazy="selectin"
    )
    predictions: Mapped[list[LandmarkPrediction]] = relationship(
        "LandmarkPrediction", back_populates="landmark_definition"
    )


class LandmarkPrediction(Base):
    """A single AI-predicted landmark coordinate."""

    __tablename__ = "landmark_predictions"

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visit_images.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    landmark_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("landmark_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # "AI" for model predictions; "Manual" for examiner-added permitted landmarks.
    source: Mapped[str] = mapped_column(String(20), default="AI", nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Null coordinates are permitted ONLY when the model reports the landmark as not identifiable.
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)
    z: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[PredictionStatusEnum] = mapped_column(
        Enum(PredictionStatusEnum, name="prediction_status_enum", native_enum=False),
        default=PredictionStatusEnum.PREDICTED,
        nullable=False,
    )
    model_name: Mapped[str | None] = mapped_column(String(200))
    model_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    image: Mapped["VisitImage"] = relationship(  # type: ignore[name-defined]
        "VisitImage", back_populates="landmark_predictions"
    )
    job: Mapped["AIJob"] = relationship(  # type: ignore[name-defined]
        "AIJob", back_populates="landmark_predictions"
    )
    landmark_definition: Mapped[LandmarkDefinition] = relationship(
        "LandmarkDefinition", back_populates="predictions"
    )
    reviews: Mapped[list[LandmarkReview]] = relationship(
        "LandmarkReview", back_populates="prediction", cascade="all, delete-orphan"
    )


class LandmarkReview(Base):
    """Expert review / correction of a landmark prediction."""

    __tablename__ = "landmark_reviews"

    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("landmark_predictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    corrected_x: Mapped[float | None] = mapped_column(Float)
    corrected_y: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[ReviewStatusEnum] = mapped_column(
        Enum(ReviewStatusEnum, name="review_status_enum", native_enum=False),
        nullable=False,
    )
    correction_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    prediction: Mapped[LandmarkPrediction] = relationship(
        "LandmarkPrediction", back_populates="reviews"
    )
    reviewer: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[reviewer_id], lazy="selectin"
    )
