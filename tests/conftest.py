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
os.environ.setdefault("SECRET_KEY", "pytest-local-secret-not-for-production")