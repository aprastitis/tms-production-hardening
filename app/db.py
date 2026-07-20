# app/db.py
"""SQLAlchemy 2.x engine and session factory.

PostgreSQL only — driven by the DATABASE_URL env var. No SQLite fallback.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.x declarative base for all ORM models."""


def _build_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a transactional DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()