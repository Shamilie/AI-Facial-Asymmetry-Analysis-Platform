"""
3-D reconstruction asset model.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AssetTypeEnum(str, enum.Enum):
    MESH = "Mesh"
    TEXTURE = "Texture"
    LANDMARKS_3D = "Landmarks3D"
    POINT_CLOUD = "PointCloud"


class ReconstructionStatusEnum(str, enum.Enum):
    COMPLETE = "Complete"
    PARTIAL = "Partial"
    LOW_CONFIDENCE = "LowConfidence"
    FAILED = "Failed"
    REQUIRES_REVIEW = "RequiresReview"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class ReconstructionAsset(Base):
    """An artefact produced by 3-D face reconstruction."""

    __tablename__ = "reconstruction_assets"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_type: Mapped[AssetTypeEnum] = mapped_column(
        Enum(AssetTypeEnum, name="asset_type_enum", native_enum=False),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_format: Mapped[str] = mapped_column(String(50), nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[ReconstructionStatusEnum] = mapped_column(
        Enum(ReconstructionStatusEnum, name="reconstruction_status_enum", native_enum=False),
        nullable=False,
    )
    warnings: Mapped[list | None] = mapped_column(JSON)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    visit: Mapped["Visit"] = relationship(  # type: ignore[name-defined]
        "Visit", back_populates="reconstruction_assets"
    )
    job: Mapped["AIJob"] = relationship(  # type: ignore[name-defined]
        "AIJob", back_populates="reconstruction_assets"
    )
