"""
Patient-related models: demographics, consent, fracture and surgery details.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
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


class SexEnum(str, enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    NOT_COLLECTED = "NotCollected"


class StudyStatusEnum(str, enum.Enum):
    DRAFT = "Draft"
    ENROLLED = "Enrolled"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    WITHDRAWN = "Withdrawn"
    EXCLUDED = "Excluded"


class ConsentStatusEnum(str, enum.Enum):
    OBTAINED = "Obtained"
    PENDING = "Pending"
    DECLINED = "Declined"
    WITHDRAWN = "Withdrawn"


class FractureSideEnum(str, enum.Enum):
    RIGHT = "Right"
    LEFT = "Left"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Patient(TimestampMixin, Base):
    """A study participant."""

    __tablename__ = "patients"

    patient_code: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    hospital_id: Mapped[str | None] = mapped_column(String(200))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    age_at_enrollment: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[SexEnum | None] = mapped_column(
        Enum(SexEnum, name="sex_enum", native_enum=False)
    )
    enrollment_date: Mapped[date | None] = mapped_column(Date)
    study_status: Mapped[StudyStatusEnum] = mapped_column(
        Enum(StudyStatusEnum, name="study_status_enum", native_enum=False),
        default=StudyStatusEnum.ENROLLED,
        index=True,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    draft_data: Mapped[dict | None] = mapped_column(JSON)
    protocol_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("protocol_versions.id", ondelete="SET NULL")
    )

    # --- relationships ---
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[created_by], lazy="selectin"
    )
    consents: Mapped[list[PatientConsent]] = relationship(
        "PatientConsent", back_populates="patient", cascade="all, delete-orphan"
    )
    fracture_detail: Mapped[FractureDetail | None] = relationship(
        "FractureDetail", back_populates="patient", uselist=False, cascade="all, delete-orphan"
    )
    surgery_detail: Mapped[SurgeryDetail | None] = relationship(
        "SurgeryDetail", back_populates="patient", uselist=False, cascade="all, delete-orphan"
    )
    visits: Mapped[list["Visit"]] = relationship(  # type: ignore[name-defined]
        "Visit", back_populates="patient", cascade="all, delete-orphan"
    )


class PatientConsent(TimestampMixin, Base):
    """Informed-consent record."""

    __tablename__ = "patient_consents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    consent_status: Mapped[ConsentStatusEnum] = mapped_column(
        Enum(ConsentStatusEnum, name="consent_status_enum", native_enum=False),
        nullable=False,
    )
    consent_date: Mapped[date | None] = mapped_column(Date)
    consent_document_ref: Mapped[str | None] = mapped_column(String(500))

    # --- relationships ---
    patient: Mapped[Patient] = relationship("Patient", back_populates="consents")


class FractureDetail(TimestampMixin, Base):
    """Clinical fracture information (one-to-one with Patient)."""

    __tablename__ = "fracture_details"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    fracture_side: Mapped[FractureSideEnum | None] = mapped_column(
        Enum(FractureSideEnum, name="fracture_side_enum", native_enum=False)
    )
    fracture_classification: Mapped[str | None] = mapped_column(String(200))
    fracture_location: Mapped[str | None] = mapped_column(String(200))
    injury_date: Mapped[date | None] = mapped_column(Date)
    injury_mechanism: Mapped[str | None] = mapped_column(Text)
    associated_fractures: Mapped[str | None] = mapped_column(Text)
    clinical_notes: Mapped[str | None] = mapped_column(Text)

    # --- relationships ---
    patient: Mapped[Patient] = relationship("Patient", back_populates="fracture_detail")


class SurgeryDetail(TimestampMixin, Base):
    """Surgical intervention record (one-to-one with Patient)."""

    __tablename__ = "surgery_details"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    surgery_date: Mapped[date | None] = mapped_column(Date)
    fixation_type: Mapped[str | None] = mapped_column(String(200))
    surgical_approach: Mapped[str | None] = mapped_column(String(200))
    plate_details: Mapped[str | None] = mapped_column(Text)
    surgeon_name: Mapped[str | None] = mapped_column(String(255))
    operative_notes: Mapped[str | None] = mapped_column(Text)

    # --- relationships ---
    patient: Mapped[Patient] = relationship("Patient", back_populates="surgery_detail")
