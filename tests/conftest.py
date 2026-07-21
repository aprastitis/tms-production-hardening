"""Pytest configuration.

Ensures required env vars are present BEFORE any test module imports
the app, so app.config.settings can build. In CI the env block on the
job provides real values; this conftest only fills in safe defaults
when nothing else has.
"""
from __future__ import annotations

import os

# Provide non-destructive defaults ONLY if not already set.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://tms:tms@localhost:5432/tms_test",
)
os.environ.setdefault("SECRET_KEY", "pytest-local-secret-not-for-production-1234567890")
os.environ.setdefault("JWT_SECRET", "pytest-local-jwt-secret-not-for-production-1234567890")
# Make `app.*` importable from src/ during pytest discovery at the repo root.
import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))