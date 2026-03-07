"""FastAPI app: symbol suggest, report job start/status/html."""

from __future__ import annotations

import asyncio
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
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

from backend.cache import get_cached_report
from backend.feedback_store import append_feedback
from backend.job_store import create_job_store, get as job_get, set_completed_with_payload, set_pending
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()
    yield
    # optional: clear jobs on shutdown
    pass


app = FastAPI(title="Equity Research API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    cached = get_cached_report(symbol, exchange)
    if cached is not None:
        set_pending(store, report_id)
        set_completed_with_payload(store, report_id, cached, from_cache=True)
        return {"report_id": report_id}
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
    try:
        pdf_bytes = render_payload_to_pdf(payload)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="PDF generation failed. If using WeasyPrint, install system libraries (e.g. on macOS: brew install pango cairo).",
        ) from e
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="PDF generation failed")
    meta = payload.get("meta") or {}
    symbol = (meta.get("symbol") or "report").upper()
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
async def api_feedback(body: FeedbackRequest):
    """Store thumbs up/down and optional comment for a report."""
    rating = (body.rating or "").strip().lower()
    if rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    append_feedback(body.report_id, rating, body.comment)
    return {"ok": True}
