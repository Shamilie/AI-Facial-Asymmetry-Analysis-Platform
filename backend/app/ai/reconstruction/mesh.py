"""
3D mesh utilities: parametric demo face mesh, OBJ/PLY serialisation and
coverage assessment.

The parametric mesh is a SYNTHETIC DEMO surface (deformed ellipsoid) whose
landmark positions are derived from accepted 2D landmarks. It is not a
validated reconstruction and is always flagged ``RequiresReview`` and
non-metric.
"""

from __future__ import annotations

import math


def parametric_face_mesh(rings: int = 28, segments: int = 40, width: float = 70.0, height: float = 100.0,
                         depth: float = 45.0, asym: float = 0.0) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Front half of a deformed ellipsoid (face-like). x: right(+)/left(-) of image, y: up, z: towards camera."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    for i in range(rings + 1):
        v = -math.pi / 2 + math.pi * i / rings  # bottom → top
        for j in range(segments + 1):
            u = -math.pi / 2 + math.pi * j / segments  # left → right (front half)
            x = width * math.cos(v) * math.sin(u)
            y = height * math.sin(v)
            z = depth * math.cos(v) * math.cos(u)
            # jaw taper + nose bump + optional lower-face asymmetry on image-right (patient-left)
            if y < 0:
                x *= 1 - 0.25 * (-y / height)
                if x > 0:
                    x -= asym * (-y / height)
            nose = 18 * math.exp(-((x / 12) ** 2 + ((y + 5) / 22) ** 2))
            verts.append((round(x, 3), round(y, 3), round(z + nose, 3)))
    cols = segments + 1
    for i in range(rings):
        for j in range(segments):
            a, b = i * cols + j, i * cols + j + 1
            c, d = (i + 1) * cols + j, (i + 1) * cols + j + 1
            faces.append((a, b, d))
            faces.append((a, d, c))
    return verts, faces


def nearest_vertex(verts: list[tuple[float, float, float]], x: float, y: float) -> tuple[float, float, float]:
    """Project an (x, y) frontal position onto the mesh by nearest vertex in the xy-plane (front surface)."""
    best = min(verts, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2 - 1e-3 * p[2])
    return best


def to_obj(verts, faces, header: str = "") -> str:
    lines = [f"# {line}" for line in header.splitlines()]
    lines += [f"v {x} {y} {z}" for x, y, z in verts]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in faces]
    return "\n".join(lines) + "\n"


def to_ply(verts, faces, comment: str = "") -> str:
    head = ["ply", "format ascii 1.0"]
    head += [f"comment {c}" for c in comment.splitlines()]
    head += [f"element vertex {len(verts)}", "property float x", "property float y", "property float z",
             f"element face {len(faces)}", "property list uchar int vertex_indices", "end_header"]
    body = [f"{x} {y} {z}" for x, y, z in verts] + [f"3 {a} {b} {c}" for a, b, c in faces]
    return "\n".join(head + body) + "\n"


def parse_obj(text: str) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    verts, faces = [], []
    for line in text.splitlines():
        if line.startswith("v "):
            _, x, y, z = line.split()[:4]
            verts.append((float(x), float(y), float(z)))
        elif line.startswith("f "):
            idx = [int(p.split("/")[0]) - 1 for p in line.split()[1:4]]
            faces.append((idx[0], idx[1], idx[2]))
    return verts, faces


def coverage_assessment(available_views: set[str], shared_landmarks: int) -> dict:
    required = {"Frontal", "RightLateral", "LeftLateral"}
    missing = sorted(required - available_views)
    if missing:
        status = "Partial" if available_views & required else "Failed"
    else:
        status = "LowConfidence" if shared_landmarks < 6 else "RequiresReview"
    return {"required_views": sorted(required), "available_views": sorted(available_views), "missing_views": missing,
            "shared_landmarks": shared_landmarks, "status": status}
