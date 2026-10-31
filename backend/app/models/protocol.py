"""
Study protocol models — protocol definitions and versioned configurations.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class StudyProtocol(TimestampMixin, Base):
    """Top-level study protocol (e.g. 'ZMC Fracture Asymmetry Study')."""

    __tablename__ = "study_protocols"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    identifier: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # --- relationships ---
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[created_by], lazy="selectin"
    )
    versions: Mapped[list[ProtocolVersion]] = relationship(
        "ProtocolVersion", back_populates="protocol", cascade="all, delete-orphan"
    )


class ProtocolVersion(TimestampMixin, Base):
    """A versioned snapshot of protocol rules (visit schedule, required images, etc.)."""

    __tablename__ = "protocol_versions"

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_protocols.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[str] = mapped_column(String(50), nullable=False)
    visit_schedule: Mapped[dict | None] = mapped_column(JSON)
    required_image_types: Mapped[list | None] = mapped_column(JSON)
    landmark_set: Mapped[list | None] = mapped_column(JSON)
    measurement_set: Mapped[list | None] = mapped_column(JSON)
    calibration_rules: Mapped[dict | None] = mapped_column(JSON)
    review_requirements: Mapped[dict | None] = mapped_column(JSON)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)

    # --- relationships ---
    protocol: Mapped[StudyProtocol] = relationship(
        "StudyProtocol", back_populates="versions"
    )
