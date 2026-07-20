"""Auto-generated adversarial test cases (Phase 5.4.2 QA Tester).
Do not edit by hand — regenerate by running a build."""

# State/idempotency: a flaky health check is a common production failure mode. Repeated calls must yield the same status code, not flap between 200 and 500/503.
def test_health_endpoint_idempotent_under_repeated_calls():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    paths = [r.path for r in app.routes]
    target = next((p for p in ("/healthz", "/health", "/healthz/db", "/readyz") if p in paths), None)
    if target is None:
        import pytest; pytest.skip("no health route registered")

    statuses = [client.get(target).status_code for _ in range(5)]
    assert all(s in (200, 503) for s in statuses), f"unexpected codes: {statuses}"
    assert len(set(statuses)) == 1, f"health endpoint flapped: {statuses}"

# Boundary/null: importing app.config must not require a full .env file. If required vars are missing, the failure must be a clear validation error, not a silent None or AttributeError downstream.
def test_config_module_loads_with_minimal_env(monkeypatch):
    import os, sys, importlib
    # Strip app-specific env so we test the truly-required surface
    for k in list(os.environ):
        if k.startswith(("DATABASE_", "DB_", "POSTGRES_", "APP_", "SECRET_")):
            monkeypatch.delenv(k, raising=False)
    for mod in [m for m in sys.modules if m.startswith("app.") or m == "app"]:
        del sys.modules[mod]
    try:
        importlib.import_module("app.config")
    except Exception as e:
        # Acceptable only if it's a validation-style error mentioning a field name
        msg = str(e)
        assert any(tok in msg.lower() for tok in ("field", "required", "missing", "validation")), \
            f"config failed with non-validation error: {type(e).__name__}: {msg}"

# Negative/state: Alembic migrations and DB sessions both need a single shared declarative Base. If models re-declare Base inconsistently, autogenerate silently produces empty migrations.
def test_models_expose_sqlalchemy_declarative_base():
    from app import models
    base = getattr(models, "Base", None)
    assert base is not None, "app.models.Base is missing"
    # Must be a SQLAlchemy declarative base, not a plain class
    assert hasattr(base, "metadata"), "Base has no .metadata attribute"
    assert hasattr(base, "registry"), "Base is not a SQLAlchemy DeclarativeBase"
    # Every mapped class must register against this same Base
    mapped = [v for v in vars(models).values()
              if isinstance(v, type) and getattr(v, "__table__", None) is not None]
    for cls in mapped:
        assert cls.__table__.metadata is base.metadata, \
            f"{cls.__name__} uses a different MetaData than models.Base"

# Negative: production error responses must not expose stack traces or internal file paths, even when DEBUG is unset. Default Starlette debug pages reveal the entire filesystem layout.
def test_app_does_not_leak_traceback_on_404():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/__definitely_not_a_real_route__/x")
    assert r.status_code == 404
    body = r.text.lower()
    # Starlette's debug 404 includes 'traceback' and local paths
    for forbidden in ("traceback (most recent call last)", "/home/", "app/", ".py", line ",
        assert forbidden not in body, f"404 leaked internal info: {forbidden!r} in body"

# State/mutation isolation: a common bug is module-level Session() reuse that accumulates uncommitted state across requests. Hitting any DB-touching endpoint repeatedly must not raise PendingRollbackError or return stale data.
def test_db_session_does_not_leak_across_requests():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    db_paths = [r.path for r in app.routes if "db" in r.path.lower() or "ready" in r.path.lower()]
    target = db_paths[0] if db_paths else "/"

    responses = []
    for i in range(3):
        r = client.get(target)
        assert r.status_code < 500, f"request {i} raised 5xx: {r.text}"
        responses.append(r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
    # Each response must be self-consistent (no leaked state, no mixing of prior payloads)
    if isinstance(responses[0], dict):
        keys = [set(r.keys()) for r in responses]
        assert len(set(map(frozenset, keys))) == 1, f"response shape drifted: {keys}"
