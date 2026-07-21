from typing import List
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    SECRET_KEY: str = ""
    JWT_SECRET: str = ""
    DATABASE_URL: str = "postgresql+psycopg2://tms:tms@localhost:5432/tms"
    CORS_ALLOWED_ORIGINS: List[str] = ["https://smartpc999-1.tail0c63e1.ts.net:8443"]
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7
    LOG_LEVEL: str = "INFO"
    
    @model_validator(mode="after")
    def _require_secrets(self) -> "Settings":
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be set to a 32+ char random value")
        if not self.JWT_SECRET or len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be set to a 32+ char random value")
        return self


settings = Settings()  # ASSUMES: instantiation raises at import if env vars missing