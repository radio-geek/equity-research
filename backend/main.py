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

from backend.job_store import create_job_store, set_pending
from backend.reports import get_report_html, get_report_status, start_report
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
    """Start a report job in background; return { report_id }."""
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
    """Return { status, report_path?, error? }."""
    store = get_store()
    info = get_report_status(store, report_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return info


@app.get("/api/reports/{report_id}/html")
async def api_reports_html(report_id: str):
    """Return report HTML when status is completed."""
    store = get_store()
    html, content_type = get_report_html(store, report_id)
    if html is None:
        raise HTTPException(status_code=404, detail="Report not found or not ready")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
