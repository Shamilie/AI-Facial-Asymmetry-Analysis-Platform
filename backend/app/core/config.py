"""
Application configuration loaded from environment variables and .env file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central application settings (env vars > .env file > defaults)."""

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR.parent / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "AI Facial Asymmetry Analysis Platform"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://faplatform:dev_password_123@localhost:5432/facial_asymmetry"
    DATABASE_URL_SYNC: str = "postgresql://faplatform:dev_password_123@localhost:5432/facial_asymmetry"

    # --- Redis / jobs ---
    REDIS_URL: str = "redis://localhost:6379/0"
    # "inline" runs AI pipelines in-process (asyncio background task);
    # "celery" dispatches to a Celery worker via Redis.
    TASK_BACKEND: str = "inline"

    # --- Security ---
    SECRET_KEY: str = "change-me-to-a-random-secret-key-in-production"
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (json.JSONDecodeError, TypeError):
                return [o.strip() for o in v.split(",") if o.strip()]
        return v  # type: ignore[return-value]

    # --- Storage ---
    STORAGE_BACKEND: str = "database"  # database | s3 | local
    UPLOAD_DIR: str = str(BACKEND_DIR / "storage")
    MAX_UPLOAD_SIZE_MB: int = 50
    MIN_IMAGE_DIMENSION_PX: int = 400
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET: str = "fa-platform"
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_REGION: str = "us-east-1"

    # --- AI providers (secrets stay server-side) ---
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    NVIDIA_API_KEY: Optional[str] = None
    CUSTOM_GPU_API_KEY: Optional[str] = None
    MEDIAPIPE_MODEL_PATH: str = str(BACKEND_DIR / "models" / "mediapipe")
    # External uploads of images/data to third-party AI providers are disabled by
    # default and must only be enabled with ethics approval + consent + DPA.
    ALLOW_EXTERNAL_AI_UPLOADS: bool = False

    # --- Display-only assumption (NOT physical calibration) ---
    DISPLAY_PX_PER_MM_ASSUMPTION: float = 3.78

    # --- Application ---
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
