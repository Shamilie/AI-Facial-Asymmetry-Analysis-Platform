"""
Synthetic demo image generator.

Produces clearly labelled SYNTHETIC frontal, lateral and OPG images with known
geometry so the full workflow can be demonstrated without real patient data.
The exact geometry is embedded in a PNG text chunk (``fa_synthetic``) and is
used ONLY by the clearly-labelled Demo provider.
"""

from __future__ import annotations

import io
import json
import random
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

LABEL = "SYNTHETIC DEMO IMAGE - NOT PATIENT DATA"


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _finish(img: Image.Image, meta: dict[str, Any], noise_sd: float, seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    arr = np.asarray(img).astype(np.float32)
    arr += rng.normal(0, noise_sd, arr.shape)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode=img.mode)
    info = PngImagePlugin.PngInfo()
    info.add_text("fa_synthetic", json.dumps(meta))
    buf = io.BytesIO()
    out.save(buf, format="PNG", pnginfo=info)
    return buf.getvalue()


def _ruler(draw: ImageDraw.ImageDraw, x0: float, y0: float, px_per_mm: float, length_mm: int = 50) -> dict:
    L = length_mm * px_per_mm
    draw.rectangle([x0 - 6, y0 - 22, x0 + L + 6, y0 + 14], fill=(250, 250, 240), outline=(40, 40, 40))
    for mm in range(0, length_mm + 1):
        tick = 12 if mm % 10 == 0 else (8 if mm % 5 == 0 else 4)
        x = x0 + mm * px_per_mm
        draw.line([x, y0, x, y0 - tick], fill=(20, 20, 20), width=1)
    draw.text((x0 + L / 2 - 20, y0 - 2), f"{length_mm} mm", fill=(20, 20, 20), font=_font(12))
    return {"marker_type": "Adhesive scale ruler", "known_length_mm": length_mm, "start": [x0, y0], "end": [x0 + L, y0], "measured_px": L}


def frontal(asym: dict[str, float] | None = None, seed: int = 1, px_per_mm: float = 4.2) -> tuple[bytes, dict]:
    """asym keys (mm, applied to patient-left = image right): GO, CH, ZY, AL, EX, chin."""
    a = {"GO": 0.0, "CH": 0.0, "ZY": 0.0, "AL": 0.0, "EX": 0.0, "chin": 0.0, **(asym or {})}
    W, H = 900, 1150
    cx, ny = W / 2, 400
    img = Image.new("RGB", (W, H), (214, 222, 228))
    d = ImageDraw.Draw(img)

    def P(xmm: float, ymm: float) -> tuple[float, float]:
        return (cx + xmm * px_per_mm, ny + ymm * px_per_mm)

    # Patient right appears on image LEFT (x negative).
    g: dict[str, tuple[float, float]] = {
        "N": P(0, 0), "PRN": P(0, 42), "SN": P(0, 55), "STO": P(a["chin"] * 0.4, 76),
        "PG": P(a["chin"], 118), "ME": P(a["chin"] * 0.9, 129),
        "EX_R": P(-45, 6), "EX_L": P(45 - a["EX"], 6),
        "EN_R": P(-16, 6), "EN_L": P(16, 6),
        "ZY_R": P(-68, 26), "ZY_L": P(68 - a["ZY"], 26),
        "AL_R": P(-17, 50), "AL_L": P(17 - a["AL"], 50),
        "CH_R": P(-25 + a["chin"] * 0.3, 76), "CH_L": P(25 - a["CH"] + a["chin"] * 0.3, 76),
        "GO_R": P(-56, 104), "GO_L": P(56 - a["GO"], 104),
    }
    skin = (226, 190, 160)
    outline = [P(-60, -60), P(-70, -10), g["ZY_R"], P(-64, 70), g["GO_R"], P(-30, 124), g["ME"],
               P(30 + a["chin"], 124), g["GO_L"], P(64 - a["GO"] * 0.5, 70), g["ZY_L"], P(70, -10), P(60, -60), P(0, -85)]
    d.polygon(outline, fill=skin, outline=(150, 110, 90))
    d.ellipse([P(-80, 0)[0] - 10, P(0, 10)[1], P(-80, 0)[0] + 10, P(0, 45)[1]], fill=skin, outline=(150, 110, 90))
    d.ellipse([P(80, 0)[0] - 10, P(0, 10)[1], P(80, 0)[0] + 10, P(0, 45)[1]], fill=skin, outline=(150, 110, 90))
    for s in ("R", "L"):
        ex, en = g[f"EX_{s}"], g[f"EN_{s}"]
        x0, x1 = sorted([ex[0], en[0]])
        d.ellipse([x0, ex[1] - 12, x1, ex[1] + 12], fill=(250, 250, 250), outline=(60, 40, 30), width=2)
        mx = (x0 + x1) / 2
        d.ellipse([mx - 9, ex[1] - 9, mx + 9, ex[1] + 9], fill=(70, 50, 40))
        d.line([x0, ex[1] - 32, x1, ex[1] - 36], fill=(90, 60, 40), width=6)
    d.line([g["N"], g["PRN"]], fill=(170, 125, 100), width=3)
    d.line([g["AL_R"], g["SN"], g["AL_L"]], fill=(150, 105, 85), width=3)
    d.ellipse([g["AL_R"][0] - 6, g["AL_R"][1] - 6, g["AL_R"][0] + 6, g["AL_R"][1] + 6], outline=(140, 95, 80), width=2)
    d.ellipse([g["AL_L"][0] - 6, g["AL_L"][1] - 6, g["AL_L"][0] + 6, g["AL_L"][1] + 6], outline=(140, 95, 80), width=2)
    d.line([g["CH_R"], g["STO"], g["CH_L"]], fill=(170, 70, 70), width=6)
    ruler = _ruler(d, 110, H - 70, px_per_mm)
    d.text((20, 18), LABEL, fill=(160, 30, 30), font=_font(20))
    d.text((20, 44), "Frontal view", fill=(40, 40, 40), font=_font(16))
    meta = {"view": "Frontal", "landmarks": {k: [round(v[0], 2), round(v[1], 2)] for k, v in g.items()},
            "px_per_mm": px_per_mm, "ruler": ruler, "generator": "fa-synthetic-1.0"}
    return _finish(img, meta, 6.0, seed), meta


def lateral(side: str, asym: dict[str, float] | None = None, seed: int = 2, px_per_mm: float = 4.2) -> tuple[bytes, dict]:
    """side='Right' → right lateral (nose points to image right); 'Left' mirrored."""
    a = {"GO": 0.0, "CH": 0.0, "T": 0.0, **(asym or {})}
    W, H = 1000, 1100
    img = Image.new("RGB", (W, H), (214, 222, 228))
    d = ImageDraw.Draw(img)
    sign = 1 if side == "Right" else -1
    tx, ty = W / 2 - sign * 220, 470

    def P(xmm: float, ymm: float) -> tuple[float, float]:
        return (tx + sign * xmm * px_per_mm, ty + ymm * px_per_mm)

    s = "R" if side == "Right" else "L"
    g = {
        f"T_{s}": P(a["T"], 0), "N": P(98, -28), "PRN": P(124, 18), "SN": P(107, 30),
        "PG": P(102, 96), "ME": P(86, 107), f"CH_{s}": P(84 - a["CH"], 52),
        f"EX_{s}": P(74, -20), f"GO_{s}": P(8 + a["GO"] * 0.5, 82 - a["GO"]),
    }
    skin = (226, 190, 160)
    prof = [P(-10, -110), P(60, -100), P(95, -60), g["N"], P(112, -5), g["PRN"], g["SN"], P(110, 45), P(104, 60),
            P(108, 75), g["PG"], g["ME"], P(55, 108), g[f"GO_{s}"], P(-5, 50), P(-25, 0), P(-30, -60)]
    d.polygon(prof, fill=skin, outline=(150, 110, 90))
    t = g[f"T_{s}"]
    d.ellipse([t[0] - 40, t[1] - 70, t[0] + 40, t[1] + 50], fill=(215, 175, 145), outline=(140, 100, 80), width=3)
    d.ellipse([t[0] - 8, t[1] - 8, t[0] + 8, t[1] + 8], fill=(120, 80, 60))
    e = g[f"EX_{s}"]
    d.ellipse([e[0] - 14, e[1] - 8, e[0] + 14, e[1] + 8], fill=(250, 250, 250), outline=(60, 40, 30), width=2)
    c = g[f"CH_{s}"]
    d.line([c, P(108, 52)], fill=(170, 70, 70), width=6)
    ruler = _ruler(d, 120 if sign > 0 else W - 120 - 50 * px_per_mm, H - 70, px_per_mm)
    d.text((20, 18), LABEL, fill=(160, 30, 30), font=_font(20))
    d.text((20, 44), f"{side} lateral view", fill=(40, 40, 40), font=_font(16))
    view = "RightLateral" if side == "Right" else "LeftLateral"
    meta = {"view": view, "landmarks": {k: [round(v[0], 2), round(v[1], 2)] for k, v in g.items()},
            "px_per_mm": px_per_mm, "ruler": ruler, "generator": "fa-synthetic-1.0"}
    return _finish(img, meta, 6.0, seed), meta


def opg(asym: dict[str, float] | None = None, seed: int = 3, px_per_mm: float = 5.0) -> tuple[bytes, dict]:
    """asym keys (mm, patient-left = image right in this rendering): ramus, body."""
    a = {"ramus": 0.0, "body": 0.0, **(asym or {})}
    W, H = 1600, 800
    img = Image.new("L", (W, H), 28)
    d = ImageDraw.Draw(img)
    cx = W / 2

    def P(xmm: float, ymm: float) -> tuple[float, float]:
        return (cx + xmm * px_per_mm, 60 + ymm * px_per_mm)

    g = {
        "OPG_CO_R": P(-112, 22), "OPG_CO_L": P(112, 22 + a["ramus"]),
        "OPG_CR_R": P(-84, 30), "OPG_CR_L": P(84, 30 + a["ramus"] * 0.5),
        "OPG_GO_R": P(-108, 88), "OPG_GO_L": P(108 - a["body"], 88),
        "OPG_AG_R": P(-90, 104), "OPG_AG_L": P(90 - a["body"], 104),
        "OPG_ME": P(0, 126),
    }
    for s in ("R", "L"):
        sg = -1 if s == "R" else 1
        ramus = [g[f"OPG_CO_{s}"], P(sg * 100, 50), g[f"OPG_GO_{s}"]]
        d.line(ramus, fill=205, width=26, joint="curve")
        d.line([g[f"OPG_CR_{s}"], P(sg * 92, 60)], fill=185, width=16)
        body = [g[f"OPG_GO_{s}"], g[f"OPG_AG_{s}"], P(sg * 60, 116), P(sg * 25, 124), g["OPG_ME"]]
        d.line(body, fill=210, width=30, joint="curve")
        d.ellipse([g[f"OPG_CO_{s}"][0] - 22, g[f"OPG_CO_{s}"][1] - 18, g[f"OPG_CO_{s}"][0] + 22, g[f"OPG_CO_{s}"][1] + 18], fill=215)
    for i in range(16):
        x = -75 + i * 10
        ux, uy = P(x, 60)
        d.rectangle([ux - 18, uy - 70, ux + 18, uy - 4], fill=235)  # upper teeth
        d.rectangle([ux - 18, uy + 4, ux + 18, uy + 70], fill=230)  # lower teeth
    rng = random.Random(seed)
    for _ in range(40):
        x, y = rng.randint(0, W), rng.randint(0, H)
        d.ellipse([x - 30, y - 30, x + 30, y + 30], fill=rng.randint(30, 60))
    d.text((20, 18), LABEL, fill=255, font=_font(22))
    d.text((20, 46), "Orthopantomogram (synthetic)", fill=200, font=_font(16))
    meta = {"view": "OPG", "landmarks": {k: [round(v[0], 2), round(v[1], 2)] for k, v in g.items()},
            "px_per_mm": px_per_mm, "pixel_spacing_mm": round(1 / px_per_mm * 1.25, 4),
            "magnification_factor": 1.25, "generator": "fa-synthetic-1.0"}
    return _finish(img, meta, 5.0, seed), meta


def visit_asymmetry(fracture_side: str, visit_index: int, severity: float = 1.0) -> dict[str, dict[str, float]]:
    """Synthetic asymmetry that decreases over follow-up (index 0 = pre-op)."""
    decay = [1.0, 0.75, 0.5, 0.3, 0.2][min(visit_index, 4)] * severity
    s = 1 if fracture_side == "Left" else -1
    return {
        "frontal": {"GO": 6 * decay * s, "CH": 3 * decay * s, "ZY": 1.5 * decay * s, "AL": 0.8 * decay * s, "EX": 0.5 * decay * s, "chin": 4 * decay * s},
        "right": {"GO": (5 * decay if fracture_side == "Right" else 0), "CH": (2 * decay if fracture_side == "Right" else 0)},
        "left": {"GO": (5 * decay if fracture_side == "Left" else 0), "CH": (2 * decay if fracture_side == "Left" else 0)},
        "opg": {"ramus": 4 * decay * (1 if fracture_side == "Left" else -1), "body": 3 * decay * (1 if fracture_side == "Left" else -1)},
    }
