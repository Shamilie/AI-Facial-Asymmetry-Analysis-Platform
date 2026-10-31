"""
Research Overview Dashboard endpoint (Page 2).

Computes all KPI cards, enrollment chart, follow-up completion chart, recent
patients, upcoming visits, AI processing status, recent activity, and pending
examiner reviews directly from live database tables.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import P
from app.core.responses import ok
from app.core.security import require_permissions
from app.models.ai import AIJob, AIJobStatusEnum
from app.models.audit import AuditLog
from app.models.measurement import Measurement, MeasurementStatusEnum
from app.models.patient import Patient, StudyStatusEnum
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_user: Any = Depends(require_permissions(P.PATIENT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    p_stmt = (
        select(Patient)
        .where(Patient.is_deleted.is_(False))
        .options(
            selectinload(Patient.fracture_detail),
            selectinload(Patient.surgery_detail),
            selectinload(Patient.visits),
        )
        .order_by(Patient.created_at.desc())
    )
    if date_from:
        p_stmt = p_stmt.where(Patient.enrollment_date >= date_from)
    if date_to:
        p_stmt = p_stmt.where(Patient.enrollment_date <= date_to)

    patients = list((await db.execute(p_stmt)).scalars().all())
    patient_ids = {p.id for p in patients}

    all_visits = [v for p in patients for v in p.visits]
    jobs = list(
        (await db.execute(select(AIJob).order_by(AIJob.created_at.desc()).limit(250))).scalars().all()
    )
    jobs = [j for j in jobs if not patient_ids or j.patient_id in patient_ids]

    ms = list(
        (await db.execute(select(Measurement).where(Measurement.is_current.is_(True)))).scalars().all()
    )

    total_patients = len(patients)
    active_patients = sum(
        1 for p in patients if p.study_status in (StudyStatusEnum.ACTIVE, StudyStatusEnum.ENROLLED)
    )
    completed_followups = sum(1 for v in all_visits if v.status == VisitStatusEnum.COMPLETED)
    pending_followups = sum(
        1
        for v in all_visits
        if v.status in (VisitStatusEnum.PLANNED, VisitStatusEnum.SCHEDULED, VisitStatusEnum.IMAGES_PENDING, VisitStatusEnum.IN_PROGRESS)
    )
    ai_completed = sum(
        1 for j in jobs if j.status in (AIJobStatusEnum.COMPLETED, AIJobStatusEnum.VALIDATED, AIJobStatusEnum.REVIEW_REQUIRED)
    )
    requiring_review = sum(1 for v in all_visits if v.status == VisitStatusEnum.REVIEW_REQUIRED) + sum(
        1 for m in ms if m.status == MeasurementStatusEnum.REVIEW_REQUIRED
    )

    # 1. Patient enrollment chart (by month)
    month_counts: Counter[str] = Counter()
    for p in patients:
        dt = p.enrollment_date or p.created_at.date()
        month_counts[dt.strftime("%Y-%m")] += 1
    enrollment_chart = [
        {"month": m, "patients": c} for m, c in sorted(month_counts.items())
    ]

    # 2. Follow-up completion chart by visit stage
    visit_order = [
        (VisitTypeEnum.PRE_OPERATIVE, "Pre-op"),
        (VisitTypeEnum.POST_OP_1_WEEK, "1 Week"),
        (VisitTypeEnum.POST_OP_6_WEEKS, "6 Weeks"),
        (VisitTypeEnum.POST_OP_3_MONTHS, "3 Months"),
        (VisitTypeEnum.POST_OP_6_MONTHS, "6 Months"),
    ]
    followup_chart = []
    for vtype, label in visit_order:
        vlist = [v for v in all_visits if v.visit_type == vtype]
        followup_chart.append(
            {
                "stage": label,
                "visit_type": vtype.value,
                "completed": sum(1 for v in vlist if v.status == VisitStatusEnum.COMPLETED),
                "review_required": sum(1 for v in vlist if v.status == VisitStatusEnum.REVIEW_REQUIRED),
                "pending": sum(
                    1
                    for v in vlist
                    if v.status not in (VisitStatusEnum.COMPLETED, VisitStatusEnum.REVIEW_REQUIRED, VisitStatusEnum.CANCELLED)
                ),
            }
        )

    # 3. Recent patients
    recent_patients = []
    for p in patients[:6]:
        done_v = sum(1 for v in p.visits if v.status == VisitStatusEnum.COMPLETED)
        rev_v = sum(1 for v in p.visits if v.status == VisitStatusEnum.REVIEW_REQUIRED)
        recent_patients.append(
            {
                "id": str(p.id),
                "patient_code": p.patient_code,
                "fracture_side": p.fracture_detail.fracture_side.value if p.fracture_detail and p.fracture_detail.fracture_side else "N/A",
                "fracture_classification": p.fracture_detail.fracture_classification if p.fracture_detail else "N/A",
                "surgery_date": p.surgery_detail.surgery_date.isoformat() if p.surgery_detail and p.surgery_detail.surgery_date else None,
                "enrollment_date": p.enrollment_date.isoformat() if p.enrollment_date else None,
                "study_status": p.study_status.value,
                "completed_visits": done_v,
                "total_visits": len(p.visits),
                "analysis_status": "ReviewRequired" if rev_v else ("Completed" if done_v else "Pending"),
                "is_synthetic": p.is_synthetic,
            }
        )

    # 4. Upcoming follow-up visits
    p_by_id = {p.id: p for p in patients}
    upcoming_visits = []
    for v in sorted(
        [
            v
            for v in all_visits
            if v.status in (VisitStatusEnum.SCHEDULED, VisitStatusEnum.PLANNED, VisitStatusEnum.IMAGES_PENDING)
        ],
        key=lambda x: x.planned_date or date.max,
    )[:8]:
        pat = p_by_id.get(v.patient_id)
        upcoming_visits.append(
            {
                "visit_id": str(v.id),
                "patient_id": str(v.patient_id),
                "patient_code": pat.patient_code if pat else "Unknown",
                "visit_type": v.visit_type.value,
                "planned_date": v.planned_date.isoformat() if v.planned_date else None,
                "status": v.status.value,
            }
        )

    # 5. AI processing status breakdown
    ai_status_counts = Counter(j.status.value for j in jobs)
    ai_processing_status = [
        {"status": st, "count": cnt} for st, cnt in sorted(ai_status_counts.items())
    ]

    # 6. Pending examiner reviews
    pending_reviews = []
    for v in [v for v in all_visits if v.status == VisitStatusEnum.REVIEW_REQUIRED][:8]:
        pat = p_by_id.get(v.patient_id)
        pending_reviews.append(
            {
                "visit_id": str(v.id),
                "patient_id": str(v.patient_id),
                "patient_code": pat.patient_code if pat else "Unknown",
                "visit_type": v.visit_type.value,
                "actual_date": v.actual_date.isoformat() if v.actual_date else None,
                "status": v.status.value,
            }
        )

    # 7. Recent audit activity
    audits = list(
        (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10))).scalars().all()
    )
    recent_activity = [
        {
            "id": str(a.id),
            "action": a.action,
            "resource_type": a.resource_type,
            "user_email": a.user.email if a.user else "system",
            "reason": a.reason,
            "created_at": a.created_at.isoformat(),
        }
        for a in audits
    ]

    return ok(
        {
            "kpis": {
                "total_patients": total_patients,
                "active_patients": active_patients,
                "completed_follow_ups": completed_followups,
                "pending_follow_ups": pending_followups,
                "ai_analyses_completed": ai_completed,
                "analyses_requiring_review": requiring_review,
            },
            "enrollment_chart": enrollment_chart,
            "follow_up_completion_chart": followup_chart,
            "recent_patients": recent_patients,
            "upcoming_visits": upcoming_visits,
            "ai_processing_status": ai_processing_status,
            "pending_examiner_reviews": pending_reviews,
            "recent_activity": recent_activity,
        }
    )
