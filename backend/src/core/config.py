"""Configuration settings using Pydantic Settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Database
    database_url: str

    # JWT Configuration
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Security
    bcrypt_rounds: int = 12
    environment: Literal["development", "production"] = "development"
    api_docs_enabled: bool | None = None
    bootstrap_token: str | None = None

    # Email (for invitations)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@annexops.local"

    # MinIO/S3 Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "annexops-attachments"
    minio_use_ssl: bool = False

    # Logging Collector (Module F - optional)
    allow_raw_pii: bool = False
    retention_days: int = 180

    # LLM Assist (Module G)
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-3-sonnet-20240229"
    llm_enabled: bool = True

    @model_validator(mode="after")
    def _validate_production_settings(self) -> Settings:
        if self.environment != "production":
            return self

        insecure_jwt_secrets = {
            "dev-secret-change-in-production",
            "your-secret-key-change-in-production",
            "change-me",
            "changeme",
        }
        if self.jwt_secret in insecure_jwt_secrets or len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be a strong secret in production")

        if self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin":
            raise ValueError("MINIO_ACCESS_KEY/MINIO_SECRET_KEY must be set in production")

        return self

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
