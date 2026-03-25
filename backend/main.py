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
    get_current_user_optional,
    get_session_id_from_request,
    google_auth_url,
    revoke_session,
    upsert_user,
    verify_oauth_state,
)
from backend.db import fetchone as db_fetchone
from backend.error_store import log_error
from backend.section_feedback_store import append_section_feedback
from backend.job_store import create_job_store, get as job_get, set_pending
from backend.pdf_render import render_payload_to_pdf
from backend.pdf_download_store import log_pdf_download
from backend.market_indices import fetch_market_indices
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

_origins_set: set[str] = set()


def _add_allowed_origin(url: str) -> None:
    u = url.strip().rstrip("/")
    if u:
        _origins_set.add(u)


_add_allowed_origin(os.environ.get("FRONTEND_URL", "http://localhost:5173"))
for _p in range(5173, 5190):
    _add_allowed_origin(f"http://localhost:{_p}")
    _add_allowed_origin(f"http://127.0.0.1:{_p}")
_add_allowed_origin("http://localhost:3000")
_add_allowed_origin("http://127.0.0.1:3000")
_vercel_url = os.environ.get("VERCEL_URL")
if _vercel_url:
    _add_allowed_origin(f"https://{_vercel_url}")
    _add_allowed_origin(f"http://{_vercel_url}")
_extra = os.environ.get("ADDITIONAL_CORS_ORIGINS", "")
for origin in _extra.split(","):
    _add_allowed_origin(origin)
_allowed_origins = list(_origins_set)


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    return origin.strip().rstrip("/") in _origins_set


def _frontend_base_for_oauth(request: Request) -> str:
    raw = request.cookies.get("oauth_client_origin")
    if raw and _origin_allowed(raw):
        return raw.strip().rstrip("/")
    return os.environ.get("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _valid_return_path(path: str | None) -> bool:
    """Return True if path is a safe relative path (no open redirect)."""
    if not path or not path.startswith("/"):
        return False
    if "//" in path or ":" in path:
        return False
    return True


@app.get("/auth/google")
async def auth_google_login(
    return_to: str | None = None,
    client_origin: str | None = None,
):
    """Redirect to Google OAuth2 consent screen (sets CSRF state cookie).
    If return_to is a safe path, redirect back there after login."""
    redirect = RedirectResponse(url="")  # url filled below after state is known
    state = generate_oauth_state(redirect)
    if _valid_return_path(return_to):
        redirect.set_cookie(
            key="oauth_return_to",
            value=return_to,
            httponly=True,
            samesite="lax",
            max_age=600,
        )
    if client_origin and _origin_allowed(client_origin):
        redirect.set_cookie(
            key="oauth_client_origin",
            value=client_origin.strip().rstrip("/"),
            httponly=True,
            samesite="lax",
            max_age=600,
        )
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

    def _auth_error_redirect(code_err: str) -> RedirectResponse:
        base = _frontend_base_for_oauth(request)
        r = RedirectResponse(url=f"{base}/?auth_error={code_err}")
        r.delete_cookie("oauth_state")
        r.delete_cookie("oauth_return_to")
        r.delete_cookie("oauth_client_origin")
        return r

    # User denied permission on Google consent screen
    if error:
        log_error("auth_signin", f"User denied Google OAuth consent: {error}")
        return _auth_error_redirect("access_denied")

    if not code or not state:
        log_error("auth_signin", "OAuth callback missing code or state params")
        return _auth_error_redirect("missing_params")

    # CSRF check
    try:
        verify_oauth_state(request, state)
    except HTTPException:
        log_error("auth_signin", "OAuth CSRF state mismatch")
        return _auth_error_redirect("csrf_failed")

    frontend_url = _frontend_base_for_oauth(request)

    try:
        google_info = await exchange_code_for_user(code)
        user = upsert_user(google_info)
        token = create_access_token(
            user["id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as exc:
        import logging
        logging.exception("OAuth callback error: %s", exc)
        log_error("auth_signin", f"OAuth callback server error: {exc}", exc=exc)
        return _auth_error_redirect("server_error")

    return_to = request.cookies.get("oauth_return_to")
    if _valid_return_path(return_to):
        sep = "&" if "?" in return_to else "?"
        redirect_url = f"{frontend_url}{return_to}{sep}token={token}"
        redirect = RedirectResponse(url=redirect_url)
        redirect.delete_cookie("oauth_return_to")
    else:
        redirect = RedirectResponse(url=f"{frontend_url}/?token={token}")
    redirect.delete_cookie("oauth_state")
    redirect.delete_cookie("oauth_client_origin")
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


@app.get("/api/market-indices")
async def api_market_indices():
    """Return live Nifty 50, Sensex, Nifty Bank quotes from Yahoo Finance (60 s cache)."""
    data = await fetch_market_indices()
    return {"indices": data}


@app.get("/api/symbols/suggest")
async def api_symbols_suggest(q: str = ""):
    """Return list of { symbol, name } for typeahead; error if NSE lookup failed."""
    import asyncio
    loop = asyncio.get_event_loop()
    results, error = await loop.run_in_executor(None, symbols_module.suggest, q)
    return {"symbols": results, "error": error}


@app.post("/api/reports")
async def api_reports_create(body: CreateReportRequest, request: Request):
    """Start a report job; if cached report exists (< 24h), complete immediately with from_cache."""
    symbol = (body.symbol or "").strip().upper()
    exchange = (body.exchange or "NSE").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    user = get_current_user_optional(request)
    user_id: int | None = user["id"] if user else None
    report_id = str(uuid.uuid4())
    store = get_store()
    set_pending(store, report_id)
    asyncio.create_task(start_report(report_id, symbol, exchange, store, user_id=user_id))
    return {"report_id": report_id}


@app.get("/api/reports/{report_id}")
async def api_reports_status(report_id: str):
    """Return { status, report?, error? }. When completed, report is the full JSON payload.
    Premium sections (concall, sectoral) are gated by blur/sign-in on the frontend."""
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
async def api_reports_pdf(report_id: str, current_user: dict = Depends(get_current_user)):
    """Return report as PDF attachment when status is completed. Requires authentication."""
    import time
    store = get_store()
    job = job_get(store, report_id)
    if job is None or job.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Report not found or not ready")
    payload = job.get("report_payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=404, detail="Report payload missing")
    meta = payload.get("meta") or {}
    symbol = (meta.get("symbol") or "report").upper()
    user_id: int | None = current_user.get("id") if current_user else None

    log_pdf_download(symbol, "requested", user_id=user_id)
    t0 = time.monotonic()
    try:
        pdf_bytes = await asyncio.to_thread(render_payload_to_pdf, payload)
    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log_error("pdf_download", f"PDF render failed for {symbol}: {e}", exc=e, symbol=symbol)
        log_pdf_download(symbol, "failed", user_id=user_id, error_detail=str(e), duration_ms=duration_ms)
        raise HTTPException(status_code=500, detail=str(e)) from e
    if not pdf_bytes:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log_error("pdf_download", f"PDF render returned empty bytes for {symbol}", symbol=symbol)
        log_pdf_download(symbol, "failed", user_id=user_id, error_detail="empty bytes", duration_ms=duration_ms)
        raise HTTPException(status_code=500, detail="PDF generation failed")
    duration_ms = int((time.monotonic() - t0) * 1000)
    log_pdf_download(symbol, "success", user_id=user_id, duration_ms=duration_ms)
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="equity-report-{symbol}.pdf"'},
    )


class DetailedFeedbackRequest(BaseModel):
    symbol: str
    section_ratings: dict  # { "section_name": rating_int }
    suggestion: str | None = None


@app.post("/api/feedback/detailed")
async def api_feedback_detailed(body: DetailedFeedbackRequest, request: Request):
    """Store per-section star ratings and optional suggestion. User optional."""
    user = get_current_user_optional(request)
    user_id = user["id"] if user else None
    report_row = db_fetchone(
        "SELECT id FROM reports WHERE symbol = %s ORDER BY generated_at DESC LIMIT 1",
        (body.symbol.upper(),),
    )
    report_id: int | None = report_row["id"] if report_row else None
    append_section_feedback(body.symbol, body.section_ratings, body.suggestion, user_id=user_id, report_id=report_id)
    return {"ok": True}
