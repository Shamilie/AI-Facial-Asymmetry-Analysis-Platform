"""
Measurement models — definitions, calculated values, and approval workflow.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class MeasurementTypeEnum(str, enum.Enum):
    LINEAR = "Linear"
    ANGULAR = "Angular"
    RATIO = "Ratio"
    AREA = "Area"
    INDEX = "Index"


class MeasurementMethodEnum(str, enum.Enum):
    AI_PREDICTED = "AIPredicted"
    EXAMINER_REVIEWED = "ExaminerReviewed"
    VALIDATED = "Validated"


class MeasurementStatusEnum(str, enum.Enum):
    CALCULATED = "Calculated"
    REVIEW_REQUIRED = "ReviewRequired"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    INVALID = "Invalid"
    MISSING_DATA = "MissingData"
    UNSCALED = "Unscaled"
    NOT_IDENTIFIABLE = "NotIdentifiable"


class ApprovalStatusEnum(str, enum.Enum):
    APPROVED = "Approved"
    REJECTED = "Rejected"
    NEEDS_REVISION = "NeedsRevision"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class MeasurementDefinition(Base):
    """Describes *what* is measured (e.g. inter-orbital distance)."""

    __tablename__ = "measurement_definitions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Structured, machine-readable definition consumed by the geometric engine.
    spec: Mapped[dict | None] = mapped_column(JSON)
    is_bilateral: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    measurement_type: Mapped[MeasurementTypeEnum] = mapped_column(
        Enum(MeasurementTypeEnum, name="measurement_type_enum", native_enum=False),
        nullable=False,
    )
    landmark_left_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("landmark_definitions.id", ondelete="SET NULL"),
    )
    landmark_right_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("landmark_definitions.id", ondelete="SET NULL"),
    )
    formula: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(50))
    protocol_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("protocol_versions.id", ondelete="SET NULL")
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    landmark_left: Mapped["LandmarkDefinition"] = relationship(  # type: ignore[name-defined]
        "LandmarkDefinition", foreign_keys=[landmark_left_id], lazy="selectin"
    )
    landmark_right: Mapped["LandmarkDefinition"] = relationship(  # type: ignore[name-defined]
        "LandmarkDefinition", foreign_keys=[landmark_right_id], lazy="selectin"
    )
    protocol_version: Mapped["ProtocolVersion"] = relationship(  # type: ignore[name-defined]
        "ProtocolVersion", foreign_keys=[protocol_version_id], lazy="selectin"
    )
    measurements: Mapped[list[Measurement]] = relationship(
        "Measurement", back_populates="measurement_definition"
    )


class Measurement(TimestampMixin, Base):
    """A concrete measurement value for a visit."""

    __tablename__ = "measurements"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    measurement_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("measurement_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    right_value: Mapped[float | None] = mapped_column(Float)
    left_value: Mapped[float | None] = mapped_column(Float)
    absolute_difference: Mapped[float | None] = mapped_column(Float)
    asymmetry_index: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50))
    source_image_type: Mapped[str | None] = mapped_column(String(50))
    calibration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calibration_records.id", ondelete="SET NULL"),
    )
    method: Mapped[MeasurementMethodEnum] = mapped_column(
        Enum(MeasurementMethodEnum, name="measurement_method_enum", native_enum=False),
        nullable=False,
    )
    model_name: Mapped[str | None] = mapped_column(String(200))
    model_version: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[MeasurementStatusEnum] = mapped_column(
        Enum(MeasurementStatusEnum, name="measurement_status_enum", native_enum=False),
        default=MeasurementStatusEnum.CALCULATED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    landmark_refs: Mapped[dict | None] = mapped_column(JSON)
    warnings: Mapped[list | None] = mapped_column(JSON)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_unscaled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    calculated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="SET NULL")
    )
    protocol_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("protocol_versions.id", ondelete="SET NULL")
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text)

    # --- relationships ---
    visit: Mapped["Visit"] = relationship(  # type: ignore[name-defined]
        "Visit", back_populates="measurements"
    )
    measurement_definition: Mapped[MeasurementDefinition] = relationship(
        "MeasurementDefinition", back_populates="measurements", lazy="selectin"
    )
    calibration: Mapped["CalibrationRecord"] = relationship(  # type: ignore[name-defined]
        "CalibrationRecord", foreign_keys=[calibration_id], lazy="selectin"
    )
    approvals: Mapped[list[MeasurementApproval]] = relationship(
        "MeasurementApproval", back_populates="measurement", cascade="all, delete-orphan"
    )


class MeasurementApproval(Base):
    """Approval / rejection of a measurement by an authorised reviewer."""

    __tablename__ = "measurement_approvals"

    measurement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("measurements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    approval_status: Mapped[ApprovalStatusEnum] = mapped_column(
        Enum(ApprovalStatusEnum, name="approval_status_enum", native_enum=False),
        nullable=False,
    )
    comments: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    measurement: Mapped[Measurement] = relationship(
        "Measurement", back_populates="approvals"
    )
    approver: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[approver_id], lazy="selectin"
    )
