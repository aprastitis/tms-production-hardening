"""SQLAlchemy engine, session factory, and declarative Base."""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import get_settings


class Base(DeclarativeBase):
    """Project-wide declarative base. Alembic autogenerate reads from Base.metadata."""


_settings = get_settings()

engine = create_engine(
    _settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()