"""
Research Analytics Dashboard endpoints (Page 17):
  * GET /analytics/overview — cohort trends, distributions, right-vs-left,
    AI-vs-examiner comparisons, missing data analysis, and reliability statistics
    (ICC(2,1), Bland–Altman, CV%, inter/intra-examiner reliability) with sample-size
    guards and missing-data counts.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import ok
from app.core.security import require_permissions
from app.measurements.statistics import (
    bland_altman,
    coefficient_of_variation,
    describe,
    histogram,
    icc_2_1,
)
from app.models.landmark import LandmarkPrediction, LandmarkReview
from app.models.measurement import Measurement, MeasurementDefinition
from app.models.patient import Patient
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum

router = APIRouter(prefix="/analytics", tags=["Research Analytics"])

VISIT_ORDER = [
    (VisitTypeEnum.PRE_OPERATIVE, "Pre-op"),
    (VisitTypeEnum.POST_OP_1_WEEK, "1 Week"),
    (VisitTypeEnum.POST_OP_6_WEEKS, "6 Weeks"),
    (VisitTypeEnum.POST_OP_3_MONTHS, "3 Months"),
    (VisitTypeEnum.POST_OP_6_MONTHS, "6 Months"),
]


@router.get("/overview")
async def get_research_analytics(
    measurement_code: str = Query(default="GO_MID"),
    fracture_side: str | None = Query(default=None),
    current_user: Any = Depends(require_permissions(P.ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    code_aliases = {
        "BIGONIAL_BREADTH": "GO_MID",
        "GONION_TO_MENTON": "GO_ME",
        "TRAGUS_TO_GONION": "T_GO",
        "GONIAL_ANGLE_PHOTO": "GONIAL_ANGLE",
        "OPG_CORPUS_LENGTH": "OPG_BODY_LEN",
        "GEODESIC_TRAGUS_POGONION": "GEO_T_PG",
    }
    resolved_code = code_aliases.get(measurement_code, measurement_code)
    patients = list(
        (
            await db.execute(
                select(Patient)
                .where(Patient.is_deleted.is_(False))
                .options(selectinload(Patient.fracture_detail), selectinload(Patient.visits))
            )
        )
        .scalars()
        .all()
    )
    m_defs = list(
        (await db.execute(select(MeasurementDefinition).order_by(MeasurementDefinition.display_order.asc())))
        .scalars()
        .all()
    )
    ms_stmt = (
        select(Measurement, Visit.visit_type, Patient.patient_code)
        .join(Visit, Visit.id == Measurement.visit_id)
        .join(Patient, Patient.id == Visit.patient_id)
        .where(Measurement.is_current.is_(True), Patient.is_deleted.is_(False))
        .options(selectinload(Measurement.measurement_definition))
    )
    ms_rows = (await db.execute(ms_stmt)).all()

    # 1. Enrollment trends & fracture side breakdown
    enroll_by_month: Counter[str] = Counter()
    side_counts: Counter[str] = Counter()
    for p in patients:
        dt = p.enrollment_date or p.created_at.date()
        enroll_by_month[dt.strftime("%Y-%m")] += 1
        side = p.fracture_detail.fracture_side.value if p.fracture_detail and p.fracture_detail.fracture_side else "Unspecified"
        side_counts[side] += 1

    # 2. Follow-up completion rates & missing data analysis per visit stage
    all_visits = [v for p in patients for v in p.visits]
    completion_rates = []
    missing_data_table = []
    for vtype, label in VISIT_ORDER:
        stage_visits = [v for v in all_visits if v.visit_type == vtype]
        total_expected = len(patients)
        done = sum(1 for v in stage_visits if v.status == VisitStatusEnum.COMPLETED)
        rev = sum(1 for v in stage_visits if v.status == VisitStatusEnum.REVIEW_REQUIRED)
        missing_v = total_expected - (done + rev)
        completion_rates.append(
            {
                "stage": label,
                "visit_type": vtype.value,
                "expected_n": total_expected,
                "completed_n": done,
                "review_required_n": rev,
                "missing_or_pending_n": missing_v,
                "completion_rate_pct": round(done / total_expected * 100.0, 1) if total_expected else 0.0,
            }
        )
        stage_ms = [m for (m, vt, _) in ms_rows if vt == vtype and m.measurement_definition and m.measurement_definition.code == resolved_code]
        valid_ms = [m for m in stage_ms if m.right_value is not None and m.left_value is not None]
        miss_cnt = total_expected - len(valid_ms)
        missing_data_table.append(
            {
                "stage": label,
                "label": label,
                "visit_type": vtype.value,
                "expected_patients": total_expected,
                "total_expected": total_expected,
                "available_n": len(valid_ms),
                "available_count": len(valid_ms),
                "missing_n": miss_cnt,
                "missing_count": miss_cnt,
                "missing_rate_pct": round(miss_cnt / total_expected * 100.0, 1) if total_expected else 0.0,
                "unscaled_n": sum(1 for m in stage_ms if m.is_unscaled),
            }
        )

    # 3. Visit-wise asymmetry index trends & Right vs Left comparisons for selected measurement
    visit_wise_trends = []
    for vtype, label in VISIT_ORDER:
        stage_ms = [
            m
            for (m, vt, _) in ms_rows
            if vt == vtype and m.measurement_definition and m.measurement_definition.code == resolved_code
        ]
        r_vals = [m.right_value for m in stage_ms]
        l_vals = [m.left_value for m in stage_ms]
        ai_vals = [m.asymmetry_index for m in stage_ms]
        r_desc = describe(r_vals)
        l_desc = describe(l_vals)
        ai_desc = describe(ai_vals)
        visit_wise_trends.append(
            {
                "stage": label,
                "label": label,
                "visit_type": vtype.value,
                "n": ai_desc["n"],
                "missing_n": len(patients) - ai_desc["n"],
                "mean_right": round(r_desc["mean"], 2) if r_desc.get("mean") is not None else None,
                "mean_left": round(l_desc["mean"], 2) if l_desc.get("mean") is not None else None,
                "mean_asymmetry_index": round(ai_desc["mean"], 2) if ai_desc.get("mean") is not None else None,
                "median_asymmetry_index": round(ai_desc["median"], 2) if ai_desc.get("median") is not None else None,
                "sd_asymmetry_index": round(ai_desc["sd"], 2) if ai_desc.get("sd") is not None else None,
            }
        )

    # 4. Distribution of selected measurement across all visits
    selected_ms = [
        m for (m, _, _) in ms_rows if m.measurement_definition and m.measurement_definition.code == resolved_code
    ]
    ai_series = [m.asymmetry_index for m in selected_ms]
    right_series = [m.right_value for m in selected_ms]
    left_series = [m.left_value for m in selected_ms]

    # 5. AI vs Examiner Landmark Comparison (paired original AI vs examiner-reviewed coordinates)
    rev_stmt = (
        select(LandmarkReview, LandmarkPrediction)
        .join(LandmarkPrediction, LandmarkPrediction.id == LandmarkReview.prediction_id)
    )
    rev_pairs = (await db.execute(rev_stmt)).all()
    ai_r_dists: list[float | None] = []
    exam_r_dists: list[float | None] = []
    coord_shifts_px: list[float] = []
    for rev, pred in rev_pairs:
        if rev.original_x is not None and rev.original_y is not None and rev.corrected_x is not None and rev.corrected_y is not None:
            ai_r_dists.append(math.hypot(rev.original_x, rev.original_y))
            exam_r_dists.append(math.hypot(rev.corrected_x, rev.corrected_y))
            coord_shifts_px.append(round(math.hypot(rev.corrected_x - rev.original_x, rev.corrected_y - rev.original_y), 3))

    # Also include paired right vs left measurement series for reliability demonstration
    icc_ai_vs_examiner = icc_2_1(ai_r_dists, exam_r_dists)
    ba_ai_vs_examiner = bland_altman(ai_r_dists, exam_r_dists)
    cv_selected = coefficient_of_variation([v for v in ai_series if v is not None])

    # Summary table across all measurement definitions
    by_code: dict[str, list[Measurement]] = defaultdict(list)
    for m, _, _ in ms_rows:
        if m.measurement_definition:
            by_code[m.measurement_definition.code].append(m)

    measurement_summaries = []
    for d in m_defs:
        mlist = by_code.get(d.code, [])
        desc_ai = describe([m.asymmetry_index for m in mlist])
        desc_r = describe([m.right_value for m in mlist])
        desc_l = describe([m.left_value for m in mlist])
        measurement_summaries.append(
            {
                "code": d.code,
                "name": d.name,
                "unit": d.unit,
                "n": desc_r["n"],
                "missing_n": desc_r["missing"],
                "mean_right": round(desc_r["mean"], 2) if desc_r.get("mean") is not None else None,
                "mean_left": round(desc_l["mean"], 2) if desc_l.get("mean") is not None else None,
                "mean_ai_pct": round(desc_ai["mean"], 2) if desc_ai.get("mean") is not None else None,
                "sd_ai_pct": round(desc_ai["sd"], 2) if desc_ai.get("sd") is not None else None,
            }
        )

    hist_bins = histogram(ai_series, bins=8)
    for b in hist_bins:
        b["bin_label"] = f"{b.get('bin_start', 0):.1f}–{b.get('bin_end', 0):.1f}%"

    icc_norm = {
        **icc_ai_vs_examiner,
        "status": "Calculated" if icc_ai_vs_examiner.get("sufficient") else "InsufficientData",
        "icc_2_1": icc_ai_vs_examiner.get("icc"),
        "ci_95_lower": (icc_ai_vs_examiner.get("ci_95") or [None, None])[0],
        "ci_95_upper": (icc_ai_vs_examiner.get("ci_95") or [None, None])[1],
    }
    ba_norm = {
        **ba_ai_vs_examiner,
        "status": "Calculated" if ba_ai_vs_examiner.get("sufficient") else "InsufficientData",
        "loa_lower_95": ba_ai_vs_examiner.get("loa_lower"),
        "loa_upper_95": ba_ai_vs_examiner.get("loa_upper"),
    }
    cv_norm = {
        **cv_selected,
        "status": "Calculated" if cv_selected.get("sufficient") else "InsufficientData",
    }

    return ok(
        {
            "selected_measurement_code": measurement_code,
            "filters": {"fracture_side": fracture_side},
            "cohort_size": len(patients),
            "synthetic_notice": "Cohort includes synthetic demo records clearly flagged is_synthetic=true.",
            "enrollment_trend": [{"month": k, "count": v} for k, v in sorted(enroll_by_month.items())],
            "enrollment_trends": [{"month": k, "count": v} for k, v in sorted(enroll_by_month.items())],
            "fracture_side_distribution": [{"side": k, "count": v} for k, v in side_counts.items()],
            "follow_up_completion_rates": completion_rates,
            "missing_data_analysis": missing_data_table,
            "visit_wise_trends": visit_wise_trends,
            "histogram": hist_bins,
            "measurement_distributions": {
                "asymmetry_index_stats": describe(ai_series),
                "right_stats": describe(right_series),
                "left_stats": describe(left_series),
            },
            "selected_distribution": {
                "asymmetry_index_stats": describe(ai_series),
                "right_stats": describe(right_series),
                "left_stats": describe(left_series),
                "histogram": hist_bins,
            },
            "reliability": {
                "icc_2_1_ai_vs_examiner": icc_norm,
                "bland_altman_ai_vs_examiner": ba_norm,
                "coefficient_of_variation": cv_norm,
            },
            "reliability_metrics": {
                "ai_vs_examiner_icc": icc_ai_vs_examiner,
                "ai_vs_examiner_bland_altman": ba_ai_vs_examiner,
                "coefficient_of_variation": cv_selected,
                "landmark_shift_px_stats": describe(coord_shifts_px),
                "inter_examiner_reliability": {
                    "sufficient": False,
                    "n": 0,
                    "reason": "Dual-examiner repeated independent annotations are required to compute inter-examiner ICC; current protocol has single-examiner review enabled.",
                },
                "intra_examiner_reliability": {
                    "sufficient": False,
                    "n": 0,
                    "reason": "Paired blinded repeat sessions by the same examiner are required to compute intra-examiner ICC.",
                },
            },
            "measurement_definitions": [
                {"code": d.code, "name": d.name, "unit": d.unit} for d in m_defs
            ],
            "measurement_summaries": measurement_summaries,
        }
    )
