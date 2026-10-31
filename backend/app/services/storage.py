"""
Database-first binary object storage abstraction.

Storage Backends:
  * ``DatabaseStorage`` (default, ``STORAGE_BACKEND="database"``) — persists all
    uploaded images, processed masks, 3D reconstruction meshes (.obj/.ply), and
    exported reports (.pdf/.csv/.xlsx) directly inside the relational database
    (``stored_blobs`` table, PostgreSQL ``BYTEA`` / SQLite ``BLOB``) with SHA-256
    checksums and single-transaction ACID consistency.
  * ``S3Storage`` (``STORAGE_BACKEND="s3"``) — S3-compatible object storage for
    multi-node cloud deployments.
  * ``LocalStorage`` (``STORAGE_BACKEND="local"``) — legacy filesystem storage.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_current_db_session, sync_session_factory
from app.models.blob import StoredBlob

CATEGORIES = {"originals", "processed", "meshes", "reports", "samples"}

MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    "obj": "model/obj",
    "ply": "application/octet-stream",
    "pdf": "application/pdf",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
}

# Write-through LRU cache (bounded to 256 objects) so reads within an uncommitted
# transaction or repeated image/mesh views are served in O(1) without extra I/O.
_MEM_CACHE: OrderedDict[str, bytes] = OrderedDict()
_MAX_CACHE_ITEMS = 256


def _cache_put(key: str, data: bytes) -> None:
    _MEM_CACHE[key] = data
    _MEM_CACHE.move_to_end(key)
    while len(_MEM_CACHE) > _MAX_CACHE_ITEMS:
        _MEM_CACHE.popitem(last=False)


def _cache_get(key: str) -> bytes | None:
    val = _MEM_CACHE.get(key)
    if val is not None:
        _MEM_CACHE.move_to_end(key)
    return val


class StorageBackend(Protocol):
    def save(self, category: str, data: bytes, extension: str, subdir: str = "") -> str: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def local_path(self, key: str) -> Path | None: ...


def _make_key(category: str, extension: str, subdir: str = "") -> str:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown storage category: {category}")
    ext = extension.lower().lstrip(".")
    parts = [category]
    if subdir:
        parts.append(subdir.strip("/\\"))
    parts.append(f"{uuid.uuid4().hex}.{ext}")
    return "/".join(parts)


class DatabaseStorage:
    """Stores all binary assets (images, 3D meshes, reports) directly in the
    relational database ``stored_blobs`` table instead of loose filesystem files.
    """

    def __init__(self, legacy_fallback_root: Path | None = None) -> None:
        self.legacy_root = legacy_fallback_root

    def save(self, category: str, data: bytes, extension: str, subdir: str = "") -> str:
        key = _make_key(category, extension, subdir)
        ext = extension.lower().lstrip(".")
        mime = MIME_BY_EXT.get(ext, "application/octet-stream")
        sha256 = hashlib.sha256(data).hexdigest()

        _cache_put(key, data)

        blob = StoredBlob(
            storage_key=key,
            category=category,
            extension=ext,
            mime_type=mime,
            byte_size=len(data),
            sha256_hash=sha256,
            content=data,
        )

        active_session = get_current_db_session()
        if active_session is not None:
            # Participate in the caller's active AsyncSession transaction (atomic ACID commit)
            active_session.add(blob)
        elif sync_session_factory is not None:
            with sync_session_factory() as session:
                session.add(blob)
                session.commit()

        return key

    def read(self, key: str) -> bytes:
        cached = _cache_get(key)
        if cached is not None:
            return cached

        if sync_session_factory is not None:
            with sync_session_factory() as session:
                row = session.execute(
                    select(StoredBlob.content).where(StoredBlob.storage_key == key)
                ).scalar_one_or_none()
                if row is not None:
                    data = bytes(row)
                    _cache_put(key, data)
                    return data

        # Transparent fallback + auto-migration for any pre-existing legacy file on disk
        if self.legacy_root is not None:
            legacy_file = (self.legacy_root / key).resolve()
            if self.legacy_root.resolve() in legacy_file.parents and legacy_file.exists():
                data = legacy_file.read_bytes()
                _cache_put(key, data)
                ext = legacy_file.suffix.lower().lstrip(".") or "bin"
                cat = key.split("/", 1)[0] if "/" in key else "originals"
                blob = StoredBlob(
                    storage_key=key,
                    category=cat if cat in CATEGORIES else "originals",
                    extension=ext,
                    mime_type=MIME_BY_EXT.get(ext, "application/octet-stream"),
                    byte_size=len(data),
                    sha256_hash=hashlib.sha256(data).hexdigest(),
                    content=data,
                )
                active_session = get_current_db_session()
                if active_session is not None:
                    active_session.add(blob)
                return data

        raise FileNotFoundError(f"Binary object not found in database stored_blobs: {key}")

    def delete(self, key: str) -> None:
        _MEM_CACHE.pop(key, None)
        active_session = get_current_db_session()
        if active_session is None and sync_session_factory is not None:
            with sync_session_factory() as session:
                session.execute(delete(StoredBlob).where(StoredBlob.storage_key == key))
                session.commit()

    def exists(self, key: str) -> bool:
        if key in _MEM_CACHE:
            return True
        if sync_session_factory is not None:
            with sync_session_factory() as session:
                found = session.execute(
                    select(StoredBlob.id).where(StoredBlob.storage_key == key)
                ).scalar_one_or_none()
                return found is not None
        return False

    def local_path(self, key: str) -> Path | None:
        return None


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def save(self, category: str, data: bytes, extension: str, subdir: str = "") -> str:
        key = _make_key(category, extension, subdir)
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        p = self._resolve(key)
        if p.exists():
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def local_path(self, key: str) -> Path | None:
        return self._resolve(key)


class S3Storage:  # pragma: no cover - requires S3 endpoint
    def __init__(self) -> None:
        import boto3

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )

    def save(self, category: str, data: bytes, extension: str, subdir: str = "") -> str:
        key = _make_key(category, extension, subdir)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")
        return key

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def local_path(self, key: str) -> Path | None:
        return None


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        backend_mode = (settings.STORAGE_BACKEND or "database").lower()
        if backend_mode == "s3":
            _storage = S3Storage()
        elif backend_mode == "local":
            _storage = LocalStorage(settings.upload_path)
        else:
            legacy_dir = Path(settings.UPLOAD_DIR).resolve() if settings.UPLOAD_DIR else None
            _storage = DatabaseStorage(legacy_fallback_root=legacy_dir)
    return _storage


async def migrate_files_to_database(db: AsyncSession) -> dict[str, int]:
    """Ensure all existing VisitImage, ReconstructionAsset, and ReportExport records
    have their binary payloads stored inside ``stored_blobs`` in the database.
    """
    from app.models.image import VisitImage
    from app.models.reconstruction import ReconstructionAsset
    from app.models.report import ReportExport

    existing_keys = set(
        (await db.execute(select(StoredBlob.storage_key))).scalars().all()
    )
    legacy_root = Path(settings.UPLOAD_DIR).resolve() if settings.UPLOAD_DIR else None
    migrated = 0

    def _ingest_if_missing(key: str | None, default_cat: str, default_ext: str) -> None:
        nonlocal migrated
        if not key or key in existing_keys:
            return
        if legacy_root is not None:
            candidate = (legacy_root / key).resolve()
            if legacy_root in candidate.parents and candidate.exists():
                raw = candidate.read_bytes()
                ext = candidate.suffix.lower().lstrip(".") or default_ext
                db.add(
                    StoredBlob(
                        storage_key=key,
                        category=default_cat,
                        extension=ext,
                        mime_type=MIME_BY_EXT.get(ext, "application/octet-stream"),
                        byte_size=len(raw),
                        sha256_hash=hashlib.sha256(raw).hexdigest(),
                        content=raw,
                    )
                )
                _cache_put(key, raw)
                existing_keys.add(key)
                migrated += 1

    for (img_path,) in (await db.execute(select(VisitImage.stored_path))).all():
        _ingest_if_missing(img_path, "originals", "png")

    for (mesh_path,) in (await db.execute(select(ReconstructionAsset.file_path))).all():
        _ingest_if_missing(mesh_path, "meshes", "obj")

    for (rep_path,) in (await db.execute(select(ReportExport.file_path))).all():
        _ingest_if_missing(rep_path, "reports", "pdf")

    if migrated > 0:
        await db.commit()

    # Warm the write-through cache with stored_blobs from the async database session
    rows = (await db.execute(select(StoredBlob.storage_key, StoredBlob.content))).all()
    for s_key, s_content in rows:
        if s_key and s_content is not None:
            _cache_put(s_key, bytes(s_content))

    return {"migrated_blobs": migrated, "total_blobs": len(existing_keys)}


async def get_database_storage_stats(db: AsyncSession) -> dict[str, Any]:
    """Return telemetry on binary blobs stored inside the relational database."""
    rows = (
        await db.execute(
            select(
                StoredBlob.category,
                func.count(StoredBlob.id),
                func.coalesce(func.sum(StoredBlob.byte_size), 0),
            ).group_by(StoredBlob.category)
        )
    ).all()
    by_category = {
        cat: {"count": int(cnt), "bytes": int(total_b), "kilobytes": round(int(total_b) / 1024, 1)}
        for cat, cnt, total_b in rows
    }
    total_count = sum(v["count"] for v in by_category.values())
    total_bytes = sum(v["bytes"] for v in by_category.values())
    return {
        "storage_backend": "database",
        "table": "stored_blobs",
        "total_blobs": total_count,
        "total_bytes": total_bytes,
        "total_megabytes": round(total_bytes / (1024 * 1024), 2),
        "by_category": by_category,
    }
