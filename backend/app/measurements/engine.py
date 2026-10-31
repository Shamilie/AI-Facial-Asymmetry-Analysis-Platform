"""
Validated geometric measurement engine.

AI models predict landmarks; this deterministic engine computes numerical
measurements from *accepted* inputs only. It never invents coordinates or values.

Rules enforced here (see docs/measurement-methodology.md):
  * View-specific calibration — each side is scaled with the calibration of the
    view it was measured in.
  * Display/PPI assumptions (e.g. 1 mm = 3.78 px) are NOT physical calibration; a
    view with no physical calibration yields ``Unscaled`` (no mm value).
  * Missing / not-identifiable / out-of-range landmarks yield no value for that side.
  * Asymmetry Index (%) = |R − L| / (R + L) × 100, only when both sides are valid
    and the denominator is positive, and only if the definition allows it.
  * OPG pixel spacing alone does not correct panoramic distortion → warning.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Any

LINEAR_KINDS = {"midline_distance", "distance", "geodesic"}


@dataclass
class LandmarkPoint:
    code: str
    x: float | None
    y: float | None
    z: float | None = None
    status: str = "Predicted"  # Predicted | Reviewed | Approved | NotIdentifiable | Rejected
    prediction_id: str | None = None
    source: str = "AI"

    @property
    def usable(self) -> bool:
        return self.status not in ("NotIdentifiable", "Rejected") and self.x is not None and self.y is not None


@dataclass
class CalibrationInfo:
    mm_per_pixel: float | None
    is_physical: bool = True
    same_plane_confirmed: bool = False
    calibration_id: str | None = None
    calibration_type: str | None = None
    method: str | None = None
    horizontal_mm_per_px: float | None = None  # OPG directional calibration
    vertical_mm_per_px: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return bool(self.is_physical and self.mm_per_pixel and self.mm_per_pixel > 0 and math.isfinite(self.mm_per_pixel))


@dataclass
class ViewData:
    landmarks: dict[str, LandmarkPoint]
    width: int | None = None
    height: int | None = None
    calibration: CalibrationInfo | None = None


@dataclass
class MeshData:
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    landmarks: dict[str, tuple[float, float, float]]
    is_metric: bool = False  # True only for a scaled & validated reconstruction
    status: str = "RequiresReview"


@dataclass
class SideResult:
    value: float | None = None
    pixel_value: float | None = None
    status: str = "ok"  # ok | missing | not_identifiable | out_of_range | unscaled | invalid
    warnings: list[str] = field(default_factory=list)
    landmarks: list[str] = field(default_factory=list)
    calibration_id: str | None = None


@dataclass
class MeasurementResult:
    code: str
    right: SideResult
    left: SideResult
    absolute_difference: float | None
    asymmetry_index: float | None
    unit: str
    status: str
    is_unscaled: bool
    warnings: list[str]

    def landmark_refs(self) -> dict[str, Any]:
        return {
            "right": self.right.landmarks,
            "left": self.left.landmarks,
            "right_status": self.right.status,
            "left_status": self.left.status,
            "pixel_values": {"right": self.right.pixel_value, "left": self.left.pixel_value},
            "calibration_ids": {"right": self.right.calibration_id, "left": self.left.calibration_id},
        }


# ---------------------------------------------------------------------------
# Primitive geometry
# ---------------------------------------------------------------------------


def euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def point_to_line_distance(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """Perpendicular distance from p to the infinite line through a and b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("Midline landmarks are coincident; midline is undefined")
    return abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / length


def angle_at_vertex(a: tuple[float, float], v: tuple[float, float], b: tuple[float, float]) -> float:
    v1 = (a[0] - v[0], a[1] - v[1])
    v2 = (b[0] - v[0], b[1] - v[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        raise ValueError("Angle undefined: coincident landmarks")
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def asymmetry_index(right: float | None, left: float | None) -> tuple[float | None, str | None]:
    """Return (AI%, warning). AI% = |R-L| / (R+L) * 100."""
    if right is None or left is None:
        return None, "Asymmetry index not computed: one or both sides missing"
    if not (math.isfinite(right) and math.isfinite(left)):
        return None, "Asymmetry index not computed: non-finite value"
    if right < 0 or left < 0:
        return None, "Asymmetry index not computed: negative values are not valid for this index"
    denom = right + left
    if denom <= 0:
        return None, "Asymmetry index not computed: zero denominator (R + L = 0)"
    return abs(right - left) / denom * 100.0, None


def mesh_geodesic(mesh: MeshData, start: tuple[float, float, float], end: tuple[float, float, float]) -> float:
    """Approximate surface geodesic via Dijkstra over mesh edges between nearest vertices."""
    verts = mesh.vertices
    if not verts:
        raise ValueError("Empty mesh")

    def nearest(p: tuple[float, float, float]) -> int:
        return min(range(len(verts)), key=lambda i: (verts[i][0] - p[0]) ** 2 + (verts[i][1] - p[1]) ** 2 + (verts[i][2] - p[2]) ** 2)

    adj: dict[int, dict[int, float]] = {}
    for f in mesh.faces:
        for i, j in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            d = math.dist(verts[i], verts[j])
            adj.setdefault(i, {})[j] = d
            adj.setdefault(j, {})[i] = d
    s, t = nearest(start), nearest(end)
    dist = {s: 0.0}
    pq = [(0.0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t:
            return d
        if d > dist.get(u, math.inf):
            continue
        for v, w in adj.get(u, {}).items():
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    raise ValueError("No surface path between landmarks (disconnected mesh)")


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class MeasurementEngine:
    def __init__(self, views: dict[str, ViewData], mesh: MeshData | None = None) -> None:
        self.views = views
        self.mesh = mesh

    # -- landmark access -------------------------------------------------------
    def _get_points(self, view: str, codes: list[str], side: SideResult) -> list[tuple[float, float]] | None:
        vd = self.views.get(view)
        if vd is None:
            side.status = "missing"
            side.warnings.append(f"No accepted {view} image/landmarks available")
            return None
        pts: list[tuple[float, float]] = []
        for code in codes:
            lm = vd.landmarks.get(code)
            side.landmarks.append(f"{view}:{code}")
            if lm is None:
                side.status = "missing"
                side.warnings.append(f"Landmark {code} missing in {view}")
                return None
            if lm.status in ("NotIdentifiable", "Rejected") or lm.x is None or lm.y is None:
                side.status = "not_identifiable"
                side.warnings.append(f"Landmark {code} not identifiable in {view}")
                return None
            if vd.width and vd.height and not (0 <= lm.x <= vd.width and 0 <= lm.y <= vd.height):
                side.status = "out_of_range"
                side.warnings.append(f"Landmark {code} coordinates out of image bounds in {view}")
                return None
            pts.append((lm.x, lm.y))
        return pts

    def _scale(self, view: str, px_value: float, side: SideResult, dxdy: tuple[float, float] | None = None) -> float | None:
        vd = self.views[view]
        cal = vd.calibration
        side.pixel_value = px_value
        if cal is None or not cal.valid:
            side.status = "unscaled"
            if cal is not None and not cal.is_physical:
                side.warnings.append(
                    f"{view}: only a display/PPI assumption is configured; this is not physical calibration — value left unscaled"
                )
            else:
                side.warnings.append(f"{view}: no valid view-specific calibration — value left unscaled")
            return None
        side.calibration_id = cal.calibration_id
        side.warnings.extend(cal.warnings)
        if not cal.same_plane_confirmed:
            side.warnings.append(f"{view}: calibration marker plane not confirmed to match the measured anatomical plane")
        if view == "OPG" and dxdy and cal.horizontal_mm_per_px and cal.vertical_mm_per_px:
            dx, dy = dxdy
            return math.hypot(dx * cal.horizontal_mm_per_px, dy * cal.vertical_mm_per_px)
        return px_value * float(cal.mm_per_pixel)  # type: ignore[arg-type]

    # -- per kind --------------------------------------------------------------
    def _side(self, spec: dict, side_key: str) -> SideResult:
        side = SideResult()
        kind = spec["kind"]
        try:
            if kind == "midline_distance":
                view = spec["view"]
                pts = self._get_points(view, [spec["midline"][0], spec["midline"][1], spec[side_key]], side)
                if pts is None:
                    return side
                px = point_to_line_distance(pts[2], pts[0], pts[1])
                side.value = self._scale(view, px, side)
            elif kind == "distance":
                view = spec[f"view_{side_key}"]
                pts = self._get_points(view, spec[side_key], side)
                if pts is None:
                    return side
                px = euclidean(pts[0], pts[1])
                side.value = self._scale(view, px, side, (abs(pts[1][0] - pts[0][0]), abs(pts[1][1] - pts[0][1])))
            elif kind == "angle":
                view = spec[f"view_{side_key}"]
                pts = self._get_points(view, spec[side_key], side)
                if pts is None:
                    return side
                side.value = angle_at_vertex(pts[0], pts[1], pts[2])
                if view == "OPG":
                    side.warnings.append("OPG angular values may be affected by panoramic projection distortion")
            elif kind == "geodesic":
                self._geodesic_side(spec, side_key, side)
            else:
                side.status = "invalid"
                side.warnings.append(f"Unsupported measurement kind: {kind}")
        except ValueError as exc:
            side.status = "invalid"
            side.value = None
            side.warnings.append(str(exc))
        if side.value is not None and side.status == "ok" and (not math.isfinite(side.value)):
            side.status = "invalid"
            side.value = None
        return side

    def _geodesic_side(self, spec: dict, side_key: str, side: SideResult) -> None:
        codes = spec[side_key]
        side.landmarks = [f"Mesh3D:{c}" for c in codes]
        mesh = self.mesh
        if mesh is None:
            side.status = "missing"
            side.warnings.append("No 3D reconstruction available")
            return
        if mesh.status in ("Failed", "Partial"):
            side.status = "invalid"
            side.warnings.append(f"3D reconstruction status is {mesh.status}; geodesic not computed")
            return
        missing = [c for c in codes if c not in mesh.landmarks]
        if missing:
            side.status = "not_identifiable"
            side.warnings.append(f"3D landmarks unavailable: {', '.join(missing)}")
            return
        length = mesh_geodesic(mesh, mesh.landmarks[codes[0]], mesh.landmarks[codes[1]])
        side.pixel_value = length
        side.warnings.append(
            "Surface geodesic approximates a flexible tape measurement; not validated against paired physical measurements"
        )
        if not mesh.is_metric:
            side.status = "unscaled"
            side.warnings.append("Mesh is not metrically scaled/validated — value reported in mesh units only")
            return
        side.value = length

    # -- public ----------------------------------------------------------------
    def compute(self, code: str, spec: dict, unit: str) -> MeasurementResult:
        right = self._side(spec, "right")
        left = self._side(spec, "left")
        warnings = [*right.warnings, *left.warnings]
        abs_diff = abs(right.value - left.value) if right.value is not None and left.value is not None else None
        ai = None
        if spec.get("asymmetry_index", False):
            ai, w = asymmetry_index(right.value, left.value)
            if w and (right.value is not None or left.value is not None):
                warnings.append(w)
            elif w and right.value is None and left.value is None:
                pass
        statuses = {right.status, left.status}
        is_unscaled = "unscaled" in statuses
        if right.value is not None and left.value is not None:
            status = "ReviewRequired" if warnings else "Calculated"
        elif statuses <= {"unscaled", "ok"} and is_unscaled:
            status = "Unscaled"
        elif "not_identifiable" in statuses:
            status = "NotIdentifiable"
        elif "invalid" in statuses or "out_of_range" in statuses:
            status = "Invalid"
        elif is_unscaled:
            status = "Unscaled"
        else:
            status = "MissingData"
        return MeasurementResult(
            code=code, right=right, left=left, absolute_difference=abs_diff, asymmetry_index=ai,
            unit=unit, status=status, is_unscaled=is_unscaled, warnings=list(dict.fromkeys(warnings)),
        )


def calibration_mm_per_pixel(known_mm: float, measured_px: float) -> float:
    """mm per pixel = known marker length (mm) / measured marker length (px)."""
    if known_mm is None or measured_px is None:
        raise ValueError("Known marker length and measured pixel length are required")
    if known_mm <= 0 or measured_px <= 0:
        raise ValueError("Marker lengths must be positive")
    return known_mm / measured_px
