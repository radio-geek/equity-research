"""
Vercel serverless entrypoint: expose the FastAPI app for /api and /auth routes.

Vercel invokes this as a single function; rewrites in vercel.json send
/api/* and /auth/* here. Path /auth/* is rewritten to /api/vercel_auth/* so the
same function handles both; we restore the path for FastAPI routing.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.main import app as _app  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402

_VERCEL_AUTH_PREFIX = "/api/vercel_auth/"
_AUTH_PREFIX = "/auth/"


class VercelAuthPathMiddleware(BaseHTTPMiddleware):
    """Restore /auth/* path when request was rewritten to /api/vercel_auth/*."""

    async def dispatch(self, request: Request, call_next):
        path = request.scope.get("path") or ""
        if path.startswith(_VERCEL_AUTH_PREFIX):
            request.scope["path"] = _AUTH_PREFIX + path[len(_VERCEL_AUTH_PREFIX) :]
        return await call_next(request)


app = VercelAuthPathMiddleware(_app)
