"""
Clinical assessment model — structured clinical examination findings per visit.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class ClinicalAssessment(TimestampMixin, Base):
    """Clinical examination record captured during a study visit."""

    __tablename__ = "clinical_assessments"

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
    examiner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    assessment_date: Mapped[date | None] = mapped_column(Date)
    facial_swelling_grade: Mapped[str | None] = mapped_column(String(100))
    occlusion_status: Mapped[str | None] = mapped_column(String(200))
    maximal_interincisal_opening_mm: Mapped[float | None] = mapped_column(Float)
    neurosensory_status: Mapped[str | None] = mapped_column(String(200))
    chin_deviation_mm: Mapped[float | None] = mapped_column(Float)
    chin_deviation_side: Mapped[str | None] = mapped_column(String(50))
    soft_tissue_healing: Mapped[str | None] = mapped_column(String(200))
    pain_score_vas: Mapped[float | None] = mapped_column(Float)
    complications_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    complication_details: Mapped[str | None] = mapped_column(Text)
    paired_physical_measurements: Mapped[dict | None] = mapped_column(JSON)
    examiner_notes: Mapped[str | None] = mapped_column(Text)

    # --- relationships ---
    visit: Mapped["Visit"] = relationship(  # type: ignore[name-defined]
        "Visit", back_populates="clinical_assessment", lazy="selectin"
    )
    patient: Mapped["Patient"] = relationship("Patient", lazy="selectin")  # type: ignore[name-defined]
    examiner: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[examiner_id], lazy="selectin"
    )
