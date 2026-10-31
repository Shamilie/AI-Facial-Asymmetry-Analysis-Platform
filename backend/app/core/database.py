"""
Async & sync SQLAlchemy engines, session factories, declarative base, and transaction context.

Supports:
  * PostgreSQL 16 (production / Docker / local service) with auto-detection
  * Local Relational DB with WAL journaling, foreign-key enforcement, and 64 MB page cache
  * Context-bound session tracking so DatabaseStorage (stored_blobs) commits atomically
    within the active request/pipeline transaction.
"""

from __future__ import annotations

import importlib.util
import socket
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, create_engine, event, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from app.core.config import settings

# Context variable tracking the active AsyncSession in the current coroutine task
_current_db_session: ContextVar[AsyncSession | None] = ContextVar(
    "_current_db_session", default=None
)


def get_current_db_session() -> AsyncSession | None:
    """Return the active AsyncSession for the current async context, if any."""
    return _current_db_session.get()


def set_current_db_session(session: AsyncSession | None):
    """Bind or clear the active AsyncSession for the current async context."""
    return _current_db_session.set(session)


@compiles(PG_UUID, "sqlite")
def _compile_pg_uuid_sqlite(type_: object, compiler: object, **kw: object) -> str:
    """Allow PostgreSQL UUID column definitions to compile cleanly on SQLite."""
    return "CHAR(36)"


def _is_tcp_port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _has_module(mod_name: str) -> bool:
    return importlib.util.find_spec(mod_name) is not None


def _normalize_pg_urls(async_url: str, sync_url: str) -> tuple[str, str | None, bool]:
    """Normalize PostgreSQL async and sync URLs based on installed Python drivers.

    Returns ``(normalized_async_url, normalized_sync_url_or_none, can_connect_async)``.
    """
    rest = async_url.split("://", 1)[1] if "://" in async_url else async_url
    sync_rest = sync_url.split("://", 1)[1] if "://" in sync_url else rest

    # Choose best installed async driver
    if _has_module("asyncpg"):
        norm_async = f"postgresql+asyncpg://{rest}"
        can_async = True
    elif _has_module("psycopg"):
        norm_async = f"postgresql+psycopg://{rest}"
        can_async = True
    else:
        norm_async = async_url
        can_async = False

    # Choose best installed sync driver (optional; async engine handles primary workload)
    if _has_module("psycopg"):
        norm_sync: str | None = f"postgresql+psycopg://{sync_rest}"
    elif _has_module("psycopg2"):
        norm_sync = f"postgresql+psycopg2://{sync_rest}"
    elif _has_module("pg8000"):
        norm_sync = f"postgresql+pg8000://{sync_rest}"
    else:
        norm_sync = None

    return norm_async, norm_sync, can_async


def _resolve_database_urls() -> tuple[str, str | None, str]:
    """Resolve (async_url, sync_url_or_none, engine_label).

    If PostgreSQL is configured and reachable (and an async PG driver is installed),
    connects to PostgreSQL; otherwise uses the WAL-mode relational database.
    """
    async_url = settings.DATABASE_URL
    sync_url = settings.DATABASE_URL_SYNC

    if async_url.startswith("postgresql"):
        host = "localhost"
        port = 5432
        try:
            after_at = async_url.split("@", 1)[1]
            host_port = after_at.split("/", 1)[0]
            if ":" in host_port:
                host, port_s = host_port.split(":", 1)
                port = int(port_s)
            else:
                host = host_port
        except Exception:
            pass

        norm_async, norm_sync, can_async = _normalize_pg_urls(async_url, sync_url)
        if can_async and _is_tcp_port_open(host, port):
            return norm_async, norm_sync, f"PostgreSQL ({host}:{port})"

        fallback_async = "sqlite+aiosqlite:///./facial_asymmetry.db"
        fallback_sync = "sqlite:///./facial_asymmetry.db"
        return fallback_async, fallback_sync, "Relational Database (WAL + Foreign Keys Enforced)"

    return async_url, sync_url, "Relational Database (WAL + Foreign Keys Enforced)"


ACTIVE_DATABASE_URL, ACTIVE_DATABASE_URL_SYNC, ACTIVE_DATABASE_LABEL = _resolve_database_urls()

_async_engine_kwargs: dict[str, Any] = {
    "echo": False,
    "future": True,
}
_sync_engine_kwargs: dict[str, Any] = {
    "echo": False,
    "future": True,
}

if ACTIVE_DATABASE_URL.startswith("postgresql"):
    _async_engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        }
    )
    _sync_engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 10,
        }
    )
else:
    _async_engine_kwargs["connect_args"] = {"timeout": 30}
    _sync_engine_kwargs["connect_args"] = {"timeout": 30, "check_same_thread": False}

engine = create_async_engine(ACTIVE_DATABASE_URL, **_async_engine_kwargs)

sync_engine = (
    create_engine(ACTIVE_DATABASE_URL_SYNC, **_sync_engine_kwargs)
    if ACTIVE_DATABASE_URL_SYNC is not None
    else None
)


def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enforce WAL mode, foreign keys, and 64MB page cache on SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=30000;")
    cursor.execute("PRAGMA cache_size=-64000;")
    cursor.close()


if ACTIVE_DATABASE_URL.startswith("sqlite"):
    event.listen(engine.sync_engine, "connect", _configure_sqlite_connection)
    if sync_engine is not None:
        event.listen(sync_engine, "connect", _configure_sqlite_connection)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_session_factory = (
    sessionmaker(
        bind=sync_engine,
        class_=Session,
        expire_on_commit=False,
    )
    if sync_engine is not None
    else None
)


@asynccontextmanager
async def managed_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Open an AsyncSession and bind it to the current task context so DatabaseStorage
    participates in the same atomic transaction."""
    async with async_session_factory() as session:
        token = set_current_db_session(session)
        try:
            yield session
        finally:
            _current_db_session.reset(token)


# ---------------------------------------------------------------------------
# Declarative base with UUID primary-key mixin baked in
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Project-wide declarative base.

    Every model that inherits from :class:`Base` automatically receives a
    ``id`` column of type ``UUID`` with a default uuid4 generator.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Timestamp mixin
# ---------------------------------------------------------------------------


class TimestampMixin:
    """Mixin that adds ``created_at`` and ``updated_at`` audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` bound to context that is automatically committed and closed."""
    async with async_session_factory() as session:
        token = set_current_db_session(session)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            _current_db_session.reset(token)
            await session.close()
