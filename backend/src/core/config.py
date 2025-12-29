"""Configuration settings using Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
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

    # CORS
    cors_allow_origins: list[str] = ["http://localhost:3000"]
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = [
        "Accept",
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Bootstrap-Token",
        "X-API-Key",
        "X-Metrics-Token",
    ]
    cors_allow_credentials: bool = True

    # Session cookie (refresh token)
    refresh_cookie_name: str = "refresh_token"
    refresh_cookie_path: str = "/api/auth/refresh"
    refresh_cookie_domain: str | None = None
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    refresh_cookie_secure: bool | None = None

    # Rate limiting (production-only safeguard)
    rate_limit_write_per_minute: int = 120
    rate_limit_refresh_per_minute: int = 60
    rate_limit_accept_invite_per_hour: int = 20

    @field_validator(
        "cors_allow_origins",
        "cors_allow_methods",
        "cors_allow_headers",
        mode="before",
    )
    @classmethod
    def _parse_csv_lists(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

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

        if any(x == "*" for x in self.cors_allow_origins):
            raise ValueError("CORS_ALLOW_ORIGINS cannot contain '*' in production")
        if any(x == "*" for x in self.cors_allow_methods):
            raise ValueError("CORS_ALLOW_METHODS cannot contain '*' in production")
        if any(x == "*" for x in self.cors_allow_headers):
            raise ValueError("CORS_ALLOW_HEADERS cannot contain '*' in production")

        if self.refresh_cookie_samesite == "none":
            secure = True if self.refresh_cookie_secure is None else bool(self.refresh_cookie_secure)
            if not secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true when REFRESH_COOKIE_SAMESITE=none")

        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
