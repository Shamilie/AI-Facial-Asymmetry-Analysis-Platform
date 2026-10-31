"""
Upload validation and heuristic image quality assessment.

The quality assessment is a *heuristic, uncalibrated* screening aid (blur,
exposure, resolution, face detection/framing). It does not certify clinical
adequacy; examiners accept or reject images manually.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime
from typing import Any

import numpy as np
from PIL import ExifTags, Image, UnidentifiedImageError

from app.core.config import settings

ALLOWED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "TIFF": "image/tiff",
    "BMP": "image/bmp",
    "WEBP": "image/webp",
}
QUALITY_MODEL_NAME = "heuristic-quality-screen"
QUALITY_MODEL_VERSION = "1.0.0"

try:  # OpenCV is optional at import time; used for Laplacian blur + face detection.
    import cv2  # type: ignore

    _HAS_CV2 = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    _HAS_CV2 = False


class ImageValidationError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_upload(data: bytes, filename: str) -> dict[str, Any]:
    """Validate file type (by content, not extension), integrity, size and dimensions."""
    if not data:
        raise ImageValidationError("File is empty")
    if len(data) > settings.max_upload_size_bytes:
        raise ImageValidationError(f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB} MB")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # detects truncated / corrupted files
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ImageValidationError(f"File is not a valid or is a corrupted image: {exc}") from exc
    fmt = (img.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise ImageValidationError(
            f"Unsupported image format '{fmt or 'unknown'}'. Allowed: JPEG, PNG, WEBP, TIFF, BMP"
        )
    w, h = img.size
    if min(w, h) < 64:
        raise ImageValidationError(
            f"Image dimensions {w}×{h}px are too small to process (minimum 64×64px)"
        )
    meta = extract_metadata(img)
    return {"format": fmt, "mime_type": ALLOWED_FORMATS[fmt], "width": int(w), "height": int(h), **meta}


def extract_metadata(img: Image.Image) -> dict[str, Any]:
    from datetime import timezone

    capture_date: datetime | None = None
    device: dict[str, Any] = {}
    try:
        exif = img.getexif()
        if exif:
            tags = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
            try:
                sub = exif.get_ifd(0x8769)
                tags.update({ExifTags.TAGS.get(k, str(k)): v for k, v in sub.items()})
            except Exception:
                pass
            for key in ("Make", "Model", "LensModel", "FocalLength", "ExposureTime", "FNumber", "ISOSpeedRatings", "Software"):
                if key in tags:
                    device[key] = str(tags[key])
            raw_dt = tags.get("DateTimeOriginal") or tags.get("DateTime")
            if raw_dt:
                try:
                    capture_date = datetime.strptime(str(raw_dt).strip("\x00 "), "%Y:%m:%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    pass
    except Exception:
        pass
    if "dpi" in img.info:
        device["dpi"] = str(img.info["dpi"])
    # Synthetic demo images carry their generator metadata in a PNG text chunk.
    if isinstance(getattr(img, "text", None), dict) and img.text.get("fa_synthetic"):
        device["synthetic"] = "SYNTHETIC DEMO IMAGE (fa-synthetic-1.0)"
    return {"capture_date": capture_date, "device_metadata": device or None}


def _gray(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data)).convert("L")
    return np.asarray(img, dtype=np.uint8)


def read_synthetic_meta(data: bytes) -> dict[str, Any] | None:
    """Return embedded synthetic-demo geometry, if this is a generated demo image."""
    import json

    try:
        img = Image.open(io.BytesIO(data))
        raw = getattr(img, "text", {}).get("fa_synthetic")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _to_native(val: Any) -> Any:
    """Recursively convert NumPy scalars/arrays into pure Python JSON-safe types."""
    if isinstance(val, np.generic):
        return val.item()
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, dict):
        return {str(k): _to_native(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_native(v) for v in val]
    return val


def _check(status: str, value: Any, message: str) -> dict[str, Any]:
    return {"status": status, "value": _to_native(value), "message": message}


def assess_quality(data: bytes, image_type: str) -> dict[str, Any]:
    """Return heuristic quality checks. Overall score is intentionally null (uncalibrated)."""
    gray = _gray(data)
    h, w = gray.shape
    issues: list[str] = []
    suggestions: list[str] = []

    # Resolution
    min_side = min(w, h)
    if min_side < settings.MIN_IMAGE_DIMENSION_PX:
        resolution = _check("Fail", f"{w}x{h}", "Resolution below protocol minimum")
    elif min_side < 800:
        resolution = _check("Warning", f"{w}x{h}", "Low resolution; fine landmarks may be hard to identify")
    else:
        resolution = _check("Pass", f"{w}x{h}", "Resolution adequate for screening")

    # Blur — variance of Laplacian
    if _HAS_CV2:
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    else:  # simple finite-difference fallback
        g = gray.astype(np.float64)
        lap = g[1:-1, 1:-1] * -4 + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
        lap_var = float(lap.var())
    blur_thr = 30.0 if image_type == "OPG" else 60.0
    if lap_var < blur_thr * 0.5:
        blur = _check("Fail", round(lap_var, 1), "Image appears blurred")
    elif lap_var < blur_thr:
        blur = _check("Warning", round(lap_var, 1), "Possible mild blur")
    else:
        blur = _check("Pass", round(lap_var, 1), "No significant blur detected")

    # Lighting / exposure
    mean_b = float(gray.mean())
    clipped_hi = float((gray >= 250).mean())
    clipped_lo = float((gray <= 5).mean())
    contrast = float(gray.std())
    if image_type == "OPG":
        lighting_status = "Pass" if contrast > 25 else ("Warning" if contrast > 12 else "Fail")
        lighting = _check(lighting_status, {"mean": round(mean_b, 1), "contrast": round(contrast, 1)}, "Radiographic contrast check")
    else:
        if mean_b < 50 or mean_b > 215 or clipped_hi > 0.25 or clipped_lo > 0.35:
            lighting = _check("Fail", {"mean": round(mean_b, 1), "overexposed": round(clipped_hi, 3), "underexposed": round(clipped_lo, 3)}, "Exposure outside acceptable range")
        elif mean_b < 80 or mean_b > 190 or clipped_hi > 0.08:
            lighting = _check("Warning", {"mean": round(mean_b, 1), "overexposed": round(clipped_hi, 3)}, "Uneven or borderline exposure")
        else:
            lighting = _check("Pass", {"mean": round(mean_b, 1)}, "Exposure acceptable")

    face_visibility = orientation = framing = occlusion = None
    pose: dict[str, Any] | None = None
    missing_regions: list[str] = []
    synthetic = read_synthetic_meta(data)
    if image_type != "OPG" and synthetic and synthetic.get("view") == image_type:
        note = "Synthetic demo image: geometry metadata used instead of the face detector"
        face_visibility = _check("Pass", None, note)
        orientation = _check("Pass", None, note)
        framing = _check("Pass", None, note)
        occlusion = _check("Pass", None, note)
    elif image_type != "OPG":
        face_visibility, orientation, framing, occlusion, pose, missing_regions = _face_checks(gray, image_type)
    else:
        aspect = w / h
        framing = _check("Pass" if 1.6 <= aspect <= 3.2 else "Warning", round(aspect, 2), "Panoramic aspect ratio check")
        orientation = _check("Pass", None, "Orientation assumed standard for OPG")
        face_visibility = _check("Pass", None, "Not applicable to OPG")
        occlusion = _check("Pass", None, "Not assessed for OPG")

    checks = {
        "face_visibility": face_visibility,
        "orientation_check": orientation,
        "lighting_check": lighting,
        "blur_check": blur,
        "occlusion_check": occlusion,
        "framing_check": framing,
        "resolution_check": resolution,
    }
    statuses = [c["status"] for c in checks.values() if c]
    for name, c in checks.items():
        if c and c["status"] != "Pass":
            issues.append(f"{name.replace('_check', '').replace('_', ' ').title()}: {c['message']}")
    for region in missing_regions:
        issues.append(f"Missing anatomical region: {region}")

    if blur["status"] != "Pass":
        suggestions.append("Stabilise the camera (tripod) and refocus on the facial plane before recapturing.")
    if lighting["status"] != "Pass":
        suggestions.append("Use diffuse, even lighting from both sides; avoid flash glare and shadows.")
    if framing and framing["status"] != "Pass":
        suggestions.append("Frame the full face from vertex to below the chin with ears visible, centred in the image.")
    if orientation and orientation["status"] != "Pass":
        suggestions.append("Align head to natural head position (Frankfort horizontal parallel to floor); avoid rotation/tilt.")
    if face_visibility and face_visibility["status"] == "Fail":
        suggestions.append("Ensure the face is fully visible and unobstructed (hair, glasses, hands, dressings).")
    if resolution["status"] != "Pass":
        suggestions.append("Capture at the camera's full resolution (≥ 2000 px on the short side recommended).")

    overall = "Fail" if "Fail" in statuses or missing_regions else ("Warning" if "Warning" in statuses else "Pass")
    return {
        "provider": "Built-in",
        "model_name": QUALITY_MODEL_NAME,
        "model_version": QUALITY_MODEL_VERSION,
        "overall_score": None,  # not calibrated → no numeric score is reported
        "status": overall,
        **checks,
        "pose": pose,
        "issues": issues,
        "suggestions": suggestions,
        "disclaimer": "Heuristic screening only. A Pass result does not establish clinical adequacy; manual acceptance is required.",
    }


def _face_checks(gray: np.ndarray, image_type: str):
    h, w = gray.shape
    if not _HAS_CV2:
        unknown = _check("Warning", None, "Face detector unavailable (OpenCV not installed)")
        return unknown, unknown, unknown, unknown, None, []
    try:
        frontal_xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        profile_xml = cv2.data.haarcascades + "haarcascade_profileface.xml"
        scale = 640.0 / max(h, w)
        small = cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale)))) if scale < 1 else gray
        s = float(scale) if scale < 1 else 1.0
        faces: list = []
        if image_type == "Frontal":
            detected = cv2.CascadeClassifier(frontal_xml).detectMultiScale(small, 1.1, 5, minSize=(40, 40))
            faces = list(detected) if len(detected) else []
        else:
            clf = cv2.CascadeClassifier(profile_xml)
            img_for = small if image_type == "LeftLateral" else cv2.flip(small, 1)
            detected = clf.detectMultiScale(img_for, 1.1, 4, minSize=(40, 40))
            faces = list(detected) if len(detected) else []
            if image_type == "RightLateral" and faces:
                faces = [(int(small.shape[1]) - int(x) - int(fw), int(y), int(fw), int(fh)) for (x, y, fw, fh) in faces]
            if not faces:  # try the other orientation, then frontal cascade as weak fallback
                det2 = clf.detectMultiScale(small, 1.1, 4, minSize=(40, 40))
                faces = list(det2) if len(det2) else []
    except Exception:
        unknown = _check("Warning", None, "Automated face screening skipped for this image")
        return unknown, unknown, unknown, unknown, None, []

    if not faces:
        vis = _check("Warning", 0, "Automated detector did not lock onto a face — verify framing manually")
        unknown = _check("Warning", None, "Manual verification recommended")
        return vis, unknown, unknown, unknown, None, []
    raw_x, raw_y, raw_fw, raw_fh = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    x, y, fw, fh = float(raw_x) / s, float(raw_y) / s, float(raw_fw) / s, float(raw_fh) / s
    cx, cy = float((x + fw / 2.0) / w), float((y + fh / 2.0) / h)
    area_frac = float((fw * fh) / (w * h))
    vis = _check("Pass", int(len(faces)), "Face detected")
    if area_frac < 0.04:
        framing = _check("Warning", round(area_frac, 3), "Face occupies a small portion of the frame")
    elif x < 2 or y < 2 or x + fw > w - 2 or y + fh > h - 2:
        framing = _check("Fail", round(area_frac, 3), "Face touches the image border — anatomical regions may be cut off")
    else:
        framing = _check("Pass", round(area_frac, 3), "Framing acceptable")
    offset = float(abs(cx - 0.5))
    orientation = _check("Pass" if offset < 0.15 else "Warning", round(offset, 3), "Face centring / rotation proxy")
    # Occlusion proxy: lower-face region texture vs upper-face (very rough heuristic).
    upper = gray[max(0, int(y)): max(0, int(y + fh / 2)), max(0, int(x)): max(0, int(x + fw))]
    lower = gray[max(0, int(y + fh / 2)): max(0, int(y + fh)), max(0, int(x)): max(0, int(x + fw))]
    occl_status = "Pass"
    if upper.size and lower.size and abs(float(upper.mean()) - float(lower.mean())) > 70:
        occl_status = "Warning"
    occlusion = _check(occl_status, None, "Heuristic occlusion screen (intensity balance)")
    pose = {"face_center": [round(cx, 3), round(cy, 3)], "face_area_fraction": round(area_frac, 3)}
    return vis, orientation, framing, occlusion, pose, []


def detect_face_bbox(data: bytes, image_type: str) -> tuple[float, float, float, float] | None:
    """Return (x, y, w, h) of the largest detected face in pixel coordinates, if any."""
    if not _HAS_CV2:
        return None
    gray = _gray(data)
    _, _, framing, _, pose, missing = _face_checks(gray, image_type)
    if missing or pose is None:
        return None
    h, w = gray.shape
    cx, cy = pose["face_center"]
    frac = pose["face_area_fraction"]
    side = (frac * w * h) ** 0.5
    return (cx * w - side / 2, cy * h - side / 2, side, side)
