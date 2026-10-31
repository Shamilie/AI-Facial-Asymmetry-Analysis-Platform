"""
Research reliability statistics with explicit sample-size guards.

Functions return ``{"sufficient": False, "reason": ...}`` instead of producing
misleading numbers when the data are insufficient.
"""

from __future__ import annotations

import math
from statistics import mean, stdev

MIN_N_ICC = 10
MIN_N_BLAND_ALTMAN = 10
MIN_N_CV = 3


def _clean_pairs(a: list[float | None], b: list[float | None]) -> list[tuple[float, float]]:
    return [(x, y) for x, y in zip(a, b) if x is not None and y is not None and math.isfinite(x) and math.isfinite(y)]


def icc_2_1(a: list[float | None], b: list[float | None]) -> dict:
    """ICC(2,1): two-way random effects, absolute agreement, single rater (Shrout & Fleiss)."""
    pairs = _clean_pairs(a, b)
    n, k = len(pairs), 2
    missing = len(a) - n
    if n < MIN_N_ICC:
        return {"sufficient": False, "n": n, "missing": missing, "reason": f"ICC requires at least {MIN_N_ICC} complete pairs"}
    grand = mean([v for p in pairs for v in p])
    row_means = [(x + y) / 2 for x, y in pairs]
    col_means = [mean([p[0] for p in pairs]), mean([p[1] for p in pairs])]
    ssr = k * sum((m - grand) ** 2 for m in row_means)
    ssc = n * sum((m - grand) ** 2 for m in col_means)
    sst = sum((v - grand) ** 2 for p in pairs for v in p)
    sse = sst - ssr - ssc
    msr = ssr / (n - 1)
    msc = ssc / (k - 1)
    mse = sse / ((n - 1) * (k - 1)) if (n - 1) * (k - 1) else 0.0
    denom = msr + (k - 1) * mse + k * (msc - mse) / n
    if denom == 0:
        return {"sufficient": False, "n": n, "missing": missing, "reason": "Zero variance — ICC undefined"}
    icc = (msr - mse) / denom
    return {"sufficient": True, "n": n, "missing": missing, "icc": icc, "model": "ICC(2,1) absolute agreement"}


def bland_altman(a: list[float | None], b: list[float | None]) -> dict:
    pairs = _clean_pairs(a, b)
    n = len(pairs)
    missing = len(a) - n
    if n < MIN_N_BLAND_ALTMAN:
        return {"sufficient": False, "n": n, "missing": missing, "reason": f"Bland–Altman requires at least {MIN_N_BLAND_ALTMAN} complete pairs"}
    diffs = [x - y for x, y in pairs]
    means = [(x + y) / 2 for x, y in pairs]
    bias = mean(diffs)
    sd = stdev(diffs)
    return {
        "sufficient": True,
        "n": n,
        "missing": missing,
        "bias": bias,
        "sd": sd,
        "loa_lower": bias - 1.96 * sd,
        "loa_upper": bias + 1.96 * sd,
        "points": [{"mean": m, "diff": d} for m, d in zip(means, diffs)],
    }


def coefficient_of_variation(values: list[float | None]) -> dict:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    n = len(vals)
    if n < MIN_N_CV:
        return {"sufficient": False, "n": n, "reason": f"CV requires at least {MIN_N_CV} values"}
    m = mean(vals)
    if m == 0:
        return {"sufficient": False, "n": n, "reason": "Mean is zero — CV undefined"}
    return {"sufficient": True, "n": n, "cv_percent": stdev(vals) / abs(m) * 100, "mean": m}


def describe(values: list[float | None]) -> dict:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    n = len(vals)
    if n == 0:
        return {"n": 0, "missing": len(values)}
    s = sorted(vals)
    mid = n // 2
    median = s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
    return {
        "n": n,
        "missing": len(values) - n,
        "mean": mean(vals),
        "sd": stdev(vals) if n > 1 else None,
        "min": s[0],
        "max": s[-1],
        "median": median,
    }


def histogram(values: list[float | None], bins: int = 10) -> list[dict]:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    if lo == hi:
        return [{"bin_start": lo, "bin_end": hi, "count": len(vals)}]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in vals:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    return [{"bin_start": lo + i * width, "bin_end": lo + (i + 1) * width, "count": c} for i, c in enumerate(counts)]
