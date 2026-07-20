# app/config.py
"""Application settings loaded from environment variables.

SECRET_KEY is required and must not be the placeholder 'changeme'.
DATABASE_URL is required and must point to PostgreSQL.
"""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strict application settings.

    Both SECRET_KEY and DATABASE_URL are mandatory. The app refuses to boot
    if SECRET_KEY is missing, blank, whitespace-only, or equal to the
    'changeme' placeholder.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ASSUMES: We don't allow the placeholder 'changeme' — this is what the
    # spec calls out explicitly as a fail-fast condition.
    SECRET_KEY: str = Field(..., min_length=1)
    DATABASE_URL: str = Field(...)

    # Server bind config (defaults are dev-friendly).
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_placeholder(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("SECRET_KEY must not be empty or whitespace-only")
        if stripped == "changeme":
            raise ValueError(
                "SECRET_KEY is set to the placeholder 'changeme'; "
                "set a real secret before booting."
            )
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_postgres(cls, value: str) -> str:
        if not value:
            raise ValueError("DATABASE_URL must not be empty")
        # Accept the SQLAlchemy "postgresql+psycopg://" and
        # "postgresql+psycopg2://" forms as well as the plain
        # "postgresql://" / "postgres://" forms. The spec pins
        # psycopg v3 (postgresql+psycopg://), so excluding that
        # prefix would block the recommended driver.
        if not (
            value.startswith("postgresql://")
            or value.startswith("postgres://")
            or value.startswith("postgresql+psycopg://")
            or value.startswith("postgresql+psycopg2://")
        ):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL "
                "(postgresql://... or postgresql+psycopg://...)"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()  # type: ignore[call-arg]