# app/main.py
"""FastAPI application entry point."""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.db import SessionLocal

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a FastAPI app instance. Settings load eagerly to fail-fast on bad config."""
    if settings is None:
        settings = get_settings()  # raises if SECRET_KEY / DATABASE_URL are invalid

    app = FastAPI(
        title="Transaction Monitoring System",
        version="1.0.0",
    )

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        """Liveness probe — the process is up."""
        return {"status": "ok"}

    @app.get("/healthz/db")
    def healthz_db() -> dict[str, str]:
        """Readiness probe — runs SELECT 1 against Postgres.
        
        Returns 200 on success, 503 with a JSON error body on failure.
        Uses a short-lived session — never reuses the request session —
        so DB restarts can't leave stale connections here.
        """
        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning("DB health check failed: %s", exc)
            # Return 503 with JSON body explicitly (FastAPI's HTTPException
            # does this for us, but we include a structured payload).
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "error",
                    "database": "unreachable",
                    "error": str(exc.__class__.__name__),
                },
            )
        finally:
            session.close()
        return {"status": "ok", "database": "reachable"}

    return app


# Eagerly construct the module-level app — this triggers settings validation
# at import time, so a missing/placeholder SECRET_KEY crashes the process
# before uvicorn binds the socket.
app: FastAPI = create_app()