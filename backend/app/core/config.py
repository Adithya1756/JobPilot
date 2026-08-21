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

    # Google Gemini API (FREE tier - get key at https://aistudio.google.com)
    gemini_api_key: Optional[str] = None

    # Embeddings (using gemini-embedding-001, 768 dims via MRL)
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # LLM (using Gemini 3.5 Flash - free tier)
    llm_model: str = "gemini-3.5-flash"

    # File storage
    upload_dir: str = "uploads"

    # App
    app_name: str = "JobPilot API"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()