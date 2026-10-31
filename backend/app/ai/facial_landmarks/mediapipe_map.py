"""
MediaPipe Face Mesh (478-point) index → protocol landmark code mapping.

This mapping is an *approximation*: MediaPipe topology points do not coincide
exactly with anthropometric landmarks. All mapped predictions require examiner
review. Landmarks without a reasonable MediaPipe counterpart (e.g. Tragion) are
reported as not identifiable — they are never fabricated.
"""

MEDIAPIPE_INDEX_MAP: dict[str, int] = {
    "N": 168,
    "PRN": 1,
    "SN": 2,
    "STO": 13,
    "PG": 175,
    "ME": 152,
    "EX_R": 33,
    "EX_L": 263,
    "EN_R": 133,
    "EN_L": 362,
    "AL_R": 64,
    "AL_L": 294,
    "CH_R": 61,
    "CH_L": 291,
    "ZY_R": 234,
    "ZY_L": 454,
    "GO_R": 172,
    "GO_L": 397,
}

NOT_AVAILABLE_IN_MEDIAPIPE = {"T_R", "T_L"}
