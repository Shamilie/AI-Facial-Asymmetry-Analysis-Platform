"""
Contour helpers used to represent segmentation outputs as polygons.
"""

from __future__ import annotations

import math


def ellipse_polygon(cx: float, cy: float, rx: float, ry: float, n: int = 48) -> list[list[float]]:
    return [[round(cx + rx * math.cos(2 * math.pi * i / n), 2), round(cy + ry * math.sin(2 * math.pi * i / n), 2)] for i in range(n)]


def polygon_from_points(points: list[tuple[float, float]]) -> list[list[float]]:
    return [[round(p[0], 2), round(p[1], 2)] for p in points]


def polygon_area(poly: list[list[float]]) -> float:
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2
