"""Application settings, read from the environment only.

compose passes `.env` through `env_file`, so the app never opens that file itself.
"""
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "1.0.0"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Typed view of the environment variables listed in section 1 of the contract."""

    # hide_input_in_errors keeps secret values out of the traceback when validation refuses a boot.
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: str = "production"
    log_level: str = "INFO"
    log_dir: str = "/app/logs"

    gemini_api_key: SecretStr = SecretStr("")
    gemini_live_model: str = "gemini-3.8-live"
    gemini_analysis_model: str = "gemini-3.6-flash"
    gemini_analysis_fallback_models: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    live_provider: Literal["gemini", "mock"] = "gemini"

    jwt_secret: SecretStr
    jwt_expire_days: int = 7
    cookie_secure: bool = False
    allowed_origins: str = "http://localhost:1201,http://127.0.0.1:1201"

    database_url: SecretStr

    daily_live_seconds_per_user: int = 1800
    max_concurrent_live_sessions: int = 5
    # Room for the longest speech, then scoring, feedback and a few follow-up questions.
    live_max_session_seconds: int = 1500
    max_speech_seconds: int = 900

    # The one admin account. Leave these empty to have no admin. See app/services/admin.py.
    admin_email: str = ""
    admin_password: SecretStr = SecretStr("")

    @field_validator("jwt_secret")
    @classmethod
    def _require_long_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters")
        return value

    @field_validator("database_url")
    @classmethod
    def _require_postgres(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must start with postgresql+psycopg://")
        return value

    @property
    def origin_list(self) -> list[str]:
        """Allowed origins as a list, for CORS and the WebSocket origin check."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def analysis_models(self) -> list[str]:
        """Analysis models in the order they should be tried."""
        fallbacks = [m.strip() for m in self.gemini_analysis_fallback_models.split(",") if m.strip()]
        return [self.gemini_analysis_model, *fallbacks]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, validating them on first use."""
    return Settings()
