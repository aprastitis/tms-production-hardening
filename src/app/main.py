"""FastAPI application factory and health endpoints.

Wiring order (outermost first): RequestID, SecurityHeaders, CORS.
Health endpoints are public and excluded from CSP by content-type guard in middleware.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_db
from app.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.auth import router as auth_router
from app.routes_flags import router as flags_router
from app.routes_transactions import router as transactions_router
from app.routes_reports import router as reports_router

# Trigger fail-fast on missing/short secrets before binding the socket.
settings = get_settings()

logger = logging.getLogger("tms")
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}',
)

STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("tms starting; db=%s", settings.DATABASE_URL.split("@")[-1])
    yield
    logger.info("tms shutting down")


app = FastAPI(
    title="TMS",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# Middleware: order matters -- add_middleware is LIFO, so the FIRST added runs OUTERMOST.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Rate-limit handler returns the JSON shape the acceptance criteria require.
@app.exception_handler(RateLimitExceeded)
async def _rate_limited(_: Request, exc: RateLimitExceeded):
    return JSONResponse({"detail": "rate_limited"}, status_code=429)


# ---------- Routers ----------

app.include_router(auth_router)
app.include_router(flags_router)
app.include_router(transactions_router)
app.include_router(reports_router)


# ---------- Health (public) ----------

@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


@app.get("/healthz/db", include_in_schema=False)
def healthz_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}


# ---------- Static dashboard ----------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root_index():
    # Returns the dashboard shell; CSP middleware applies because content-type is text/html.
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html")
    # Placeholder until dashboard assets are built in a later iteration.
    return JSONResponse(
        {"status": "ok", "message": "TMS API online. Dashboard not yet built."},
        media_type="application/json",
    )