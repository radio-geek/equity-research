"""Report job: run graph in background; cache 24h; status and PDF endpoints."""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

# Ensure repo root is on path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.cache import get_cached_report_if_fresh, set_cached_report
from backend.error_store import log_error
from backend.job_store import (
    get as job_get,
    set_completed_with_payload as job_set_completed_with_payload,
    set_failed as job_set_failed,
    set_running as job_set_running,
)


def _run_report_sync(report_id: str, symbol: str, exchange: str, store: dict, user_id: int | None = None) -> None:
    """Run graph once; update store with report_payload or error; write cache on success."""
    job_set_running(store, report_id)
    t0 = time.monotonic()
    try:
        # Step 0a: Refresh transcript cache (fast when DB is up to date — 1 NSE API call)
        # Wrapped in its own try/except so a cache failure never kills the full report job.
        from src.data.concall import refresh_transcript_cache
        from backend.transcript_store import get_latest_stored_at
        import logging as _logging
        _log = _logging.getLogger(__name__)

        try:
            transcripts_updated = refresh_transcript_cache(symbol, exchange)
        except Exception as _e:
            _log.warning("transcript cache refresh failed for %s (%s) — continuing without cache", symbol, _e)
            transcripts_updated = False

        # Step 0b: Return cached report if transcripts haven't changed
        if not transcripts_updated:
            latest_at = get_latest_stored_at(symbol, exchange)
            cached = get_cached_report_if_fresh(symbol, exchange, latest_at)
            if cached:
                job_set_completed_with_payload(store, report_id, cached, from_cache=True)
                return

        from src.graph import build_graph

        graph = build_graph()
        config = {
            "configurable": {"thread_id": report_id},
            "tags": ["equity-research", symbol, exchange],
            "metadata": {"symbol": symbol, "exchange": exchange},
            "run_name": f"equity-research-{symbol}-{exchange}",
        }
        initial_state = {"symbol": symbol, "exchange": exchange, "messages": []}
        result = graph.invoke(initial_state, config=config)
        values = result if isinstance(result, dict) else getattr(result, "values", result)
        report_payload = values.get("report_payload") if isinstance(values, dict) else None
        if isinstance(report_payload, dict):
            generation_ms = int((time.monotonic() - t0) * 1000)
            set_cached_report(symbol, exchange, report_payload, requested_by=user_id, generation_ms=generation_ms)
            job_set_completed_with_payload(store, report_id, report_payload, from_cache=False)
        else:
            msg = "No report_payload in result"
            job_set_failed(store, report_id, msg)
            log_error("report_generate", msg, symbol=symbol)
    except Exception as e:
        job_set_failed(store, report_id, str(e))
        log_error("report_generate", str(e), exc=e, symbol=symbol)


async def start_report(report_id: str, symbol: str, exchange: str, store: dict, user_id: int | None = None) -> None:
    """Run _run_report_sync in a thread so the event loop is not blocked."""
    import asyncio

    await asyncio.to_thread(_run_report_sync, report_id, symbol, exchange, store, user_id)


def get_report_status(store: dict, report_id: str) -> dict | None:
    """Return { status, report?, from_cache?, error? } or None if unknown."""
    job = job_get(store, report_id)
    if job is None:
        return None
    out = {
        "status": job["status"],
        "error": job.get("error"),
    }
    if job.get("status") == "completed" and "report_payload" in job:
        out["report"] = job["report_payload"]
        if job.get("from_cache"):
            out["from_cache"] = True
    return out
