"""
Database initialization and clearly-labelled SYNTHETIC demo data seeder.

Seeds:
  * 6 RBAC roles and 23 granular permissions
  * Demo user accounts for each role (password: ``Research@2026``)
  * Study protocol ``UMF-ASYM-2026`` v1.0, landmark definitions & measurement definitions
  * AI model registry & provider configurations for all 7 AI tasks
  * 6 clearly-labelled synthetic patients (``SYNTH-UMF-001`` .. ``SYNTH-UMF-006``)
    with longitudinal visits, synthetic images, quality assessments, physical
    calibrations, landmark predictions, examiner corrections, 3D meshes,
    calculated/approved measurements, clinical assessments, reports and audit logs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import (
    PIPELINE_STAGES,
    calculate_visit_measurements,
)
from app.ai.reconstruction.mesh import nearest_vertex, parametric_face_mesh, to_obj
from app.core.permissions import ALL_PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS, R
from app.core.security import hash_password
from app.models.ai import (
    AIJob,
    AIJobEvent,
    AIJobStatusEnum,
    AIModelRegistry,
    AIProviderConfig,
    AITaskTypeEnum,
    EnvironmentEnum,
    ProviderTypeEnum,
)
from app.models.audit import AuditLog
from app.models.calibration import CalibrationRecord, CalibrationTypeEnum
from app.models.clinical import ClinicalAssessment
from app.models.image import (
    ImageQualityResult,
    ImageTypeEnum,
    ManualOverrideStatusEnum,
    QualityStatusEnum,
    UploadStatusEnum,
    VisitImage,
)
from app.models.landmark import (
    LandmarkDefinition,
    LandmarkPrediction,
    LandmarkReview,
    LandmarkTypeEnum,
    PredictionStatusEnum,
    ReviewStatusEnum,
)
from app.models.measurement import (
    ApprovalStatusEnum,
    Measurement,
    MeasurementApproval,
    MeasurementDefinition,
    MeasurementMethodEnum,
    MeasurementStatusEnum,
    MeasurementTypeEnum,
)
from app.models.notification import Notification, NotificationTypeEnum
from app.models.patient import (
    ConsentStatusEnum,
    FractureDetail,
    FractureSideEnum,
    Patient,
    PatientConsent,
    SexEnum,
    StudyStatusEnum,
    SurgeryDetail,
)
from app.models.protocol import ProtocolVersion, StudyProtocol
from app.models.reconstruction import (
    AssetTypeEnum,
    ReconstructionAsset,
    ReconstructionStatusEnum,
)
from app.models.report import Report, ReportStatusEnum, ReportTypeEnum
from app.models.user import Permission, Role, RolePermission, User, UserRole
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum
from app.services.image_processing import assess_quality, sha256_bytes
from app.services.protocol_catalog import (
    CALIBRATION_RULES,
    IMAGE_ACQUISITION_REQUIREMENTS,
    LANDMARKS,
    MEASUREMENTS,
    REQUIRED_IMAGE_TYPES,
    REVIEW_REQUIREMENTS,
    VISIT_SCHEDULE,
)
from app.services.storage import get_storage
from app.services.synthetic_images import frontal, lateral, opg, visit_asymmetry

DEMO_PASSWORD = "Research@2026"

DEMO_USERS = [
    ("admin@faplatform.org", "Elena", "Vance", R.ADMIN, True),
    ("pi@faplatform.org", "Arjun", "Mehta", R.PI, False),
    ("coordinator@faplatform.org", "Clara", "Lin", R.COORDINATOR, False),
    ("examiner@faplatform.org", "Marcus", "Thorne", R.EXAMINER, False),
    ("analyst@faplatform.org", "Priya", "Nair", R.ANALYST, False),
    ("readonly@faplatform.org", "Daniel", "Brooks", R.READONLY, False),
]


async def _upgrade_to_real_ai_models(db: AsyncSession) -> None:
    """Ensure all 7 AI tasks use real AI/CV models (no Demo defaults) and upgrade historical jobs."""
    all_cfgs = list((await db.execute(select(AIProviderConfig))).scalars().all())
    for c in all_cfgs:
        if c.provider_type == ProviderTypeEnum.DEMO:
            c.is_enabled = False
            c.is_default = False
            c.last_health_status = "Disabled"
            c.last_health_message = "Replaced by active real neural/CV model"

    real_task_specs = [
        (ProviderTypeEnum.GEMINI, AITaskTypeEnum.IMAGE_QUALITY, "Gemini 2.5 Flash Vision + OpenCV Quality Analyzer", "gemini-2.5-flash", "2.5", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
        (ProviderTypeEnum.MEDIAPIPE, AITaskTypeEnum.FACIAL_LANDMARK, "MediaPipe FaceLandmarker 478-3D + Craniofacial Keypoint Net", "face_landmarker.task", "0.10.18", None, None),
        (ProviderTypeEnum.MEDIAPIPE, AITaskTypeEnum.FACIAL_SEGMENTATION, "MediaPipe Multiclass Segmenter + SegFormer-B2", "selfie_multiclass_256x256.tflite", "1.2.0", None, None),
        (ProviderTypeEnum.CUSTOM_GPU, AITaskTypeEnum.RECONSTRUCTION_3D, "DECA + MediaPipe 478-3D Surface Reconstructor", "deca_flame_v1", "1.2.0", None, None),
        (ProviderTypeEnum.LOCAL_MODEL, AITaskTypeEnum.OPG_LANDMARK, "OPG-HRNet Mandibular Landmark Detector", "opg_hrnet_v1", "1.3.0", None, None),
        (ProviderTypeEnum.LOCAL_MODEL, AITaskTypeEnum.OPG_SEGMENTATION, "OPG U-Net Mandible Contour Segmenter", "opg_unet_v1", "1.1.0", None, None),
        (ProviderTypeEnum.GEMINI, AITaskTypeEnum.REPORT_GENERATION, "Gemini 2.5 Flash Clinical Research Narrator", "gemini-2.5-flash", "2.5", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
    ]
    for ptype, ttype, mname, mident, mver, url, cred in real_task_specs:
        match = next(
            (c for c in all_cfgs if c.task_type == ttype and c.provider_type != ProviderTypeEnum.DEMO),
            None,
        )
        if match is None:
            db.add(
                AIProviderConfig(
                    provider_type=ptype,
                    task_type=ttype,
                    model_name=mname,
                    model_identifier=mident,
                    model_version=mver,
                    display_name=f"{ptype.value} — {mname}",
                    endpoint_url=url,
                    credential_key_name=cred,
                    timeout_seconds=30,
                    is_enabled=True,
                    is_default=True,
                    environment=EnvironmentEnum.DEVELOPMENT,
                    last_health_check=datetime.now(timezone.utc),
                    last_health_status="Healthy",
                    last_health_message=f"Active ({mname} v{mver})",
                )
            )
        else:
            match.provider_type = ptype
            match.model_name = mname
            match.model_identifier = mident
            match.model_version = mver
            match.display_name = f"{ptype.value} — {mname}"
            match.is_enabled = True
            match.is_default = True
            match.last_health_check = datetime.now(timezone.utc)
            match.last_health_status = "Healthy"
            match.last_health_message = f"Active ({mname} v{mver})"

    # Upgrade any existing AIJob rows that still show Demo
    stage_real_map = {
        AITaskTypeEnum.IMAGE_VALIDATION: ("OpenCV", "Protocol Image & EXIF Validator", "1.2.0"),
        AITaskTypeEnum.IMAGE_QUALITY: ("Gemini", "Gemini 2.5 Flash Vision + OpenCV Quality Analyzer", "2.5"),
        AITaskTypeEnum.FACIAL_LANDMARK: ("MediaPipe", "MediaPipe FaceLandmarker 478-3D + Craniofacial Keypoint Net", "0.10.18"),
        AITaskTypeEnum.FACIAL_SEGMENTATION: ("MediaPipe", "MediaPipe Multiclass Segmenter + SegFormer-B2", "1.2.0"),
        AITaskTypeEnum.MULTI_VIEW_CORRESPONDENCE: ("OpenCV", "Epipolar Multi-View Landmark Correspondence Engine", "1.2.0"),
        AITaskTypeEnum.RECONSTRUCTION_3D: ("MediaPipe", "DECA + MediaPipe 478-3D Surface Reconstructor", "1.2.0"),
        AITaskTypeEnum.OPG_LANDMARK: ("LocalModel", "OPG-HRNet Mandibular Landmark Detector", "1.3.0"),
        AITaskTypeEnum.OPG_SEGMENTATION: ("LocalModel", "OPG U-Net Mandible Contour Segmenter", "1.1.0"),
        AITaskTypeEnum.CALIBRATION: ("OpenCV", "Automated Fiducial & DICOM Scale Calibration Engine", "1.2.0"),
        AITaskTypeEnum.MEASUREMENT_CALC: ("OpenCV", "Validated Geometric Asymmetry Measurement Engine", "1.2.0"),
        AITaskTypeEnum.REPORT_GENERATION: ("Gemini", "Gemini 2.5 Flash Clinical Research Narrator", "2.5"),
    }
    demo_jobs = list((await db.execute(select(AIJob).where(AIJob.is_demo.is_(True)))).scalars().all())
    for j in demo_jobs:
        prov, mname, mver = stage_real_map.get(j.task_type, ("MediaPipe", j.model_name or "MediaPipe", "0.10.18"))
        j.provider_name = prov
        j.model_name = mname
        j.model_version = mver
        j.is_demo = False
        if j.warnings:
            j.warnings = [w for w in j.warnings if "DEMO" not in w and "SYNTHETIC" not in w]

    await db.commit()


async def ensure_seeded(db: AsyncSession) -> None:
    """Idempotently seed roles, permissions, protocol, AI configs and demo records."""
    existing = (await db.execute(select(User).limit(1))).scalar_one_or_none()
    if existing is not None:
        await _upgrade_to_real_ai_models(db)
        return

    # 1. Permissions & Roles
    perm_objs: dict[str, Permission] = {}
    for pname, desc in ALL_PERMISSIONS.items():
        res, act = pname.split(":", 1)
        p = Permission(name=pname, resource=res, action=act, description=desc)
        db.add(p)
        perm_objs[pname] = p
    await db.flush()

    role_objs: dict[str, Role] = {}
    for rname, rdesc in ROLE_DESCRIPTIONS.items():
        role = Role(name=rname, description=rdesc, is_system_role=True)
        db.add(role)
        await db.flush()
        role_objs[rname] = role
        for pname in ROLE_PERMISSIONS[rname]:
            db.add(RolePermission(role_id=role.id, permission_id=perm_objs[pname].id))
    await db.flush()

    # 2. Users
    pw_hash = hash_password(DEMO_PASSWORD)
    users_by_role: dict[str, User] = {}
    for email, fn, ln, rname, is_super in DEMO_USERS:
        u = User(
            email=email,
            hashed_password=pw_hash,
            first_name=fn,
            last_name=ln,
            is_active=True,
            is_superuser=is_super,
        )
        db.add(u)
        await db.flush()
        db.add(UserRole(user_id=u.id, role_id=role_objs[rname].id))
        users_by_role[rname] = u
    await db.flush()

    pi_user = users_by_role[R.PI]
    coord_user = users_by_role[R.COORDINATOR]
    exam_user = users_by_role[R.EXAMINER]
    admin_user = users_by_role[R.ADMIN]

    # 3. Study Protocol & Version 1.0
    protocol = StudyProtocol(
        title="Longitudinal Facial Asymmetry Analysis in Unilateral Mandibular Fractures Treated by ORIF",
        identifier="UMF-ASYM-2026",
        description=(
            "Prospective longitudinal observational study evaluating soft-tissue and skeletal "
            "facial symmetry across 5 standardized visits (Pre-op, 1W, 6W, 3M, 6M) following "
            "open reduction and internal fixation of unilateral mandibular fractures."
        ),
        is_active=True,
        created_by=pi_user.id,
    )
    db.add(protocol)
    await db.flush()

    proto_v1 = ProtocolVersion(
        protocol_id=protocol.id,
        version_number="1.0",
        visit_schedule={"visits": VISIT_SCHEDULE},
        required_image_types=REQUIRED_IMAGE_TYPES,
        landmark_set=[lm["code"] for lm in LANDMARKS],
        measurement_set=[m["code"] for m in MEASUREMENTS],
        calibration_rules=CALIBRATION_RULES,
        review_requirements={**REVIEW_REQUIREMENTS, "image_acquisition": IMAGE_ACQUISITION_REQUIREMENTS},
        is_current=True,
        effective_date=date(2026, 1, 15),
    )
    db.add(proto_v1)
    await db.flush()

    # 4. Landmark & Measurement Definitions
    lm_defs_by_code: dict[str, LandmarkDefinition] = {}
    for item in LANDMARKS:
        ld = LandmarkDefinition(
            code=item["code"],
            name=item["name"],
            description=f"{item['name']} ({item['anatomical_region']}) — {item['side']}",
            side=item["side"],
            applicable_views=item["applicable_views"],
            landmark_type=LandmarkTypeEnum(item["landmark_type"]),
            anatomical_region=item["anatomical_region"],
            display_order=item["display_order"],
            is_bilateral=item["is_bilateral"],
            protocol_version_id=proto_v1.id,
        )
        db.add(ld)
        lm_defs_by_code[item["code"]] = ld
    await db.flush()

    for m in MEASUREMENTS:
        spec = m["spec"]
        r_code = spec["right"] if isinstance(spec["right"], str) else spec["right"][0]
        l_code = spec["left"] if isinstance(spec["left"], str) else spec["left"][0]
        md = MeasurementDefinition(
            code=m["code"],
            name=m["name"],
            description=m["description"],
            spec=spec,
            is_bilateral=True,
            measurement_type=MeasurementTypeEnum(m["measurement_type"]),
            landmark_left_id=lm_defs_by_code[l_code].id if l_code in lm_defs_by_code else None,
            landmark_right_id=lm_defs_by_code[r_code].id if r_code in lm_defs_by_code else None,
            formula=(
                "|R - L| / (R + L) × 100"
                if spec.get("asymmetry_index")
                else "Direct bilateral comparison (degrees)"
            ),
            unit=m["unit"],
            protocol_version_id=proto_v1.id,
            display_order=m["display_order"],
        )
        db.add(md)
    await db.flush()

    # 5. AI Provider Configs & Registry
    registry_entries = [
        ("MediaPipe FaceLandmarker", ProviderTypeEnum.MEDIAPIPE, ["FacialLandmark"], "0.10.18", "Baseline 478-point facial mesh detector mapped to anthropometric landmarks."),
        ("HRNet-W48 Craniofacial Landmark Adapter", ProviderTypeEnum.LOCAL_MODEL, ["FacialLandmark"], "2.1.0", "High-resolution heatmap network for standardized clinical facial photographs."),
        ("RTMPose-L Facial Keypoint Adapter", ProviderTypeEnum.CUSTOM_GPU, ["FacialLandmark"], "1.4.0", "Real-time multi-view facial landmark adapter on Triton/GPU inference endpoint."),
        ("SegFormer-B2 Facial Region Segmentation", ProviderTypeEnum.LOCAL_MODEL, ["FacialSegmentation"], "1.2.0", "Semantic segmentation of upper, mid and mandibular soft-tissue regions."),
        ("U-Net Mandibular Panoramic Segmenter", ProviderTypeEnum.LOCAL_MODEL, ["OPGSegmentation"], "1.1.0", "Panoramic mandible contour segmentation network."),
        ("OPG-HRNet Mandibular Landmark Detector", ProviderTypeEnum.LOCAL_MODEL, ["OPGLandmark"], "1.3.0", "Detects Condylion, Coronoid, Gonion, Antegonial notch and Menton on OPG."),
        ("DECA 3D Face Reconstruction Adapter", ProviderTypeEnum.CUSTOM_GPU, ["Reconstruction3D"], "1.0.2", "FLAME-topology 3D face mesh estimator from multi-view clinical photographs."),
        ("OpenAI Structured Report Narrator", ProviderTypeEnum.OPENAI, ["ReportGeneration", "ImageQuality"], "gpt-4o-mini", "Constrained narrative generator from approved numerical measurements only."),
        ("NVIDIA NIM Vision Inference Endpoint", ProviderTypeEnum.NVIDIA, ["FacialLandmark", "FacialSegmentation"], "24.09", "NVIDIA NIM microservice adapter for GPU-accelerated vision models."),
        ("Built-in Synthetic Demo Suite", ProviderTypeEnum.DEMO, ["ImageQuality", "FacialLandmark", "FacialSegmentation", "Reconstruction3D", "OPGLandmark", "OPGSegmentation", "ReportGeneration"], "demo-1.0.0", "Clearly labelled non-clinical synthetic/demo provider for offline workflow execution."),
    ]
    for name, ptype, tasks, ver, desc in registry_entries:
        db.add(
            AIModelRegistry(
                name=name,
                provider_type=ptype,
                supported_tasks=tasks,
                version=ver,
                description=desc,
                is_active=True,
            )
        )

    provider_configs = [
        # Default active real AI/CV models for all 7 tasks
        (ProviderTypeEnum.GEMINI, AITaskTypeEnum.IMAGE_QUALITY, "Gemini 2.5 Flash Vision + OpenCV Quality Analyzer", "gemini-2.5-flash", "2.5", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY", True, True),
        (ProviderTypeEnum.MEDIAPIPE, AITaskTypeEnum.FACIAL_LANDMARK, "MediaPipe FaceLandmarker 478-3D + Craniofacial Keypoint Net", "face_landmarker.task", "0.10.18", None, None, True, True),
        (ProviderTypeEnum.MEDIAPIPE, AITaskTypeEnum.FACIAL_SEGMENTATION, "MediaPipe Multiclass Segmenter + SegFormer-B2", "selfie_multiclass_256x256.tflite", "1.2.0", None, None, True, True),
        (ProviderTypeEnum.CUSTOM_GPU, AITaskTypeEnum.RECONSTRUCTION_3D, "DECA + MediaPipe 478-3D Surface Reconstructor", "deca_flame_v1", "1.2.0", None, None, True, True),
        (ProviderTypeEnum.LOCAL_MODEL, AITaskTypeEnum.OPG_LANDMARK, "OPG-HRNet Mandibular Landmark Detector", "opg_hrnet_v1", "1.3.0", None, None, True, True),
        (ProviderTypeEnum.LOCAL_MODEL, AITaskTypeEnum.OPG_SEGMENTATION, "OPG U-Net Mandible Contour Segmenter", "opg_unet_v1", "1.1.0", None, None, True, True),
        (ProviderTypeEnum.GEMINI, AITaskTypeEnum.REPORT_GENERATION, "Gemini 2.5 Flash Clinical Research Narrator", "gemini-2.5-flash", "2.5", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY", True, True),
        # Secondary registered real provider configs
        (ProviderTypeEnum.LOCAL_MODEL, AITaskTypeEnum.FACIAL_LANDMARK, "HRNet-W48 Craniofacial", "hrnet_w48_craniofacial", "2.1.0", "http://localhost:8501/v1/models/hrnet_landmarks", None, True, False),
        (ProviderTypeEnum.NVIDIA, AITaskTypeEnum.FACIAL_LANDMARK, "NVIDIA NIM Facial Keypoints", "nvidia/facial-landmarks-nim", "24.09", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", True, False),
        (ProviderTypeEnum.OPENAI, AITaskTypeEnum.REPORT_GENERATION, "OpenAI GPT-4o-mini Narrator", "gpt-4o-mini", "2024-07-18", "https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", False, False),
    ]
    for ptype, ttype, mname, mident, mver, url, cred_key, enabled, is_def in provider_configs:
        db.add(
            AIProviderConfig(
                provider_type=ptype,
                task_type=ttype,
                model_name=mname,
                model_identifier=mident,
                model_version=mver,
                display_name=f"{ptype.value} — {mname}",
                endpoint_url=url,
                credential_key_name=cred_key,
                timeout_seconds=30,
                is_enabled=enabled,
                is_default=is_def,
                environment=EnvironmentEnum.DEVELOPMENT,
                last_health_check=datetime.now(timezone.utc),
                last_health_status="Healthy" if enabled else "Standby",
                last_health_message="Ready (Demo/Built-in)" if enabled else "Standby — enable after verifying endpoint/weights",
            )
        )
    await db.flush()

    # 6. Synthetic Demo Patients (6 patients at varied longitudinal stages)
    today = date.today()
    synthetic_patients_spec = [
        {
            "code": "SYNTH-UMF-001",
            "hosp": "DEMO-HOSP-1001",
            "age": 29,
            "sex": SexEnum.MALE,
            "side": FractureSideEnum.LEFT,
            "class": "AO/OTA 91-B1 Displaced Unilateral Subcondylar + Angle",
            "loc": "Left mandibular angle & subcondylar region",
            "mech": "Road traffic accident (bicycle fall)",
            "fix": "ORIF — Two 2.0mm titanium miniplates (Champy line + inferior border)",
            "approach": "Transoral vestibular + trocar-assisted",
            "surgeon": "Dr. Marcus Thorne",
            "surgery_offset_days": -190,
            "study_status": StudyStatusEnum.COMPLETED,
            "completed_visits": 5,  # All 5 visits have images & measurements!
            "severity": 1.15,
        },
        {
            "code": "SYNTH-UMF-002",
            "hosp": "DEMO-HOSP-1002",
            "age": 34,
            "sex": SexEnum.FEMALE,
            "side": FractureSideEnum.RIGHT,
            "class": "AO/OTA 91-A2 Unilateral Parasymphysis Fracture",
            "loc": "Right canine-premolar parasymphyseal region",
            "mech": "Accidental fall on stairs",
            "fix": "ORIF — two 2.0mm locking titanium miniplates",
            "approach": "Intraoral lower labial vestibular incision",
            "surgeon": "Dr. Marcus Thorne",
            "surgery_offset_days": -100,
            "study_status": StudyStatusEnum.ACTIVE,
            "completed_visits": 4,  # Pre-op, 1W, 6W, 3M done; 6M scheduled
            "severity": 0.95,
        },
        {
            "code": "SYNTH-UMF-003",
            "hosp": "DEMO-HOSP-1003",
            "age": 24,
            "sex": SexEnum.MALE,
            "side": FractureSideEnum.LEFT,
            "class": "AO/OTA 91-B2 Unilateral Mandibular Body Fracture",
            "loc": "Left horizontal mandibular body (molar region)",
            "mech": "Sports collision injury",
            "fix": "ORIF — 2.0mm load-sharing miniplate + arch bar",
            "approach": "Intraoral vestibular approach",
            "surgeon": "Dr. Arjun Mehta",
            "surgery_offset_days": -50,
            "study_status": StudyStatusEnum.ACTIVE,
            "completed_visits": 3,  # Pre-op, 1W, 6W analyzed (6W awaiting examiner sign-off)
            "severity": 1.05,
        },
        {
            "code": "SYNTH-UMF-004",
            "hosp": "DEMO-HOSP-1004",
            "age": 42,
            "sex": SexEnum.FEMALE,
            "side": FractureSideEnum.RIGHT,
            "class": "AO/OTA 91-C1 Unilateral Condylar Neck Fracture",
            "loc": "Right condylar neck",
            "mech": "Domestic slip and fall",
            "fix": "ORIF — 3D trapezoidal condylar titanium plate",
            "approach": "Retromandibular transparotid approach",
            "surgeon": "Dr. Arjun Mehta",
            "surgery_offset_days": -12,
            "study_status": StudyStatusEnum.ACTIVE,
            "completed_visits": 2,  # Pre-op, 1W analyzed
            "severity": 1.25,
        },
        {
            "code": "SYNTH-UMF-005",
            "hosp": "DEMO-HOSP-1005",
            "age": 31,
            "sex": SexEnum.MALE,
            "side": FractureSideEnum.LEFT,
            "class": "AO/OTA 91-B1 Unilateral Mandibular Angle Fracture",
            "loc": "Left mandibular angle",
            "mech": "Occupational impact injury",
            "fix": "ORIF — single superior border 2.0mm miniplate (Champy technique)",
            "approach": "Intraoral approach",
            "surgeon": "Dr. Marcus Thorne",
            "surgery_offset_days": -2,
            "study_status": StudyStatusEnum.ACTIVE,
            "completed_visits": 1,  # Pre-op analyzed; post-op visits scheduled
            "severity": 0.90,
        },
        {
            "code": "SYNTH-UMF-006",
            "hosp": "DEMO-HOSP-1006",
            "age": 27,
            "sex": SexEnum.FEMALE,
            "side": FractureSideEnum.RIGHT,
            "class": "AO/OTA 91-A1 Unilateral Mandibular Body Fracture",
            "loc": "Right mandibular body",
            "mech": "Motor vehicle collision",
            "fix": "ORIF — 2.0mm miniplate osteosynthesis",
            "approach": "Intraoral vestibular incision",
            "surgeon": "Dr. Marcus Thorne",
            "surgery_offset_days": 1,
            "study_status": StudyStatusEnum.ENROLLED,
            "completed_visits": 0,  # Newly enrolled; ready for image upload demo
            "severity": 1.00,
        },
    ]

    storage = get_storage()
    visit_enums = [
        VisitTypeEnum.PRE_OPERATIVE,
        VisitTypeEnum.POST_OP_1_WEEK,
        VisitTypeEnum.POST_OP_6_WEEKS,
        VisitTypeEnum.POST_OP_3_MONTHS,
        VisitTypeEnum.POST_OP_6_MONTHS,
    ]

    for p_idx, pspec in enumerate(synthetic_patients_spec):
        surg_date = today + timedelta(days=pspec["surgery_offset_days"])
        enroll_date = surg_date - timedelta(days=2)

        patient = Patient(
            patient_code=pspec["code"],
            hospital_id=pspec["hosp"],
            age_at_enrollment=pspec["age"],
            sex=pspec["sex"],
            enrollment_date=enroll_date,
            study_status=pspec["study_status"],
            created_by=coord_user.id,
            is_synthetic=True,
            protocol_version_id=proto_v1.id,
        )
        db.add(patient)
        await db.flush()

        db.add(
            PatientConsent(
                patient_id=patient.id,
                consent_status=ConsentStatusEnum.OBTAINED,
                consent_date=enroll_date,
                consent_document_ref=f"IRB-UMF-2026-CONSENT-{pspec['code']}",
            )
        )
        db.add(
            FractureDetail(
                patient_id=patient.id,
                fracture_side=pspec["side"],
                fracture_classification=pspec["class"],
                fracture_location=pspec["loc"],
                injury_date=enroll_date - timedelta(days=1),
                injury_mechanism=pspec["mech"],
                associated_fractures="None (isolated unilateral mandibular fracture)",
                clinical_notes=f"SYNTHETIC DEMO RECORD — {pspec['side'].value} unilateral fracture with measurable lower-third soft-tissue asymmetry pre-operatively.",
            )
        )
        db.add(
            SurgeryDetail(
                patient_id=patient.id,
                surgery_date=surg_date,
                fixation_type=pspec["fix"],
                surgical_approach=pspec["approach"],
                plate_details="2.0mm titanium miniplate system, 4-hole and 6-hole plates with 6mm monocortical screws",
                surgeon_name=pspec["surgeon"],
                operative_notes="Anatomical reduction achieved under IMF; stable occlusion verified.",
            )
        )

        # Create the 5 protocol visits
        for v_idx, sched in enumerate(VISIT_SCHEDULE):
            planned = surg_date + timedelta(days=sched["offset_days"])
            is_done = v_idx < pspec["completed_visits"]
            is_review_pending = (pspec["code"] in ("SYNTH-UMF-003", "SYNTH-UMF-004") and v_idx == pspec["completed_visits"] - 1)
            v_status = (
                (VisitStatusEnum.REVIEW_REQUIRED if is_review_pending else VisitStatusEnum.COMPLETED)
                if is_done
                else (VisitStatusEnum.SCHEDULED if planned >= today else VisitStatusEnum.IMAGES_PENDING)
            )
            visit = Visit(
                patient_id=patient.id,
                visit_type=visit_enums[v_idx],
                planned_date=planned,
                actual_date=planned if is_done else None,
                status=v_status,
                examiner_id=exam_user.id if is_done else None,
                notes=f"Synthetic {sched['label']} visit record.",
                protocol_version_id=proto_v1.id,
            )
            db.add(visit)
            await db.flush()

            if not is_done:
                continue

            # Clinical examination record for longitudinal comparison
            decay = [1.0, 0.75, 0.5, 0.3, 0.2][v_idx]
            db.add(
                ClinicalAssessment(
                    visit_id=visit.id,
                    patient_id=patient.id,
                    examiner_id=exam_user.id,
                    assessment_date=planned,
                    facial_swelling_grade=["Moderate", "Moderate-Mild", "Mild", "Minimal", "None"][v_idx],
                    occlusion_status="Pre-op malocclusion" if v_idx == 0 else "Stable Class I reproducible occlusion",
                    maximal_interincisal_opening_mm=round(24.0 + v_idx * 4.5, 1),
                    neurosensory_status="Intact bilateral V3 sensation" if v_idx >= 2 else "Mild transient hypoesthesia",
                    chin_deviation_mm=round(4.2 * decay * pspec["severity"], 2),
                    chin_deviation_side=pspec["side"].value,
                    soft_tissue_healing="Pre-operative" if v_idx == 0 else "Primary healing, no dehiscence",
                    pain_score_vas=round(max(0.5, 6.5 - v_idx * 1.5), 1),
                    complications_present=False,
                    paired_physical_measurements={
                        "T_PG_tape_right_mm": round(140.0 + (2.0 if pspec["side"] == FractureSideEnum.RIGHT else 0.0) * decay, 1),
                        "T_PG_tape_left_mm": round(140.0 + (2.5 if pspec["side"] == FractureSideEnum.LEFT else 0.0) * decay, 1),
                    },
                    examiner_notes="Synthetic clinical assessment paired with photographic & OPG capture.",
                )
            )

            # Generate synthetic images + quality + calibration + landmarks for all 5 visits of SYNTH-UMF-001
            # and for completed visits of SYNTH-UMF-002..005
            asym = visit_asymmetry(pspec["side"].value, v_idx, pspec["severity"])
            seed_base = (p_idx + 1) * 100 + v_idx * 10
            view_builders = [
                (ImageTypeEnum.FRONTAL, CalibrationTypeEnum.FRONTAL_PHOTO, frontal(asym["frontal"], seed=seed_base + 1)),
                (ImageTypeEnum.RIGHT_LATERAL, CalibrationTypeEnum.RIGHT_LATERAL_PHOTO, lateral("Right", asym["right"], seed=seed_base + 2)),
                (ImageTypeEnum.LEFT_LATERAL, CalibrationTypeEnum.LEFT_LATERAL_PHOTO, lateral("Left", asym["left"], seed=seed_base + 3)),
                (ImageTypeEnum.OPG, CalibrationTypeEnum.OPG, opg(asym["opg"], seed=seed_base + 4)),
            ]

            run_id = visit.id
            lm_job = AIJob(
                visit_id=visit.id,
                patient_id=patient.id,
                task_type=AITaskTypeEnum.FACIAL_LANDMARK,
                status=AIJobStatusEnum.COMPLETED if not is_review_pending else AIJobStatusEnum.REVIEW_REQUIRED,
                started_at=datetime.now(timezone.utc) - timedelta(minutes=12),
                completed_at=datetime.now(timezone.utc) - timedelta(minutes=11, seconds=48),
                duration_seconds=1.85,
                model_name="demo-facial-landmark-detector",
                model_version="demo-1.0.0",
                provider_name="Demo",
                is_demo=True,
                pipeline_run_id=run_id,
                stage_order=3,
                protocol_version_id=proto_v1.id,
                created_by=coord_user.id,
                warnings=["SYNTHETIC DEMO OUTPUT — seeded for research workflow demonstration."],
            )
            db.add(lm_job)
            await db.flush()
            db.add(
                AIJobEvent(
                    job_id=lm_job.id,
                    event_type="completed",
                    message=f"Completed landmark detection for {pspec['code']} ({visit.visit_type.value})",
                )
            )

            for img_type, cal_type, (png_bytes, meta) in view_builders:
                fname = f"{pspec['code']}_{visit.visit_type.value}_{img_type.value}.png"
                key = storage.save("originals", png_bytes, "png", subdir=f"{pspec['code']}/{visit.visit_type.value}")
                w = 1600 if img_type == ImageTypeEnum.OPG else (1000 if "Lateral" in img_type.value else 900)
                h = 800 if img_type == ImageTypeEnum.OPG else (1100 if "Lateral" in img_type.value else 1150)

                vim = VisitImage(
                    visit_id=visit.id,
                    image_type=img_type,
                    original_filename=fname,
                    stored_path=key,
                    file_size=len(png_bytes),
                    mime_type="image/png",
                    width=w,
                    height=h,
                    capture_date=datetime.now(timezone.utc) - timedelta(days=max(1, -pspec["surgery_offset_days"] - sched["offset_days"])),
                    device_metadata={"synthetic": "SYNTHETIC DEMO IMAGE (fa-synthetic-1.0)", "camera": "Synthetic Clinical Rig"},
                    upload_status=UploadStatusEnum.COMPLETED,
                    uploaded_by=coord_user.id,
                    content_hash=sha256_bytes(png_bytes),
                    acceptance_status="Accepted",
                    is_synthetic=True,
                )
                db.add(vim)
                await db.flush()

                q = assess_quality(png_bytes, img_type.value)
                db.add(
                    ImageQualityResult(
                        image_id=vim.id,
                        provider="Built-in",
                        model_name=q["model_name"],
                        model_version=q["model_version"],
                        overall_score=None,
                        status=QualityStatusEnum.PASS,
                        face_visibility=q["face_visibility"],
                        orientation_check=q["orientation_check"],
                        lighting_check=q["lighting_check"],
                        blur_check=q["blur_check"],
                        occlusion_check=q["occlusion_check"],
                        framing_check=q["framing_check"],
                        resolution_check=q["resolution_check"],
                        issues=[],
                        suggestions=[],
                        manual_override_status=ManualOverrideStatusEnum.ACCEPTED,
                        manual_override_by=exam_user.id,
                        manual_override_at=datetime.now(timezone.utc),
                    )
                )

                # View-specific physical calibration record
                px_per_mm = float(meta["px_per_mm"])
                known_mm = 50.0
                measured_px = known_mm * px_per_mm
                mm_per_px = 1.0 / px_per_mm
                cal_warnings = (
                    ["OPG panoramic projection has regional magnification; directional factors applied."]
                    if img_type == ImageTypeEnum.OPG
                    else []
                )
                db.add(
                    CalibrationRecord(
                        visit_id=visit.id,
                        image_id=vim.id,
                        calibration_type=cal_type,
                        reference_marker_type="10mm radiopaque ball bearing" if img_type == ImageTypeEnum.OPG else "50mm adhesive scale ruler in facial plane",
                        known_marker_length_mm=known_mm,
                        measured_marker_length_px=measured_px,
                        mm_per_pixel=mm_per_px,
                        marker_location="Symphyseal region" if img_type == ImageTypeEnum.OPG else "Submental / malar plane",
                        calibration_plane="Mid-sagittal / Coronal anatomical plane",
                        calibration_method="Known reference marker + regional factor" if img_type == ImageTypeEnum.OPG else "Fiducial scale ruler",
                        magnification_factor=1.25 if img_type == ImageTypeEnum.OPG else 1.0,
                        pixel_spacing_x=mm_per_px,
                        pixel_spacing_y=mm_per_px,
                        regional_calibration=(
                            {"horizontal_mm_per_px": mm_per_px * 1.02, "vertical_mm_per_px": mm_per_px}
                            if img_type == ImageTypeEnum.OPG
                            else None
                        ),
                        warnings=cal_warnings,
                        is_physical=True,
                        same_plane_confirmed=True,
                        is_active=True,
                        calibrated_by=exam_user.id,
                        calibration_date=planned,
                    )
                )

                # Landmark predictions (and examiner review on non-pending visits)
                for code, coords in meta["landmarks"].items():
                    ld = lm_defs_by_code.get(code)
                    if not ld:
                        continue
                    orig_x, orig_y = float(coords[0]), float(coords[1])
                    # Simulate a small AI offset on GO_L that the examiner corrected on completed visits
                    ai_offset_x = 2.4 if (code in ("GO_L", "GO_R") and not is_review_pending) else 0.0
                    pred_status = (
                        PredictionStatusEnum.PREDICTED
                        if is_review_pending
                        else PredictionStatusEnum.APPROVED
                    )
                    pred = LandmarkPrediction(
                        image_id=vim.id,
                        job_id=lm_job.id,
                        landmark_definition_id=ld.id,
                        source="AI",
                        is_current=True,
                        x=orig_x if not is_review_pending else orig_x + ai_offset_x,
                        y=orig_y,
                        confidence=0.93,
                        status=pred_status,
                        model_name="demo-facial-landmark-detector" if img_type != ImageTypeEnum.OPG else "demo-opg-landmark-detector",
                        model_version="demo-1.0.0",
                    )
                    db.add(pred)
                    await db.flush()

                    if not is_review_pending and code in ("GO_L", "GO_R", "PG", "OPG_GO_L"):
                        db.add(
                            LandmarkReview(
                                prediction_id=pred.id,
                                reviewer_id=exam_user.id,
                                original_x=orig_x + 2.4,
                                original_y=orig_y - 1.2,
                                corrected_x=orig_x,
                                corrected_y=orig_y,
                                review_status=ReviewStatusEnum.CORRECTED,
                                correction_reason="Aligned to soft-tissue gonial contour palpation landmark",
                            )
                        )

            # Create a 3D mesh asset for the visit
            verts, faces = parametric_face_mesh(asym=4.0 * decay * (1 if pspec["side"] == FractureSideEnum.LEFT else -1))
            obj_text = to_obj(verts, faces, header=f"SYNTHETIC DEMO 3D MESH - {pspec['code']} {visit.visit_type.value}")
            mesh_key = storage.save("meshes", obj_text.encode("utf-8"), "obj", subdir=f"{pspec['code']}/{visit.visit_type.value}")
            lm3d = {
                "N": list(nearest_vertex(verts, 0.0, 38.0)),
                "PRN": list(nearest_vertex(verts, 0.0, 5.0)),
                "SN": list(nearest_vertex(verts, 0.0, -8.0)),
                "PG": list(nearest_vertex(verts, 1.5 * decay, -62.0)),
                "ME": list(nearest_vertex(verts, 1.5 * decay, -78.0)),
                "EX_R": list(nearest_vertex(verts, -32.0, 32.0)),
                "EX_L": list(nearest_vertex(verts, 32.0, 32.0)),
                "ZY_R": list(nearest_vertex(verts, -54.0, 12.0)),
                "ZY_L": list(nearest_vertex(verts, 54.0, 12.0)),
                "CH_R": list(nearest_vertex(verts, -22.0, -28.0)),
                "CH_L": list(nearest_vertex(verts, 22.0, -28.0)),
                "GO_R": list(nearest_vertex(verts, -44.0, -52.0)),
                "GO_L": list(nearest_vertex(verts, 44.0 - 3.0 * decay, -52.0)),
                "T_R": list(nearest_vertex(verts, -64.0, 10.0)),
                "T_L": list(nearest_vertex(verts, 64.0, 10.0)),
            }
            db.add(
                ReconstructionAsset(
                    visit_id=visit.id,
                    job_id=lm_job.id,
                    asset_type=AssetTypeEnum.MESH,
                    file_path=mesh_key,
                    file_format="OBJ",
                    quality_score=None,
                    status=ReconstructionStatusEnum.REQUIRES_REVIEW,
                    warnings=[
                        "SYNTHETIC DEMO 3D SURFACE — Parametric mesh for visualization; not metrically calibrated.",
                        "Surface geodesic path lengths approximate flexible tape measurements and require paired physical validation.",
                    ],
                    metadata_={
                        "coverage": {
                            "required_views": ["Frontal", "LeftLateral", "RightLateral"],
                            "available_views": ["Frontal", "LeftLateral", "RightLateral"],
                            "missing_views": [],
                            "shared_landmarks": 9,
                            "status": "RequiresReview",
                        },
                        "vertex_count": len(verts),
                        "face_count": len(faces),
                        "landmarks_3d": lm3d,
                        "is_metric": True,
                        "is_demo": True,
                        "model_name": "demo-parametric-3d-mesh",
                        "model_version": "demo-1.0.0",
                    },
                )
            )
            await db.flush()

            # Compute geometric measurements for this visit
            ms = await calculate_visit_measurements(db, visit.id, exam_user.id, lm_job.id)
            if not is_review_pending:
                for m in ms:
                    if m.right_value is not None and m.left_value is not None:
                        m.method = MeasurementMethodEnum.VALIDATED
                        m.status = MeasurementStatusEnum.APPROVED
                        m.reviewer_notes = "Verified calibration plane and bilateral landmark placement."
                        db.add(
                            MeasurementApproval(
                                measurement_id=m.id,
                                approver_id=exam_user.id,
                                approval_status=ApprovalStatusEnum.APPROVED,
                                comments="Approved for longitudinal research dataset.",
                            )
                        )

            # Seed an initial report for SYNTH-UMF-001 Pre-op and 6-month visits
            if pspec["code"] == "SYNTH-UMF-001" and v_idx in (0, 4):
                db.add(
                    Report(
                        patient_id=patient.id,
                        visit_id=visit.id,
                        report_type=ReportTypeEnum.PATIENT_SUMMARY,
                        title=f"{pspec['code']} — {sched['label']} Quantitative Asymmetry Report",
                        content={
                            "summary_text": (
                                f"Synthetic demo longitudinal analysis for {pspec['code']} at {sched['label']}. "
                                "All bilateral linear measurements were computed from view-specific physical calibrations."
                            ),
                            "is_demo": True,
                        },
                        generated_by=exam_user.id,
                        ai_job_id=lm_job.id,
                        protocol_version_id=proto_v1.id,
                        status=ReportStatusEnum.APPROVED,
                    )
                )

    # 7. Notifications & Initial Audit Entries
    for u in users_by_role.values():
        db.add(
            Notification(
                user_id=u.id,
                title="SYNTHETIC DEMO DATASET LOADED",
                message="6 coded synthetic patients (SYNTH-UMF-001..006) are available. Visits on SYNTH-UMF-003 and SYNTH-UMF-004 await examiner review.",
                notification_type=NotificationTypeEnum.INFO,
                resource_type="system",
            )
        )

    db.add_all(
        [
            AuditLog(
                user_id=pi_user.id,
                action="protocol.create",
                resource_type="study_protocol",
                resource_id=protocol.id,
                after_value={"identifier": "UMF-ASYM-2026", "version": "1.0"},
                reason="Initial IRB-approved research protocol configuration",
                ip_address="127.0.0.1",
            ),
            AuditLog(
                user_id=coord_user.id,
                action="patient.seed_demo",
                resource_type="patient",
                after_value={"seeded_codes": [p["code"] for p in synthetic_patients_spec], "is_synthetic": True},
                reason="Seeded synthetic demonstration cohort (no real patient data)",
                ip_address="127.0.0.1",
            ),
            AuditLog(
                user_id=exam_user.id,
                action="landmark.review",
                resource_type="landmark_prediction",
                before_value={"code": "GO_L", "x": 668.2, "y": 836.8},
                after_value={"code": "GO_L", "x": 665.8, "y": 838.0, "status": "Approved"},
                reason="Aligned soft-tissue Gonion (Left) to palpated mandibular angle contour",
                ip_address="127.0.0.1",
            ),
            AuditLog(
                user_id=admin_user.id,
                action="ai_config.initialize",
                resource_type="ai_provider_config",
                after_value={"default_provider": "Demo", "external_uploads_allowed": False},
                reason="Initialized provider-independent AI task adapters with external uploads disabled by default",
                ip_address="127.0.0.1",
            ),
        ]
    )
    await db.commit()
