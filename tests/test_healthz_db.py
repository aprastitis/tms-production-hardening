"""Smoke test: GET /healthz/db against a real Postgres."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


# The DATABASE_URL env var must be set before this module is imported,
# because app.config.settings is built at import time. In CI it comes
# from the workflow's env block; for local runs, export it first or use
# a .env file at the repo root.

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def test_healthz_db_returns_ok_when_db_reachable(client: TestClient) -> None:
    response = client.get("/healthz/db")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"status": "ok", "db": "ok"}


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}