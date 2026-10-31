"""
Consistent API response envelope helpers.

Success:  {"success": true,  "data": ..., "message": null, "meta": {...}}
Error:    {"success": false, "error": {"code": "...", "message": "...", "details": ...}}
"""

from __future__ import annotations

import enum
import math
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException


def ok(data: Any = None, message: str | None = None, meta: dict | None = None) -> dict:
    return {"success": True, "data": to_jsonable(data), "message": message, "meta": meta}


def paginated(items: list, total: int, page: int, page_size: int) -> dict:
    return ok(
        items,
        meta={
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)) if page_size else 1,
        },
    )


def not_found(what: str = "Resource") -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


def bad_request(msg: str) -> HTTPException:
    return HTTPException(status_code=400, detail=msg)


def conflict(msg: str) -> HTTPException:
    return HTTPException(status_code=409, detail=msg)


def to_jsonable(value: Any) -> Any:
    """Recursively convert UUIDs, enums, dates and ORM-friendly values to JSON types."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump())
    return str(value)


def row_to_dict(obj: Any, exclude: set[str] | None = None) -> dict:
    """Serialize a SQLAlchemy model's column attributes (no relationships)."""
    exclude = exclude or set()
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        key = col.key
        attr = key
        # handle python attribute names that differ from column names
        for prop in obj.__mapper__.column_attrs:
            if prop.columns[0] is col:
                attr = prop.key
                break
        if attr in exclude:
            continue
        out[attr.rstrip("_")] = to_jsonable(getattr(obj, attr))
    return out
