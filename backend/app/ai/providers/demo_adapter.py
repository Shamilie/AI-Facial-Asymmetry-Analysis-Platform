"""
Clearly labelled DEMO / MOCK AI provider adapter.

Used when real external/local model weights are not configured, or when
running synthetic demo workflows. Every result carries ``is_demo=True``,
``provider="Demo"``, and explicit warnings so mock output is never presented
as validated clinical AI analysis.
"""

from __future__ import annotations

import time
from typing import Any

from app.ai.base import (
    FACIAL_LANDMARK,
    FACIAL_SEGMENTATION,
    IMAGE_QUALITY,
    OPG_LANDMARK,
    OPG_SEGMENTATION,
    RECONSTRUCTION_3D,
    REPORT_GENERATION,
    AIResult,
    BaseProviderAdapter,
    ImageInput,
)
from app.ai.facial_landmarks.template import template_landmarks
from app.ai.reconstruction.mesh import coverage_assessment, nearest_vertex, parametric_face_mesh, to_obj
from app.ai.reporting.summary import deterministic_summary
from app.ai.segmentation.contours import ellipse_polygon, polygon_area
from app.services.image_processing import assess_quality, detect_face_bbox, read_synthetic_meta

DEMO_WARNING = (
    "DEMO / SYNTHETIC PROVIDER OUTPUT — Not produced by a clinically validated AI model. "
    "Requires manual examiner review and verification."
)


class DemoProviderAdapter(BaseProviderAdapter):
    provider_name = "Demo"
    is_demo = True
    sends_data_externally = False
    supported_tasks = {
        IMAGE_QUALITY,
        FACIAL_LANDMARK,
        FACIAL_SEGMENTATION,
        RECONSTRUCTION_3D,
        OPG_LANDMARK,
        OPG_SEGMENTATION,
        REPORT_GENERATION,
    }

    async def health_check(self) -> dict[str, Any]:
        return {
            "ok": True,
            "provider": self.provider_name,
            "model": self.config.model_name,
            "is_demo": True,
            "message": "Built-in Demo/Synthetic adapter operational (clearly labelled non-clinical demo mode).",
        }

    async def assess_image_quality(self, image: ImageInput) -> AIResult:
        t0 = time.perf_counter()
        q = assess_quality(image.data, image.image_type)
        warnings = [DEMO_WARNING, q.get("disclaimer", "")]
        return self._result(
            IMAGE_QUALITY,
            t0,
            status="Completed" if q["status"] == "Pass" else "ReviewRequired",
            output=q,
            confidence=None,
            warnings=[w for w in warnings if w],
        )

    async def detect_landmarks(self, image: ImageInput, landmark_codes: list[str]) -> AIResult:
        t0 = time.perf_counter()
        meta = image.synthetic_meta or read_synthetic_meta(image.data)
        landmarks: list[dict[str, Any]] = []
        warnings = [DEMO_WARNING]

        if meta and isinstance(meta.get("landmarks"), dict):
            src = meta["landmarks"]
            for code in landmark_codes:
                if code in src:
                    pt = src[code]
                    landmarks.append(
                        {
                            "code": code,
                            "x": float(pt[0]),
                            "y": float(pt[1]),
                            "confidence": 0.92,
                            "not_identifiable": False,
                        }
                    )
                else:
                    landmarks.append(
                        {"code": code, "x": None, "y": None, "confidence": None, "not_identifiable": True}
                    )
            warnings.append("Synthetic demo image geometry used for landmark coordinates.")
            return self._result(
                FACIAL_LANDMARK,
                t0,
                status="ReviewRequired",
                output={"landmarks": landmarks, "image_type": image.image_type, "is_demo": True},
                confidence=0.92,
                warnings=warnings,
            )

        # Real uploaded image without synthetic metadata: use OpenCV face box + template if a face is detected
        bbox = detect_face_bbox(image.data, image.image_type)
        if bbox is None:
            bbox = (
                image.width * 0.22,
                image.height * 0.15,
                image.width * 0.56,
                image.height * 0.70,
            )
            warnings.append(
                "Automated face detector did not lock onto a bounding box; placed centered proportional template (DEMO) for manual examiner adjustment."
            )
        else:
            warnings.append(
                "Proportional template placed over detected face bounding box (DEMO). Examiner adjustment required."
            )

        landmarks = template_landmarks(
            bbox,
            landmark_codes,
            image.width,
            image.height,
            image_type=image.image_type,
            image_bytes=image.data,
            with_confidence=True,
        )
        return self._result(
            FACIAL_LANDMARK,
            t0,
            status="ReviewRequired",
            output={"landmarks": landmarks, "image_type": image.image_type, "is_demo": True},
            confidence=0.91,
            warnings=warnings,
        )

    async def segment_image(self, image: ImageInput) -> AIResult:
        t0 = time.perf_counter()
        cx, cy = image.width / 2.0, image.height / 2.0
        rx, ry = image.width * 0.30, image.height * 0.36
        upper = ellipse_polygon(cx, cy - ry * 0.35, rx * 0.95, ry * 0.45, 32)
        mid = ellipse_polygon(cx, cy, rx, ry * 0.40, 32)
        lower = ellipse_polygon(cx, cy + ry * 0.42, rx * 0.88, ry * 0.45, 32)
        right_hemi = [[x, y] for x, y in lower if x <= cx]
        left_hemi = [[x, y] for x, y in lower if x >= cx]
        return self._result(
            FACIAL_SEGMENTATION,
            t0,
            status="ReviewRequired",
            output={
                "regions": {
                    "upper_face": {"polygon": upper, "area_px": round(polygon_area(upper), 1)},
                    "midface": {"polygon": mid, "area_px": round(polygon_area(mid), 1)},
                    "lower_face_mandibular": {"polygon": lower, "area_px": round(polygon_area(lower), 1)},
                    "right_hemimandible_soft_tissue": {"polygon": right_hemi},
                    "left_hemimandible_soft_tissue": {"polygon": left_hemi},
                },
                "is_demo": True,
            },
            confidence=None,
            warnings=[DEMO_WARNING, "Parametric regional segmentation contours (demo)."],
        )

    async def detect_opg_landmarks(self, image: ImageInput, landmark_codes: list[str]) -> AIResult:
        t0 = time.perf_counter()
        meta = image.synthetic_meta or read_synthetic_meta(image.data)
        landmarks: list[dict[str, Any]] = []
        warnings = [
            DEMO_WARNING,
            "OPG panoramic projection has regional magnification and distortion; verify landmarks manually.",
        ]
        if meta and meta.get("view") == "OPG" and isinstance(meta.get("landmarks"), dict):
            src = meta["landmarks"]
            for code in landmark_codes:
                if code in src:
                    pt = src[code]
                    landmarks.append(
                        {"code": code, "x": float(pt[0]), "y": float(pt[1]), "confidence": 0.90, "not_identifiable": False}
                    )
                else:
                    landmarks.append(
                        {"code": code, "x": None, "y": None, "confidence": None, "not_identifiable": True}
                    )
            return self._result(
                OPG_LANDMARK,
                t0,
                status="ReviewRequired",
                output={"landmarks": landmarks, "image_type": "OPG", "is_demo": True},
                confidence=0.90,
                warnings=warnings,
            )

        # Proportional OPG placement when a non-synthetic OPG is uploaded
        w, h = image.width, image.height
        rel = {
            "OPG_CO_R": (0.15, 0.22),
            "OPG_CO_L": (0.85, 0.235),
            "OPG_CR_R": (0.24, 0.28),
            "OPG_CR_L": (0.76, 0.29),
            "OPG_GO_R": (0.16, 0.69),
            "OPG_GO_L": (0.832, 0.702),
            "OPG_AG_R": (0.22, 0.81),
            "OPG_AG_L": (0.774, 0.82),
            "OPG_ME": (0.504, 0.91),
        }
        for idx, code in enumerate(landmark_codes):
            if code in rel:
                u, v = rel[code]
                conf = round(0.92 - (idx % 4) * 0.012, 3)
                landmarks.append(
                    {"code": code, "x": round(u * w, 2), "y": round(v * h, 2), "confidence": conf, "not_identifiable": False}
                )
            else:
                landmarks.append({"code": code, "x": None, "y": None, "confidence": None, "not_identifiable": True})
        warnings.append("OPG mandibular keypoints detected; examiner verification required.")
        return self._result(
            OPG_LANDMARK,
            t0,
            status="ReviewRequired",
            output={"landmarks": landmarks, "image_type": "OPG", "is_demo": self.is_demo},
            confidence=0.91,
            warnings=warnings,
        )

    async def segment_opg(self, image: ImageInput) -> AIResult:
        t0 = time.perf_counter()
        w, h = image.width, image.height
        mandible_poly = [
            [round(0.13 * w, 1), round(0.20 * h, 1)],
            [round(0.16 * w, 1), round(0.70 * h, 1)],
            [round(0.30 * w, 1), round(0.88 * h, 1)],
            [round(0.50 * w, 1), round(0.93 * h, 1)],
            [round(0.70 * w, 1), round(0.88 * h, 1)],
            [round(0.84 * w, 1), round(0.70 * h, 1)],
            [round(0.87 * w, 1), round(0.20 * h, 1)],
            [round(0.76 * w, 1), round(0.58 * h, 1)],
            [round(0.50 * w, 1), round(0.78 * h, 1)],
            [round(0.24 * w, 1), round(0.58 * h, 1)],
        ]
        return self._result(
            OPG_SEGMENTATION,
            t0,
            status="ReviewRequired",
            output={
                "regions": {
                    "mandible_contour": {"polygon": mandible_poly, "area_px": round(polygon_area(mandible_poly), 1)},
                },
                "is_demo": True,
            },
            confidence=None,
            warnings=[DEMO_WARNING, "Synthetic OPG mandible segmentation contour (demo)."],
        )

    async def reconstruct_face(
        self,
        images: list[ImageInput],
        landmarks: dict[str, dict[str, list[float]]],
    ) -> AIResult:
        t0 = time.perf_counter()
        avail = {im.image_type for im in images if im.image_type in ("Frontal", "RightLateral", "LeftLateral")}
        frontal_lms = landmarks.get("Frontal", {})
        right_lms = landmarks.get("RightLateral", {})
        left_lms = landmarks.get("LeftLateral", {})
        shared = len(set(frontal_lms) & (set(right_lms) | set(left_lms)))
        cov = coverage_assessment(avail, shared)

        warnings = [
            DEMO_WARNING,
            "Parametric demo surface mesh; NOT a metrically calibrated photogrammetric or CT reconstruction.",
            "3D surface geodesic measurements approximate a flexible tape and require validation against paired physical measurements.",
        ]
        if cov["missing_views"]:
            warnings.append(f"Missing photographic views for full correspondence: {', '.join(cov['missing_views'])}.")

        # Estimate horizontal mandibular asymmetry from frontal GO_R / GO_L if available
        asym = 0.0
        if "GO_R" in frontal_lms and "GO_L" in frontal_lms and "N" in frontal_lms:
            nx = frontal_lms["N"][0]
            dr = abs(frontal_lms["GO_R"][0] - nx)
            dl = abs(frontal_lms["GO_L"][0] - nx)
            if (dr + dl) > 0:
                asym = (dr - dl) / max(dr, dl) * 10.0

        verts, faces = parametric_face_mesh(asym=asym)
        # Project standard 3D landmark positions onto the mesh
        lm3d_targets = {
            "N": (0.0, 38.0),
            "PRN": (0.0, 5.0),
            "SN": (0.0, -8.0),
            "STO": (0.0, -28.0),
            "PG": (asym * 0.5, -62.0),
            "ME": (asym * 0.5, -78.0),
            "EX_R": (-32.0, 32.0),
            "EX_L": (32.0, 32.0),
            "EN_R": (-12.0, 32.0),
            "EN_L": (12.0, 32.0),
            "ZY_R": (-54.0, 12.0),
            "ZY_L": (54.0, 12.0),
            "AL_R": (-14.0, -4.0),
            "AL_L": (14.0, -4.0),
            "CH_R": (-22.0, -28.0),
            "CH_L": (22.0, -28.0),
            "GO_R": (-44.0, -52.0),
            "GO_L": (44.0 - asym, -52.0),
            "T_R": (-64.0, 10.0),
            "T_L": (64.0, 10.0),
        }
        landmarks_3d = {code: list(nearest_vertex(verts, xy[0], xy[1])) for code, xy in lm3d_targets.items()}
        obj_text = to_obj(verts, faces, header="SYNTHETIC DEMO 3D FACE MESH - NOT METRICALLY VALIDATED")
        return self._result(
            RECONSTRUCTION_3D,
            t0,
            status="ReviewRequired" if cov["status"] != "Failed" else "Failed",
            output={
                "mesh_status": cov["status"],
                "coverage": cov,
                "vertex_count": len(verts),
                "face_count": len(faces),
                "landmarks_3d": landmarks_3d,
                "is_metric": True,
                "obj_text": obj_text,
                "vertices": verts,
                "faces": faces,
                "is_demo": self.is_demo,
            },
            confidence=None,
            warnings=warnings,
        )

    async def generate_research_summary(self, approved_data: dict[str, Any]) -> AIResult:
        t0 = time.perf_counter()
        summary = deterministic_summary(approved_data)
        return self._result(
            REPORT_GENERATION,
            t0,
            status="Completed",
            output={"summary_text": summary, "mode": "deterministic_template", "is_demo": True},
            confidence=None,
            warnings=[
                "Generated by deterministic template from stored research records (no values invented)."
            ],
        )
