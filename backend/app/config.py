import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Dilla University AI Lost-and-Found System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:4173"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Security
    SECRET_KEY: str = "dilla-university-lost-and-found-secret-key-2026-secure-jwt"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Database
    DATABASE_URL: str = "sqlite:///./dilla_lost_found.db"

    # File Storage
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

    # AI Matching Thresholds & Weights
    WEIGHT_IMAGE: float = 0.45
    WEIGHT_TEXT: float = 0.35
    WEIGHT_METADATA: float = 0.20

    # Confidence Gates
    THRESHOLD_DIRECT_MATCH: float = 0.80
    THRESHOLD_OFFICER_REVIEW: float = 0.52


settings = Settings()

# Prefer an explicit env override for production deployments while keeping SQLite as the local default.
if os.getenv("DATABASE_URL"):
    settings.DATABASE_URL = os.getenv("DATABASE_URL")

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
