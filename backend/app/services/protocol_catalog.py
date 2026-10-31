"""
Default research protocol catalogue: visit schedule, landmark definitions and
measurement definitions. Seeded into the database as protocol version 1.0.

Measurement ``spec`` kinds understood by the geometric engine:
  * ``midline_distance`` – perpendicular distance from a bilateral landmark to a
    facial midline defined by two midline landmarks, in one view.
  * ``distance``         – Euclidean distance between two landmarks per side.
  * ``angle``            – angle at a vertex landmark (degrees; scale-invariant).
  * ``geodesic``         – 3D surface path length on a reconstructed mesh
    (approximation of a flexible tape measurement; requires separate validation).
"""

from __future__ import annotations

VISIT_SCHEDULE = [
    {"visit_type": "PreOperative", "label": "Pre-operative", "offset_days": -1, "window_days": 3, "order": 1},
    {"visit_type": "PostOp1Week", "label": "Post-operative – 1 week", "offset_days": 7, "window_days": 2, "order": 2},
    {"visit_type": "PostOp6Weeks", "label": "Post-operative – 6 weeks", "offset_days": 42, "window_days": 7, "order": 3},
    {"visit_type": "PostOp3Months", "label": "Post-operative – 3 months", "offset_days": 90, "window_days": 14, "order": 4},
    {"visit_type": "PostOp6Months", "label": "Post-operative – 6 months", "offset_days": 180, "window_days": 14, "order": 5},
]

REQUIRED_IMAGE_TYPES = ["Frontal", "RightLateral", "LeftLateral", "OPG"]

FACE_VIEWS_R = ["Frontal", "RightLateral"]
FACE_VIEWS_L = ["Frontal", "LeftLateral"]
ALL_FACE = ["Frontal", "RightLateral", "LeftLateral"]


def _bilateral(code: str, name: str, region: str, views_r: list[str], views_l: list[str], order: int, kind: str = "Facial"):
    return [
        {"code": f"{code}_R", "name": f"{name} (Right)", "side": "Right", "landmark_type": kind,
         "anatomical_region": region, "applicable_views": views_r, "display_order": order, "is_bilateral": True},
        {"code": f"{code}_L", "name": f"{name} (Left)", "side": "Left", "landmark_type": kind,
         "anatomical_region": region, "applicable_views": views_l, "display_order": order + 1, "is_bilateral": True},
    ]


LANDMARKS: list[dict] = [
    {"code": "N", "name": "Soft-tissue Nasion", "side": "Midline", "landmark_type": "Facial", "anatomical_region": "Midface", "applicable_views": ALL_FACE, "display_order": 1, "is_bilateral": False},
    {"code": "PRN", "name": "Pronasale", "side": "Midline", "landmark_type": "Facial", "anatomical_region": "Nose", "applicable_views": ALL_FACE, "display_order": 2, "is_bilateral": False},
    {"code": "SN", "name": "Subnasale", "side": "Midline", "landmark_type": "Facial", "anatomical_region": "Nose", "applicable_views": ALL_FACE, "display_order": 3, "is_bilateral": False},
    {"code": "STO", "name": "Stomion", "side": "Midline", "landmark_type": "Facial", "anatomical_region": "Lips", "applicable_views": ["Frontal"], "display_order": 4, "is_bilateral": False},
    {"code": "PG", "name": "Soft-tissue Pogonion", "side": "Midline", "landmark_type": "Facial", "anatomical_region": "Chin", "applicable_views": ALL_FACE, "display_order": 5, "is_bilateral": False},
    {"code": "ME", "name": "Soft-tissue Menton", "side": "Midline", "landmark_type": "Facial", "anatomical_region": "Chin", "applicable_views": ALL_FACE, "display_order": 6, "is_bilateral": False},
    *_bilateral("EX", "Exocanthion", "Orbit", FACE_VIEWS_R, FACE_VIEWS_L, 10),
    *_bilateral("EN", "Endocanthion", "Orbit", ["Frontal"], ["Frontal"], 12),
    *_bilateral("ZY", "Zygion", "Midface", ["Frontal"], ["Frontal"], 14),
    *_bilateral("AL", "Alare", "Nose", ["Frontal"], ["Frontal"], 16),
    *_bilateral("CH", "Cheilion", "Lips", FACE_VIEWS_R, FACE_VIEWS_L, 18),
    *_bilateral("GO", "Soft-tissue Gonion", "Mandible", FACE_VIEWS_R, FACE_VIEWS_L, 20),
    *_bilateral("T", "Tragion", "Ear", ["RightLateral"], ["LeftLateral"], 22),
    # --- OPG (radiographic) landmarks ---
    *_bilateral("OPG_CO", "Condylion", "Condyle", ["OPG"], ["OPG"], 40, "OPG"),
    *_bilateral("OPG_CR", "Coronoid tip", "Ramus", ["OPG"], ["OPG"], 42, "OPG"),
    *_bilateral("OPG_GO", "Gonion", "Mandibular angle", ["OPG"], ["OPG"], 44, "OPG"),
    *_bilateral("OPG_AG", "Antegonial notch", "Mandibular body", ["OPG"], ["OPG"], 46, "OPG"),
    {"code": "OPG_ME", "name": "Menton (radiographic)", "side": "Midline", "landmark_type": "OPG", "anatomical_region": "Symphysis", "applicable_views": ["OPG"], "display_order": 50, "is_bilateral": False},
]

MEASUREMENTS: list[dict] = [
    {
        "code": "EX_MID", "name": "Exocanthion to facial midline", "measurement_type": "Linear", "unit": "mm",
        "description": "Perpendicular distance from exocanthion to the N–SN midline on the frontal photograph.",
        "spec": {"kind": "midline_distance", "view": "Frontal", "midline": ["N", "SN"], "right": "EX_R", "left": "EX_L", "asymmetry_index": True},
        "display_order": 1,
    },
    {
        "code": "ZY_MID", "name": "Zygion to facial midline", "measurement_type": "Linear", "unit": "mm",
        "description": "Perpendicular distance from zygion to the N–SN midline (frontal).",
        "spec": {"kind": "midline_distance", "view": "Frontal", "midline": ["N", "SN"], "right": "ZY_R", "left": "ZY_L", "asymmetry_index": True},
        "display_order": 2,
    },
    {
        "code": "AL_MID", "name": "Alare to facial midline", "measurement_type": "Linear", "unit": "mm",
        "description": "Perpendicular distance from alare to the N–SN midline (frontal).",
        "spec": {"kind": "midline_distance", "view": "Frontal", "midline": ["N", "SN"], "right": "AL_R", "left": "AL_L", "asymmetry_index": True},
        "display_order": 3,
    },
    {
        "code": "CH_MID", "name": "Cheilion to facial midline", "measurement_type": "Linear", "unit": "mm",
        "description": "Perpendicular distance from cheilion to the N–SN midline (frontal).",
        "spec": {"kind": "midline_distance", "view": "Frontal", "midline": ["N", "SN"], "right": "CH_R", "left": "CH_L", "asymmetry_index": True},
        "display_order": 4,
    },
    {
        "code": "GO_MID", "name": "Soft-tissue gonion to facial midline", "measurement_type": "Linear", "unit": "mm",
        "description": "Perpendicular distance from soft-tissue gonion to the N–SN midline (frontal).",
        "spec": {"kind": "midline_distance", "view": "Frontal", "midline": ["N", "SN"], "right": "GO_R", "left": "GO_L", "asymmetry_index": True},
        "display_order": 5,
    },
    {
        "code": "EX_CH", "name": "Exocanthion – Cheilion (frontal)", "measurement_type": "Linear", "unit": "mm",
        "description": "Vertical/oblique hemi-facial height between exocanthion and cheilion on the frontal photograph.",
        "spec": {"kind": "distance", "view_right": "Frontal", "view_left": "Frontal", "right": ["EX_R", "CH_R"], "left": ["EX_L", "CH_L"], "asymmetry_index": True},
        "display_order": 6,
    },
    {
        "code": "GO_PG_F", "name": "Gonion – Pogonion (frontal)", "measurement_type": "Linear", "unit": "mm",
        "description": "Projected mandibular contour length on the frontal photograph.",
        "spec": {"kind": "distance", "view_right": "Frontal", "view_left": "Frontal", "right": ["GO_R", "PG"], "left": ["GO_L", "PG"], "asymmetry_index": True},
        "display_order": 7,
    },
    {
        "code": "T_CH", "name": "Tragion – Cheilion (lateral)", "measurement_type": "Linear", "unit": "mm",
        "description": "Right value from the right lateral photograph and left value from the left lateral photograph, each with its own view-specific calibration.",
        "spec": {"kind": "distance", "view_right": "RightLateral", "view_left": "LeftLateral", "right": ["T_R", "CH_R"], "left": ["T_L", "CH_L"], "asymmetry_index": True},
        "display_order": 8,
    },
    {
        "code": "T_PG", "name": "Tragion – Soft-tissue Pogonion (lateral)", "measurement_type": "Linear", "unit": "mm",
        "description": "Projected 2D tragion–pogonion distance per lateral view.",
        "spec": {"kind": "distance", "view_right": "RightLateral", "view_left": "LeftLateral", "right": ["T_R", "PG"], "left": ["T_L", "PG"], "asymmetry_index": True},
        "display_order": 9,
    },
    {
        "code": "T_GO", "name": "Tragion – Soft-tissue Gonion (lateral)", "measurement_type": "Linear", "unit": "mm",
        "description": "Projected 2D tragion–gonion distance per lateral view.",
        "spec": {"kind": "distance", "view_right": "RightLateral", "view_left": "LeftLateral", "right": ["T_R", "GO_R"], "left": ["T_L", "GO_L"], "asymmetry_index": True},
        "display_order": 10,
    },
    {
        "code": "OPG_RAMUS", "name": "Ramus height (Condylion – Gonion, OPG)", "measurement_type": "Linear", "unit": "mm",
        "description": "Ramus height on the OPG. Panoramic magnification and regional distortion must be considered.",
        "spec": {"kind": "distance", "view_right": "OPG", "view_left": "OPG", "right": ["OPG_CO_R", "OPG_GO_R"], "left": ["OPG_CO_L", "OPG_GO_L"], "asymmetry_index": True},
        "display_order": 11,
    },
    {
        "code": "OPG_BODY", "name": "Mandibular body length (Gonion – Menton, OPG)", "measurement_type": "Linear", "unit": "mm",
        "description": "Mandibular body length on the OPG. Horizontal panoramic distortion is typically larger than vertical.",
        "spec": {"kind": "distance", "view_right": "OPG", "view_left": "OPG", "right": ["OPG_GO_R", "OPG_ME"], "left": ["OPG_GO_L", "OPG_ME"], "asymmetry_index": True},
        "display_order": 12,
    },
    {
        "code": "OPG_GONIAL", "name": "Gonial angle (Co – Go – Me, OPG)", "measurement_type": "Angular", "unit": "deg",
        "description": "Gonial angle per side. Angles do not require length calibration; asymmetry index is not computed for angles.",
        "spec": {"kind": "angle", "view_right": "OPG", "view_left": "OPG", "right": ["OPG_CO_R", "OPG_GO_R", "OPG_ME"], "left": ["OPG_CO_L", "OPG_GO_L", "OPG_ME"], "asymmetry_index": False},
        "display_order": 13,
    },
    {
        "code": "GEO_T_PG", "name": "Tragion – Pogonion surface geodesic (3D)", "measurement_type": "Linear", "unit": "mm",
        "description": "Approximate surface path on a reconstructed 3D mesh. Approximates a flexible tape measurement and must be validated against paired physical measurements before being treated as equivalent.",
        "spec": {"kind": "geodesic", "view_right": "Mesh3D", "view_left": "Mesh3D", "right": ["T_R", "PG"], "left": ["T_L", "PG"], "asymmetry_index": True},
        "display_order": 14,
    },
]

CALIBRATION_RULES = {
    "facial_views_require_separate_calibration": True,
    "marker_must_be_in_same_plane": True,
    "opg_pixel_spacing_not_sufficient_alone": True,
    "display_ppi_assumption_is_not_calibration": True,
    "min_marker_length_px": 20,
}

REVIEW_REQUIREMENTS = {
    "landmark_review_required": True,
    "measurement_approval_role": "Clinician / Examiner",
    "dual_review": False,
}

IMAGE_ACQUISITION_REQUIREMENTS = {
    "formats": ["image/jpeg", "image/png", "image/tiff", "image/bmp"],
    "min_dimension_px": 400,
    "max_size_mb": 50,
    "frontal": "Natural head position, Frankfort horizontal parallel to floor, neutral expression, lips relaxed, calibration ruler in the facial plane.",
    "lateral": "True 90° profile, Frankfort horizontal parallel to floor, ear visible, calibration ruler in the mid-sagittal plane.",
    "opg": "Standard panoramic radiograph; record device, magnification factor and pixel spacing.",
}
