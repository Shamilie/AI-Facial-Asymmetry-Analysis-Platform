"""
Export all SQLAlchemy models so Alembic and application modules can discover them.
"""

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
from app.models.blob import StoredBlob
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
from app.models.report import (
    ExportFormatEnum,
    Report,
    ReportExport,
    ReportStatusEnum,
    ReportTypeEnum,
)
from app.models.system_setting import SystemSetting
from app.models.user import Permission, Role, RolePermission, User, UserRole
from app.models.visit import Visit, VisitStatusEnum, VisitTypeEnum

__all__ = [
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "Patient",
    "PatientConsent",
    "FractureDetail",
    "SurgeryDetail",
    "SexEnum",
    "StudyStatusEnum",
    "ConsentStatusEnum",
    "FractureSideEnum",
    "Visit",
    "VisitTypeEnum",
    "VisitStatusEnum",
    "VisitImage",
    "ImageQualityResult",
    "ImageTypeEnum",
    "UploadStatusEnum",
    "QualityStatusEnum",
    "ManualOverrideStatusEnum",
    "AIJob",
    "AIJobEvent",
    "AIProviderConfig",
    "AIModelRegistry",
    "AITaskTypeEnum",
    "AIJobStatusEnum",
    "ProviderTypeEnum",
    "EnvironmentEnum",
    "LandmarkDefinition",
    "LandmarkPrediction",
    "LandmarkReview",
    "LandmarkTypeEnum",
    "PredictionStatusEnum",
    "ReviewStatusEnum",
    "CalibrationRecord",
    "CalibrationTypeEnum",
    "MeasurementDefinition",
    "Measurement",
    "MeasurementApproval",
    "MeasurementTypeEnum",
    "MeasurementMethodEnum",
    "MeasurementStatusEnum",
    "ApprovalStatusEnum",
    "Report",
    "ReportExport",
    "ReportTypeEnum",
    "ReportStatusEnum",
    "ExportFormatEnum",
    "StudyProtocol",
    "ProtocolVersion",
    "ReconstructionAsset",
    "AssetTypeEnum",
    "ReconstructionStatusEnum",
    "ClinicalAssessment",
    "AuditLog",
    "StoredBlob",
    "SystemSetting",
    "Notification",
    "NotificationTypeEnum",
]
