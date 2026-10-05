import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dilla University AI Lost-and-Found System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    model_config = SettingsConfigDict(case_sensitive=True)

    # Security
    SECRET_KEY: str = "dilla-university-lost-and-found-secret-key-2026-secure-jwt"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database
    DATABASE_URL: str = "sqlite:///./dilla_lost_found.db"

    # File Storage
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

    # AI Matching Thresholds & Weights
    WEIGHT_IMAGE: float = 0.45
    WEIGHT_TEXT: float = 0.35
    WEIGHT_METADATA: float = 0.20

    # Confidence Gates
    THRESHOLD_DIRECT_MATCH: float = 0.80  # Auto-notify user
    THRESHOLD_OFFICER_REVIEW: float = 0.52  # Send to officer queue for review

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
