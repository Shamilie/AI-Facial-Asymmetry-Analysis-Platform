"""
Role and permission catalogue.

Authorization is enforced in the backend through ``require_permissions``.
The frontend only *mirrors* these permissions to shape navigation.
"""

from __future__ import annotations


class P:
    """Permission names (resource:action)."""

    PATIENT_READ = "patient:read"
    PATIENT_WRITE = "patient:write"
    PATIENT_EXPORT = "patient:export"
    PATIENT_IDENTIFIERS = "patient:identifiers"  # may view hospital IDs / DOB
    VISIT_READ = "visit:read"
    VISIT_WRITE = "visit:write"
    IMAGE_UPLOAD = "image:upload"
    IMAGE_DELETE = "image:delete"
    IMAGE_REVIEW = "image:review"
    AI_RUN = "ai:run"
    AI_MANAGE = "ai:manage"
    LANDMARK_REVIEW = "landmark:review"
    LANDMARK_APPROVE = "landmark:approve"
    CALIBRATION_WRITE = "calibration:write"
    MEASUREMENT_READ = "measurement:read"
    MEASUREMENT_CALCULATE = "measurement:calculate"
    MEASUREMENT_APPROVE = "measurement:approve"
    REPORT_GENERATE = "report:generate"
    REPORT_EXPORT = "report:export"
    ANALYTICS_READ = "analytics:read"
    CONFIG_MANAGE = "config:manage"
    PROTOCOL_MANAGE = "protocol:manage"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"


ALL_PERMISSIONS: dict[str, str] = {
    P.PATIENT_READ: "View coded patient records",
    P.PATIENT_WRITE: "Create and update patient records",
    P.PATIENT_EXPORT: "Export authorized patient listings",
    P.PATIENT_IDENTIFIERS: "View protocol-permitted identifiers (hospital ID, DOB)",
    P.VISIT_READ: "View study visits",
    P.VISIT_WRITE: "Create and update study visits",
    P.IMAGE_UPLOAD: "Upload visit images",
    P.IMAGE_DELETE: "Delete visit images",
    P.IMAGE_REVIEW: "Accept / reject image quality",
    P.AI_RUN: "Start AI analysis",
    P.AI_MANAGE: "Retry, cancel and inspect AI jobs",
    P.LANDMARK_REVIEW: "Review and correct landmarks",
    P.LANDMARK_APPROVE: "Approve reviewed landmarks",
    P.CALIBRATION_WRITE: "Create calibration records",
    P.MEASUREMENT_READ: "View measurements",
    P.MEASUREMENT_CALCULATE: "Run measurement calculations",
    P.MEASUREMENT_APPROVE: "Approve / reject measurements",
    P.REPORT_GENERATE: "Generate reports",
    P.REPORT_EXPORT: "Download / export reports and data",
    P.ANALYTICS_READ: "View research analytics",
    P.CONFIG_MANAGE: "Manage AI provider configuration",
    P.PROTOCOL_MANAGE: "Manage research protocol",
    P.USER_MANAGE: "Manage users and roles",
    P.AUDIT_READ: "View audit logs",
}


class R:
    ADMIN = "System Administrator"
    PI = "Principal Investigator"
    COORDINATOR = "Research Coordinator"
    EXAMINER = "Clinician / Examiner"
    ANALYST = "Research Analyst"
    READONLY = "Read-only Researcher"


ROLE_PERMISSIONS: dict[str, set[str]] = {
    R.ADMIN: set(ALL_PERMISSIONS),
    R.PI: set(ALL_PERMISSIONS) - {P.USER_MANAGE, P.CONFIG_MANAGE},
    R.COORDINATOR: {
        P.PATIENT_READ, P.PATIENT_WRITE, P.PATIENT_EXPORT, P.PATIENT_IDENTIFIERS,
        P.VISIT_READ, P.VISIT_WRITE, P.IMAGE_UPLOAD, P.IMAGE_DELETE, P.IMAGE_REVIEW,
        P.AI_RUN, P.LANDMARK_REVIEW, P.CALIBRATION_WRITE, P.MEASUREMENT_READ,
        P.MEASUREMENT_CALCULATE, P.REPORT_GENERATE, P.REPORT_EXPORT, P.ANALYTICS_READ,
    },
    R.EXAMINER: {
        P.PATIENT_READ, P.VISIT_READ, P.VISIT_WRITE, P.IMAGE_UPLOAD, P.IMAGE_REVIEW,
        P.AI_RUN, P.LANDMARK_REVIEW, P.LANDMARK_APPROVE, P.CALIBRATION_WRITE,
        P.MEASUREMENT_READ, P.MEASUREMENT_CALCULATE, P.MEASUREMENT_APPROVE,
        P.REPORT_GENERATE, P.REPORT_EXPORT, P.ANALYTICS_READ,
    },
    R.ANALYST: {
        P.PATIENT_READ, P.VISIT_READ, P.MEASUREMENT_READ, P.ANALYTICS_READ,
        P.REPORT_GENERATE, P.REPORT_EXPORT, P.PATIENT_EXPORT,
    },
    R.READONLY: {P.PATIENT_READ, P.VISIT_READ, P.MEASUREMENT_READ, P.ANALYTICS_READ},
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    R.ADMIN: "Full system administration including users, AI configuration and audit.",
    R.PI: "Study oversight, protocol management, approvals and audit review.",
    R.COORDINATOR: "Patient enrollment, visit scheduling, image acquisition and analysis runs.",
    R.EXAMINER: "Landmark review, calibration, measurement review and approval.",
    R.ANALYST: "Research analytics and data exports.",
    R.READONLY: "Read-only access to coded research records.",
}
