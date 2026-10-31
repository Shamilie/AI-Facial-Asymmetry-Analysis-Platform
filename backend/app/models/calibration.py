"""
Calibration record model — pixel-to-millimetre conversion data.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class CalibrationTypeEnum(str, enum.Enum):
    FRONTAL_PHOTO = "FrontalPhoto"
    RIGHT_LATERAL_PHOTO = "RightLateralPhoto"
    LEFT_LATERAL_PHOTO = "LeftLateralPhoto"
    OPG = "OPG"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class CalibrationRecord(TimestampMixin, Base):
    """Stores pixel↔mm calibration parameters for an image or visit."""

    __tablename__ = "calibration_records"

    visit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visits.id", ondelete="SET NULL")
    )
    image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visit_images.id", ondelete="SET NULL")
    )
    calibration_type: Mapped[CalibrationTypeEnum] = mapped_column(
        Enum(CalibrationTypeEnum, name="calibration_type_enum", native_enum=False),
        nullable=False,
    )
    reference_marker_type: Mapped[str | None] = mapped_column(String(200))
    known_marker_length_mm: Mapped[float] = mapped_column(Float, nullable=False)
    measured_marker_length_px: Mapped[float] = mapped_column(Float, nullable=False)
    mm_per_pixel: Mapped[float] = mapped_column(Float, nullable=False)
    marker_location: Mapped[str | None] = mapped_column(String(200))
    calibration_plane: Mapped[str | None] = mapped_column(String(200))
    calibration_method: Mapped[str | None] = mapped_column(String(200))
    magnification_factor: Mapped[float | None] = mapped_column(Float)
    pixel_spacing_x: Mapped[float | None] = mapped_column(Float)
    pixel_spacing_y: Mapped[float | None] = mapped_column(Float)
    warnings: Mapped[list | None] = mapped_column(JSON)
    # Regional / directional OPG calibration factors, e.g. {"horizontal": 0.1, "vertical": 0.11, "regions": {...}}
    regional_calibration: Mapped[dict | None] = mapped_column(JSON)
    # False for display-only PPI assumptions; such records never scale measurements to mm.
    is_physical: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    same_plane_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    calibrated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    calibration_date: Mapped[date | None] = mapped_column(Date)

    # --- relationships ---
    visit: Mapped["Visit"] = relationship(  # type: ignore[name-defined]
        "Visit", foreign_keys=[visit_id], lazy="selectin"
    )
    image: Mapped["VisitImage"] = relationship(  # type: ignore[name-defined]
        "VisitImage", foreign_keys=[image_id], lazy="selectin"
    )
    calibrator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[calibrated_by], lazy="selectin"
    )
