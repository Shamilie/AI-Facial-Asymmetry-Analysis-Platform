"""
Report models — generated analysis reports and their exports.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ReportTypeEnum(str, enum.Enum):
    PATIENT_SUMMARY = "PatientSummary"
    VISIT_ANALYSIS = "VisitAnalysis"
    COHORT_SUMMARY = "CohortSummary"
    RESEARCH_EXPORT = "ResearchExport"


class ReportStatusEnum(str, enum.Enum):
    DRAFT = "Draft"
    GENERATED = "Generated"
    REVIEWED = "Reviewed"
    APPROVED = "Approved"
    EXPORTED = "Exported"


class ExportFormatEnum(str, enum.Enum):
    PDF = "PDF"
    CSV = "CSV"
    EXCEL = "Excel"
    JSON = "JSON"
    OBJ = "OBJ"
    PLY = "PLY"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Report(TimestampMixin, Base):
    """A generated analysis report."""

    __tablename__ = "reports"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="SET NULL")
    )
    report_type: Mapped[ReportTypeEnum] = mapped_column(
        Enum(ReportTypeEnum, name="report_type_enum", native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[dict | None] = mapped_column(JSON)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="SET NULL")
    )
    protocol_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("protocol_versions.id", ondelete="SET NULL")
    )
    status: Mapped[ReportStatusEnum] = mapped_column(
        Enum(ReportStatusEnum, name="report_status_enum", native_enum=False),
        default=ReportStatusEnum.DRAFT,
        nullable=False,
    )

    # --- relationships ---
    patient: Mapped["Patient"] = relationship("Patient", lazy="selectin")  # type: ignore[name-defined]
    visit: Mapped["Visit"] = relationship(  # type: ignore[name-defined]
        "Visit", back_populates="reports"
    )
    generator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[generated_by], lazy="selectin"
    )
    ai_job: Mapped["AIJob"] = relationship(  # type: ignore[name-defined]
        "AIJob", foreign_keys=[ai_job_id], lazy="selectin"
    )
    protocol_version: Mapped["ProtocolVersion"] = relationship(  # type: ignore[name-defined]
        "ProtocolVersion", foreign_keys=[protocol_version_id], lazy="selectin"
    )
    exports: Mapped[list[ReportExport]] = relationship(
        "ReportExport", back_populates="report", cascade="all, delete-orphan"
    )


class ReportExport(Base):
    """A file exported from a report (PDF, CSV, etc.)."""

    __tablename__ = "report_exports"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_format: Mapped[ExportFormatEnum] = mapped_column(
        Enum(ExportFormatEnum, name="export_format_enum", native_enum=False),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    exported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- relationships ---
    report: Mapped[Report] = relationship("Report", back_populates="exports")
    exporter: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[exported_by], lazy="selectin"
    )
