"""Custom ASGI middleware: security headers + request ID.

CSP is applied ONLY to text/html responses so JSON and binary responses keep their
existing content-type and aren't accidentally blocked by script-src.
nosniff and no-referrer are applied globally.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ASSUMES: Tailwind via the official play CDN at cdn.tailwindcss.com and Alpine via
# cdn.jsdelivr.net. No 'unsafe-eval'. Tailwind CDN is loaded as an external script;
# its JIT runtime executes inside its own bundle, not via page-context eval.
CSP_DIRECTIVES = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        ctype = response.headers.get("content-type", "")
        if ctype.startswith("text/html"):
            response.headers["Content-Security-Policy"] = CSP_DIRECTIVES
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response