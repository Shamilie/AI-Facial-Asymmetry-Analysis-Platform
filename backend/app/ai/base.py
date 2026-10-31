"""
Provider-independent AI adapter contract.

Every adapter implements only the tasks it genuinely supports and declares them
in ``supported_tasks``. Calling an unsupported task raises ``TaskNotSupported``;
the orchestrator validates compatibility before dispatch.

Every response is an :class:`AIResult` with:
  task, provider, model, model_version, status, confidence, output, warnings,
  processing_time_ms, is_demo
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

# Canonical task identifiers (mirror AITaskTypeEnum values)
IMAGE_QUALITY = "ImageQuality"
FACIAL_LANDMARK = "FacialLandmark"
FACIAL_SEGMENTATION = "FacialSegmentation"
RECONSTRUCTION_3D = "Reconstruction3D"
OPG_LANDMARK = "OPGLandmark"
OPG_SEGMENTATION = "OPGSegmentation"
REPORT_GENERATION = "ReportGeneration"

MODEL_TASKS = [IMAGE_QUALITY, FACIAL_LANDMARK, FACIAL_SEGMENTATION, RECONSTRUCTION_3D, OPG_LANDMARK, OPG_SEGMENTATION, REPORT_GENERATION]


class TaskNotSupported(Exception):
    pass


class ProviderUnavailable(Exception):
    """Raised when a provider/model cannot be reached or is not installed."""


@dataclass
class ImageInput:
    image_id: str
    image_type: str  # Frontal | RightLateral | LeftLateral | OPG
    data: bytes
    width: int
    height: int
    synthetic_meta: dict | None = None


@dataclass
class AIResult:
    task: str
    provider: str
    model: str
    model_version: str
    status: str  # Completed | Failed | ReviewRequired | NotIdentifiable
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    is_demo: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderConfig:
    provider_type: str
    model_name: str
    model_identifier: str | None = None
    model_version: str | None = None
    endpoint_url: str | None = None
    api_key: str | None = None  # resolved server-side from credential_key_name; never returned via API
    timeout_seconds: int = 30
    settings: dict[str, Any] = field(default_factory=dict)


class BaseProviderAdapter:
    provider_name: str = "base"
    supported_tasks: set[str] = set()
    is_demo: bool = False
    sends_data_externally: bool = False

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    # ---- helpers ----
    def _result(self, task: str, start: float, **kw: Any) -> AIResult:
        return AIResult(
            task=task,
            provider=self.provider_name,
            model=self.config.model_name,
            model_version=self.config.model_version or "unversioned",
            processing_time_ms=round((time.perf_counter() - start) * 1000, 2),
            is_demo=self.is_demo,
            **kw,
        )

    def supports(self, task: str) -> bool:
        return task in self.supported_tasks

    def _unsupported(self, task: str) -> AIResult:
        raise TaskNotSupported(f"{self.provider_name} does not support task {task}")

    # ---- contract ----
    async def health_check(self) -> dict[str, Any]:
        return {"ok": True, "message": "No health check implemented"}

    async def assess_image_quality(self, image: ImageInput) -> AIResult:
        return self._unsupported(IMAGE_QUALITY)

    async def detect_landmarks(self, image: ImageInput, landmark_codes: list[str]) -> AIResult:
        return self._unsupported(FACIAL_LANDMARK)

    async def segment_image(self, image: ImageInput) -> AIResult:
        return self._unsupported(FACIAL_SEGMENTATION)

    async def reconstruct_face(self, images: list[ImageInput], landmarks: dict[str, dict[str, list[float]]]) -> AIResult:
        return self._unsupported(RECONSTRUCTION_3D)

    async def detect_opg_landmarks(self, image: ImageInput, landmark_codes: list[str]) -> AIResult:
        return self._unsupported(OPG_LANDMARK)

    async def segment_opg(self, image: ImageInput) -> AIResult:
        return self._unsupported(OPG_SEGMENTATION)

    async def generate_research_summary(self, approved_data: dict[str, Any]) -> AIResult:
        return self._unsupported(REPORT_GENERATION)


def validate_landmark_output(output: dict[str, Any], width: int, height: int) -> list[str]:
    """Schema/bounds validation for landmark outputs. Returns a list of problems."""
    problems: list[str] = []
    lms = output.get("landmarks")
    if not isinstance(lms, list):
        return ["Output missing 'landmarks' list"]
    for lm in lms:
        if not isinstance(lm, dict) or "code" not in lm:
            problems.append("Landmark entry missing 'code'")
            continue
        if lm.get("not_identifiable"):
            if lm.get("x") is not None or lm.get("y") is not None:
                problems.append(f"{lm['code']}: not_identifiable landmarks must not carry coordinates")
            continue
        x, y = lm.get("x"), lm.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            problems.append(f"{lm['code']}: missing numeric coordinates")
        elif not (0 <= x <= width and 0 <= y <= height):
            problems.append(f"{lm['code']}: coordinates out of image bounds")
        c = lm.get("confidence")
        if c is not None and not (0 <= c <= 1):
            problems.append(f"{lm['code']}: confidence must be within [0, 1]")
    return problems
