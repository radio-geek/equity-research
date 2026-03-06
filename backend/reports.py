"""Report job: run graph in background; status and HTML endpoints."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Ensure repo root is on path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.job_store import (
    get as job_get,
    set_completed as job_set_completed,
    set_failed as job_set_failed,
    set_running as job_set_running,
)


def _run_report_sync(report_id: str, symbol: str, exchange: str, store: dict) -> None:
    """Run graph once; update store with report_path or error. Blocks."""
    job_set_running(store, report_id)
    try:
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
        report_path = values.get("report_path") if isinstance(values, dict) else None
        if report_path:
            job_set_completed(store, report_id, str(report_path))
        else:
            job_set_failed(store, report_id, "No report_path in result")
    except Exception as e:
        job_set_failed(store, report_id, str(e))


async def start_report(report_id: str, symbol: str, exchange: str, store: dict) -> None:
    """Run _run_report_sync in a thread so the event loop is not blocked."""
    import asyncio

    await asyncio.to_thread(_run_report_sync, report_id, symbol, exchange, store)


def get_report_status(store: dict, report_id: str) -> dict | None:
    """Return { status, report_path?, error? } or None if unknown."""
    job = job_get(store, report_id)
    if job is None:
        return None
    return {
        "status": job["status"],
        "report_path": job.get("report_path"),
        "error": job.get("error"),
    }


def get_report_html(store: dict, report_id: str) -> tuple[str | None, str | None]:
    """
    Return (html_content, content_type) for the report HTML.
    content_type is "text/html" or None if not found/failed.
    """
    job = job_get(store, report_id)
    if job is None or job.get("status") != "completed":
        return None, None
    path_str = job.get("report_path")
    if not path_str:
        return None, None
    path = Path(path_str)
    if not path.is_file():
        return None, None
    try:
        return path.read_text(encoding="utf-8"), "text/html"
    except Exception:
        return None, None
