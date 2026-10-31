"""
Database-backed binary object storage model (StoredBlob).

Stores uploaded visit images, processed segmentation overlays, 3D reconstruction
meshes (.obj/.ply), and exported clinical research reports (.pdf/.csv/.xlsx)
directly inside the relational database (PostgreSQL BYTEA / SQLite BLOB) with
SHA-256 content integrity and metadata, eliminating loose filesystem files.
"""

from __future__ import annotations

from sqlalchemy import Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class StoredBlob(TimestampMixin, Base):
    """Binary object persisted directly in the relational database."""

    __tablename__ = "stored_blobs"

    storage_key: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False, default="application/octet-stream")
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
