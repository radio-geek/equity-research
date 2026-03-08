"""FastAPI app: symbol suggest, report job start/status/html."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Fail at startup if nse is missing (ensures we're running with the correct venv)
try:
    from nse import NSE  # noqa: F401
except ModuleNotFoundError as e:
    if e.name == "nse":
        print(
            "Error: the 'nse' package is not installed in this Python environment.\n"
            "Start the backend using your project venv, e.g.:\n"
            "  source .venv/bin/activate\n"
            "  python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000\n",
            file=sys.stderr,
        )
    raise

from backend.auth import (
    create_access_token,
    exchange_code_for_user,
    generate_oauth_state,
    get_current_user,
    get_session_id_from_request,
    google_auth_url,
    revoke_session,
    upsert_user,
    verify_oauth_state,
)
from backend.error_store import log_error
from backend.feedback_store import append_feedback
from backend.job_store import create_job_store, get as job_get, set_pending
from backend.pdf_render import render_payload_to_pdf
from backend.reports import get_report_status, start_report
from backend import symbols as symbols_module


class CreateReportRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"


# Global job store (in-memory)
_job_store: dict | None = None


def get_store() -> dict:
    global _job_store
    if _job_store is None:
        _job_store = create_job_store()
    return _job_store


_REQUIRED_ENV = [
    "OPENAI_API_KEY",
    "DATABASE_URL",
    "JWT_SECRET",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()
    # Log any missing required env vars at startup
    for var in _REQUIRED_ENV:
        if not os.environ.get(var):
            log_error("env_load", f"Required environment variable '{var}' is not set")
    yield


app = FastAPI(title="Equity Research API", lifespan=lifespan)

_frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
_origins_set = {
    _frontend_url,
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
}
_vercel_url = os.environ.get("VERCEL_URL")
if _vercel_url:
    _origins_set.add(f"https://{_vercel_url}")
    _origins_set.add(f"http://{_vercel_url}")
_allowed_origins = list(_origins_set)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/auth/google")
async def auth_google_login():
    """Redirect to Google OAuth2 consent screen (sets CSRF state cookie)."""
    redirect = RedirectResponse(url="")  # url filled below after state is known
    state = generate_oauth_state(redirect)
    redirect.headers["location"] = google_auth_url(state)
    return redirect


@app.get("/auth/google/callback")
async def auth_google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Handle Google OAuth2 callback."""
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")

    # User denied permission on Google consent screen
    if error:
        log_error("auth_signin", f"User denied Google OAuth consent: {error}")
        return RedirectResponse(url=f"{frontend_url}/?auth_error=access_denied")

    if not code or not state:
        log_error("auth_signin", "OAuth callback missing code or state params")
        return RedirectResponse(url=f"{frontend_url}/?auth_error=missing_params")

    # CSRF check
    try:
        verify_oauth_state(request, state)
    except HTTPException:
        log_error("auth_signin", "OAuth CSRF state mismatch")
        return RedirectResponse(url=f"{frontend_url}/?auth_error=csrf_failed")

    try:
        google_info = await exchange_code_for_user(code)
        user = upsert_user(google_info)
        token = create_access_token(user["id"])
    except Exception as exc:
        import logging
        logging.exception("OAuth callback error: %s", exc)
        log_error("auth_signin", f"OAuth callback server error: {exc}", exc=exc)
        return RedirectResponse(url=f"{frontend_url}/?auth_error=server_error")

    redirect = RedirectResponse(url=f"{frontend_url}/?token={token}")
    redirect.delete_cookie("oauth_state")
    return redirect


@app.post("/auth/logout")
async def auth_logout(request: Request):
    """Revoke the current session server-side."""
    session_id = get_session_id_from_request(request)
    if session_id:
        revoke_session(session_id)
    return {"ok": True}


@app.get("/auth/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@app.get("/api/symbols/suggest")
async def api_symbols_suggest(q: str = ""):
    """Return list of { symbol, name } for typeahead; error if NSE lookup failed."""
    import asyncio
    loop = asyncio.get_event_loop()
    results, error = await loop.run_in_executor(None, symbols_module.suggest, q)
    return {"symbols": results, "error": error}


@app.post("/api/reports")
async def api_reports_create(body: CreateReportRequest):
    """Start a report job; if cached report exists (< 24h), complete immediately with from_cache."""
    symbol = (body.symbol or "").strip().upper()
    exchange = (body.exchange or "NSE").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    report_id = str(uuid.uuid4())
    store = get_store()
    set_pending(store, report_id)
    asyncio.create_task(start_report(report_id, symbol, exchange, store))
    return {"report_id": report_id}


@app.get("/api/reports/{report_id}")
async def api_reports_status(report_id: str):
    """Return { status, report?, error? }. When completed, report is the full JSON payload."""
    store = get_store()
    info = get_report_status(store, report_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return info


@app.get("/api/reports/{report_id}/html")
async def api_reports_html(report_id: str):
    """Deprecated: reports are now returned as JSON in GET /api/reports/{id}. Returns 410 Gone."""
    raise HTTPException(
        status_code=410,
        detail="HTML endpoint deprecated. Use GET /api/reports/{report_id} for JSON report when status is completed.",
    )


@app.get("/api/reports/{report_id}/pdf")
async def api_reports_pdf(report_id: str):
    """Return report as PDF attachment when status is completed."""
    store = get_store()
    job = job_get(store, report_id)
    if job is None or job.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Report not found or not ready")
    payload = job.get("report_payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=404, detail="Report payload missing")
    meta = payload.get("meta") or {}
    symbol = (meta.get("symbol") or "report").upper()
    try:
        pdf_bytes = render_payload_to_pdf(payload)
    except Exception as e:
        log_error("pdf_download", f"PDF render failed for {symbol}: {e}", exc=e, symbol=symbol)
        raise HTTPException(
            status_code=500,
            detail="PDF generation failed. If using WeasyPrint, install system libraries (e.g. on macOS: brew install pango cairo).",
        ) from e
    if not pdf_bytes:
        log_error("pdf_download", f"PDF render returned empty bytes for {symbol}", symbol=symbol)
        raise HTTPException(status_code=500, detail="PDF generation failed")
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="equity-report-{symbol}.pdf"'},
    )


class FeedbackRequest(BaseModel):
    report_id: str
    rating: str  # "up" or "down"
    comment: str | None = None


@app.post("/api/feedback")
async def api_feedback(body: FeedbackRequest, request: Request):
    """Store thumbs up/down and optional comment for a report. User optional."""
    from backend.auth import get_current_user_optional
    rating = (body.rating or "").strip().lower()
    if rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    user = get_current_user_optional(request)
    user_id = user["id"] if user else None
    append_feedback(body.report_id, rating, body.comment, user_id=user_id)
    return {"ok": True}
