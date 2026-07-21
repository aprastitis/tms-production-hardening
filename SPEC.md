# Feature: TMS Production Hardening — Full Domain Port

Port the complete domain layer from the original transaction-monitoring-system into the existing hardened FastAPI shell, add a static vanilla-JS dashboard, and prove end-to-end correctness via a 7-step smoke test.

## Goals

- Bring over all 14 (TBD exact count — see Open Questions) tables, the matching engine, FX conversion, parsers for CSV/XLSX/MT940/BAI2, and the original six write/summary routes.
- Add the two missing read endpoints the dashboard needs: GET /transactions and GET /flags, both paginated.
- Add three first-class auth endpoints the security bar requires: POST /auth/refresh, GET /auth/me, PATCH /auth/me/password.
- Serve the dashboard at /static/ (Tailwind via CDN, Alpine.js for the change-password modal and resolve button state, no bundler).
- Alembic migrations apply cleanly on a fresh PostgreSQL DB at boot; CI on GitHub Actions must stay green.
- A 7-step smoke harness (login, flag create, list open, resolve, daily summary, rate limit, bad-creds) passes locally, in CI, and against the live Tailscale deployment.
- Reach production-equivalent security bar: Argon2id password hashing, HS256 JWT with separate SECRET_KEY/JWT_SECRET, slowapi on login, exact-origin CORS, strict CSP with no unsafe-eval, Pydantic extra='forbid' on all inputs, audit logs on writes, secrets fail-fast at boot.

## Non-Goals

- Multi-tenant isolation. Single-tenant deployment for v1.
- Date-range filtering on /reports/daily-summary (today only — explicit follow-up).
- Refresh-token rotation policy or family revocation. One refresh per access session; revoking access via secret rotation is sufficient.
- ML/heuristic flagging beyond rule-based amount/date/counterparty matching.
- Full MT940/BAI2/CSV/XLSX edge cases. Parsers handle well-formed inputs; malformed rows are logged and rejected at the row level.
- httpOnly-cookie auth alternative.
- Tailscale certificate provisioning, reverse proxy, or cert renewal.
- Read-write audit log UI. Only writes happen; reads are endpoint-only (GET /audit-log).
- JWT_SECRET rotation flow. Documented; not built.

## Acceptance Criteria

- POST /auth/login with correct admin/admin returns 200 and {access_token, refresh_token, user}.
- Six failed/successful logins from the same IP within 60s cause the 6th to return 429 with {"detail":"rate_limited"}.
- POST /auth/login with admin/wrong returns 401 with {"detail":"invalid_credentials"}.
- Any protected endpoint returns 401 with {"detail":"missing_token"} when no Authorization: Bearer header is present.
- POST /flags with a valid payload returns 201 + flag_id and writes an AuditLog row with actor=<jwt sub>, event_type=flag.created, payload=<body>, occurred_at=<UTC now>.
- POST /flags/{flag_id}/resolve for an existing open flag returns 200 with status: resolved and writes an AuditLog row with event_type=flag.resolved.
- GET /flags?status=open returns 200 with {items, total, page, page_size} and includes a flag created earlier.
- GET /transactions with filters source_id, status, value_date_from, value_date_to returns 200 with {items, total, page, page_size}.
- GET /reports/daily-summary returns 200 with {date=today UTC, ingested, matched, flag_count, open_count, total_usd}; flag_count > 0 after the smoke test creates one.
- POST /ingest/upload accepts multipart CSV and returns 202 + {raw_file_id, rows_accepted}.
- POST /ingest/webhook/DEFAULT accepts a payload when Source with code=DEFAULT and is_webhook_enabled=true exists and returns 202 + {raw_file_id}.
- Any POST endpoint receiving a body with an unknown field returns 422 (Pydantic ConfigDict(extra='forbid')).
- CORS preflight from https://smartpc999-1.tail0c63e1.ts.net:8443 returns that origin in Access-Control-Allow-Origin; preflight from any other origin returns no allow-origin header.
- Every HTML response carries a Content-Security-Policy header with the specified directives and no unsafe-eval.
- The admin user's password_hash in PostgreSQL begins with $argon2id$.
- Booting the app without SECRET_KEY or JWT_SECRET exits non-zero with a clear error before binding.
- After admin login with must_change_password=true, the dashboard renders a change-password modal that blocks all other UI until PATCH /auth/me/password rotates the password.
- After alembic upgrade head against a fresh DB, the seed step creates one admin user, one Source row with code=DEFAULT, and three ReasonCode rows: AMOUNT_MISMATCH, DATE_OUTSIDE_WINDOW, MISSING_COUNTERPARTY.
- GET /static/index.html returns 200 with an HTML body containing a login form; GET /static/app.js returns 200.
- The CI workflow runs the 7-step smoke harness against a docker-compose stack and asserts all 7 steps pass.

## Technical Notes

**Stack**
- Python 3.11+, FastAPI, SQLAlchemy 2.x sync, Alembic, psycopg2-binary, Pydantic v2, pydantic-settings, python-multipart, argon2-cffi, PyJWT, slowapi, httpx, pytest.
- Frontend: vanilla JS, no bundler. Tailwind v3 via CDN. Alpine.js v3 via CDN for the change-password modal and the resolve-button busy state.

**Database**
- PostgreSQL 14+. One Alembic migration creates all domain tables. Role and Flag.status stored as Postgres ENUM types.

**Settings**
- Settings(BaseSettings): SECRET_KEY: str and JWT_SECRET: str are required fields with no defaults; model validator raises at instantiation if either is empty.
- DATABASE_URL, CORS_ALLOWED_ORIGINS (list, default ["https://smartpc999-1.tail0c63e1.ts.net:8443"]), JWT_ACCESS_TTL_MIN=15, JWT_REFRESH_TTL_DAYS=7.
- .env.example lists both secrets with the comment "set to a 32+ char random value".

**Auth**
- Argon2id via argon2-cffi's PasswordHasher with default params. ph.check(db_hash, plaintext); ph.verify_and_update on password change.
- POST /auth/login: verify hash in constant time, mint access_token (HS256, 15min, claims sub/iat/exp/type=access) and refresh_token (HS256, 7d, type=refresh).
- POST /auth/refresh: accepts {refresh_token}, returns new pair (default rotation). Rejects type=access tokens. Slowapi at 5/min/IP.
- GET /auth/me: returns current user; dashboard checks must_change_password here.
- PATCH /auth/me/password: {new_password}. Validates complexity (min 12 chars, not equal to old). Updates hash, sets must_change_password=false.
- require_user dependency decodes Authorization: Bearer <jwt> with JWT_SECRET; 401 on missing/expired/invalid. Stashes user id on request.state for audit.

**Audit log**
- AuditLog(actor_id, event_type, payload JSONB, occurred_at).
- Writes happen inside route handlers immediately after mutation succeeds.
- GET /audit-log?page=1&page_size=50 returns paginated rows (read-only; dashboard does not consume v1).

**CORS + CSP**
- CORSMiddleware with allow_origins=settings.cors_allowed_origins (exact match), allow_credentials=False, allow_methods=["GET","POST","PATCH","OPTIONS"], allow_headers=["Authorization","Content-Type"].
- Response middleware applies CSP header to text/html responses only. Also adds X-Content-Type-Options: nosniff and Referrer-Policy: no-referrer globally.

**Rate limiting**
- slowapi.Limiter(key_func=get_remote_address, default_limits=[]).
- POST /auth/login: @limiter.limit("5/minute").
- POST /auth/refresh: @limiter.limit("5/minute").
- On exceed: JSONResponse({"detail":"rate_limited"}, status_code=429).

**Pydantic strictness**
- StrictModel(BaseModel) with model_config = ConfigDict(extra='forbid', str_strip_whitespace=True). All input/body/query/path models subclass StrictModel.

**Matching engine (matching.py)**
- Rule-based: for each new external Transaction, look up candidates in InternalTransaction rows in a date window (default ±2 business days), with FX-normalized amounts within tolerance (default 1% relative, configurable per Source).
- Produces Match rows; when no match meets tolerance, opens a Flag with reason code (AMOUNT_MISMATCH, DATE_OUTSIDE_WINDOW, MISSING_COUNTERPARTY).
- Idempotent: re-ingesting the same raw file does not duplicate matches/flags.

**FX conversion (fx.py)**
- convert(amount, from_currency, to_currency, on_date) → Decimal. Reads from fx_rate table; falls back to most-recent prior date. Missing rate → FXRateMissing; mapped to 422 at API boundary.

**Parsers (parsers.py)**
- dispatch(raw_bytes, content_type, source) → list[RawRow]. CSV via stdlib csv, XLSX via openpyxl, MT940 and BAI2 via small hand-rolled state-machine parsers (happy path only). Row-level errors captured on the raw file's processing log.

**Dashboard (src/app/static/)**
- index.html: Tailwind-styled shell with one div#app for Alpine.js.
- app.js: handles login (POST → store tokens → fetch /auth/me → branch on must_change_password), transactions table with prev/next paging, flags table with per-row resolve button (POST → refresh list), daily-summary card.
- Change-password modal (Alpine x-show): PATCH /auth/me/password, then refresh /auth/me, then unmount.
- Logout: clear localStorage, redirect to login.
- All fetches add Authorization: Bearer …; on 401, clear localStorage and show login.

**Static serving**
- app.mount("/static", StaticFiles(directory="src/app/static"), name="static").
- GET / returns static/index.html with CSP middleware applied.

**Health (already in shell)**
- /healthz and /healthz/db retained, public. CSP middleware excluded for application/json.

**CI**
- Existing GitHub Actions workflow gains a smoke step: postgres up, alembic upgrade head, python -m app.seed, uvicorn, pytest tests/smoke/ -v.
- The 7 steps are covered end-to-end by acceptance criteria.

**Webhook auth model**
- POST /ingest/webhook/{source_code} requires JWT per the security bar. Operators mint a long-lived service-account JWT for upstream integrations. Source-keyed HMAC auth is a future enhancement.

**Operational**
- Logs: JSON structured. X-Request-ID middleware.
- Container: existing multi-stage Dockerfile unchanged. Image boots → alembic upgrade head → python -m app.seed → uvicorn.
- README documents JWT_SECRET rotation: rotating forces all current users to re-login; no rotation flow in v1.

## Open Questions

- Table count from /workspaces/transaction-monitoring-system-627deb0d/src/tms/models.py. Spec assumes 14; discovery will record actual count. The orchestrator must surface any delta in commit notes and adjust the smoke harness.
- Default matching tolerances: spec assumes 1% relative amount, ±2 business days window. Confirm or change before matching.py is wired into ingest.
- FX rate data source: manual seed for v1, or provider integration (ECB / exchangerate.host)? Spec assumes manual seed + test fixture endpoint. Confirm provider preference or accept manual seeding.
- /auth/refresh rate limit: 5/min/IP shared with login (spec assumption), or its own threshold?
- Dashboard refresh cadence: refresh-on-action only (spec assumption), or N-second polling on flags/transactions tables?