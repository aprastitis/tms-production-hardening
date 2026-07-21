"""Application settings. Boot fails fast if required secrets are missing."""
from __future__ import annotations

from typing import List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Required secrets. SPEC.md acceptance criteria #16: missing/empty -> boot fails.
    # ASSUMES: 32-char minimum as recommended in SPEC.md.
    SECRET_KEY: str = Field(..., min_length=32)
    JWT_SECRET: str = Field(..., min_length=32)

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://tms:tms@localhost:5432/tms"

    # CORS — exact origin, no credentials.
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "https://smartpc999-1.tail0c63e1.ts.net:8443",
        ]
    )

    # JWT TTLs
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        # ASSUMES: 32+ chars per SPEC.md; this is a belt-and-braces check on top of Field(min_length=32).
        if len(self.SECRET_KEY.strip()) < 32:
            raise ValueError("SECRET_KEY must be 32+ characters")
        if len(self.JWT_SECRET.strip()) < 32:
            raise ValueError("JWT_SECRET must be 32+ characters")
        return self


def get_settings() -> Settings:
    """Instantiate Settings fresh — pydantic-settings re-reads env each call."""
    return Settings()