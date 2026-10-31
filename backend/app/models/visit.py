"""
Visit model — scheduled and completed patient visits.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class VisitTypeEnum(str, enum.Enum):
    PRE_OPERATIVE = "PreOperative"
    POST_OP_1_WEEK = "PostOp1Week"
    POST_OP_6_WEEKS = "PostOp6Weeks"
    POST_OP_3_MONTHS = "PostOp3Months"
    POST_OP_6_MONTHS = "PostOp6Months"


class VisitStatusEnum(str, enum.Enum):
    PLANNED = "Planned"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "InProgress"
    IMAGES_PENDING = "ImagesPending"
    PROCESSING = "Processing"
    REVIEW_REQUIRED = "ReviewRequired"
    COMPLETED = "Completed"
    MISSED = "Missed"
    CANCELLED = "Cancelled"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Visit(TimestampMixin, Base):
    """A single visit in the study protocol for a patient."""

    __tablename__ = "visits"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_type: Mapped[VisitTypeEnum] = mapped_column(
        Enum(VisitTypeEnum, name="visit_type_enum", native_enum=False),
        nullable=False,
    )
    planned_date: Mapped[date | None] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[VisitStatusEnum] = mapped_column(
        Enum(VisitStatusEnum, name="visit_status_enum", native_enum=False),
        default=VisitStatusEnum.PLANNED,
        index=True,
        nullable=False,
    )
    examiner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    protocol_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("protocol_versions.id", ondelete="SET NULL")
    )

    # --- relationships ---
    patient: Mapped["Patient"] = relationship(  # type: ignore[name-defined]
        "Patient", back_populates="visits"
    )
    examiner: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[examiner_id], lazy="selectin"
    )
    protocol_version: Mapped["ProtocolVersion"] = relationship(  # type: ignore[name-defined]
        "ProtocolVersion", foreign_keys=[protocol_version_id], lazy="selectin"
    )
    images: Mapped[list["VisitImage"]] = relationship(  # type: ignore[name-defined]
        "VisitImage", back_populates="visit", cascade="all, delete-orphan"
    )
    ai_jobs: Mapped[list["AIJob"]] = relationship(  # type: ignore[name-defined]
        "AIJob", back_populates="visit", cascade="all, delete-orphan"
    )
    measurements: Mapped[list["Measurement"]] = relationship(  # type: ignore[name-defined]
        "Measurement", back_populates="visit", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(  # type: ignore[name-defined]
        "Report", back_populates="visit"
    )
    reconstruction_assets: Mapped[list["ReconstructionAsset"]] = relationship(  # type: ignore[name-defined]
        "ReconstructionAsset", back_populates="visit", cascade="all, delete-orphan"
    )
    clinical_assessment: Mapped["ClinicalAssessment | None"] = relationship(  # type: ignore[name-defined]
        "ClinicalAssessment", back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )
