"""
Application configuration using Pydantic Settings.
All secrets come from environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://jobpilot:jobpilot_dev_password@localhost:5432/jobpilot"

    # Auth
    jwt_secret_key: str = "change-me-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LLM APIs
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Reranking (Cohere)
    cohere_api_key: Optional[str] = None

    # Web Search APIs
    tavily_api_key: Optional[str] = None
    serper_api_key: Optional[str] = None

    # Google Calendar API
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_refresh_token: Optional[str] = None

    # Embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # File storage
    s3_bucket: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_endpoint: Optional[str] = None  # For Supabase Storage or other S3-compatible
    upload_dir: str = "uploads"  # Local fallback

    # Redis (for Celery)
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_name: str = "JobPilot API"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
