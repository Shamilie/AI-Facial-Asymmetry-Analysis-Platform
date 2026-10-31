"""
Unit tests for the validated geometric measurement engine and reliability statistics.

Covers every required scenario from Section 14:
  1. Valid bilateral values
  2. Missing right-side value
  3. Missing left-side value
  4. Zero denominator
  5. Invalid calibration
  6. Not-identifiable landmark
  7. Unscaled image (and display PPI assumption rejected as physical calibration)
  8. Out-of-range coordinates
"""

from __future__ import annotations

import pytest

from app.measurements.engine import (
    CalibrationInfo,
    LandmarkPoint,
    MeasurementEngine,
    ViewData,
    asymmetry_index,
    calibration_mm_per_pixel,
)
from app.measurements.statistics import bland_altman, coefficient_of_variation, icc_2_1

SPEC_MIDLINE = {
    "kind": "midline_distance",
    "view": "Frontal",
    "midline": ["N", "SN"],
    "right": "GO_R",
    "left": "GO_L",
    "asymmetry_index": True,
}


def _base_landmarks() -> dict[str, LandmarkPoint]:
    return {
        "N": LandmarkPoint("N", 450.0, 300.0),
        "SN": LandmarkPoint("SN", 450.0, 520.0),
        "GO_R": LandmarkPoint("GO_R", 250.0, 700.0),  # 200 px from midline
        "GO_L": LandmarkPoint("GO_L", 610.0, 700.0),  # 160 px from midline
    }


def test_valid_bilateral_values():
    cal = CalibrationInfo(mm_per_pixel=0.25, is_physical=True, same_plane_confirmed=True, calibration_id="cal-1")
    engine = MeasurementEngine({"Frontal": ViewData(_base_landmarks(), width=900, height=1150, calibration=cal)})
    res = engine.compute("GO_MID", SPEC_MIDLINE, "mm")
    assert res.right.value == pytest.approx(50.0)
    assert res.left.value == pytest.approx(40.0)
    assert res.absolute_difference == pytest.approx(10.0)
    # |50 - 40| / (50 + 40) * 100 = 11.111...
    assert res.asymmetry_index == pytest.approx(11.1111, rel=1e-3)
    assert res.status == "Calculated"
    assert not res.is_unscaled


def test_missing_right_side_value():
    lms = _base_landmarks()
    del lms["GO_R"]
    cal = CalibrationInfo(mm_per_pixel=0.25, is_physical=True, same_plane_confirmed=True)
    engine = MeasurementEngine({"Frontal": ViewData(lms, width=900, height=1150, calibration=cal)})
    res = engine.compute("GO_MID", SPEC_MIDLINE, "mm")
    assert res.right.value is None
    assert res.left.value == pytest.approx(40.0)
    assert res.asymmetry_index is None
    assert res.status == "MissingData"


def test_missing_left_side_value():
    lms = _base_landmarks()
    del lms["GO_L"]
    cal = CalibrationInfo(mm_per_pixel=0.25, is_physical=True, same_plane_confirmed=True)
    engine = MeasurementEngine({"Frontal": ViewData(lms, width=900, height=1150, calibration=cal)})
    res = engine.compute("GO_MID", SPEC_MIDLINE, "mm")
    assert res.right.value == pytest.approx(50.0)
    assert res.left.value is None
    assert res.asymmetry_index is None
    assert res.status == "MissingData"


def test_zero_denominator_asymmetry_index():
    ai, warning = asymmetry_index(0.0, 0.0)
    assert ai is None
    assert warning is not None and "zero denominator" in warning.lower()


def test_invalid_calibration():
    with pytest.raises(ValueError):
        calibration_mm_per_pixel(50.0, 0.0)
    cal = CalibrationInfo(mm_per_pixel=-0.25, is_physical=True)
    engine = MeasurementEngine({"Frontal": ViewData(_base_landmarks(), width=900, height=1150, calibration=cal)})
    res = engine.compute("GO_MID", SPEC_MIDLINE, "mm")
    assert res.right.value is None
    assert res.left.value is None
    assert res.status == "Unscaled"


def test_not_identifiable_landmark():
    lms = _base_landmarks()
    lms["GO_L"] = LandmarkPoint("GO_L", None, None, status="NotIdentifiable")
    cal = CalibrationInfo(mm_per_pixel=0.25, is_physical=True, same_plane_confirmed=True)
    engine = MeasurementEngine({"Frontal": ViewData(lms, width=900, height=1150, calibration=cal)})
    res = engine.compute("GO_MID", SPEC_MIDLINE, "mm")
    assert res.right.value == pytest.approx(50.0)
    assert res.left.value is None
    assert res.left.status == "not_identifiable"
    assert res.status == "NotIdentifiable"


def test_unscaled_image_and_ppi_assumption_rejected():
    # Display PPI assumption (1 mm = 3.78 px -> is_physical=False) must NOT scale physical measurements
    ppi_cal = CalibrationInfo(mm_per_pixel=1.0 / 3.78, is_physical=False)
    engine = MeasurementEngine({"Frontal": ViewData(_base_landmarks(), width=900, height=1150, calibration=ppi_cal)})
    res = engine.compute("GO_MID", SPEC_MIDLINE, "mm")
    assert res.right.value is None
    assert res.left.value is None
    assert res.is_unscaled is True
    assert res.status == "Unscaled"
    assert any("display/ppi" in w.lower() for w in res.warnings)


def test_out_of_range_coordinates():
    lms = _base_landmarks()
    lms["GO_R"] = LandmarkPoint("GO_R", 1450.0, 700.0)  # outside width=900
    cal = CalibrationInfo(mm_per_pixel=0.25, is_physical=True, same_plane_confirmed=True)
    engine = MeasurementEngine({"Frontal": ViewData(lms, width=900, height=1150, calibration=cal)})
    res = engine.compute("GO_MID", SPEC_MIDLINE, "mm")
    assert res.right.value is None
    assert res.right.status == "out_of_range"
    assert res.status == "Invalid"


def test_statistics_sample_size_guards():
    small_a = [10.0, 12.0, 14.0]
    small_b = [10.2, 11.9, 14.1]
    assert icc_2_1(small_a, small_b)["sufficient"] is False
    assert bland_altman(small_a, small_b)["sufficient"] is False
    assert coefficient_of_variation(small_a)["sufficient"] is True

    # Sufficient sample (n >= 10)
    a = [40.0 + i * 1.5 for i in range(12)]
    b = [40.1 + i * 1.5 for i in range(12)]
    icc_res = icc_2_1(a, b)
    ba_res = bland_altman(a, b)
    assert icc_res["sufficient"] is True and icc_res["icc"] > 0.99
    assert ba_res["sufficient"] is True and abs(ba_res["bias"] + 0.1) < 1e-6
