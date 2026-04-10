"""In-memory job store: report_id -> status, report_payload, error."""

from __future__ import annotations

import threading
from typing import Any

_STATUS_PENDING = "pending"
_STATUS_RUNNING = "running"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"


def create_job_store() -> dict[str, Any]:
    """Return a new job store (dict) and its lock. Caller holds the dict; use lock for access."""
    return {"_lock": threading.Lock(), "_jobs": {}}


def _jobs(store: dict[str, Any]) -> dict:
    return store["_jobs"]


def _lock(store: dict[str, Any]) -> threading.Lock:
    return store["_lock"]


def set_pending(store: dict[str, Any], report_id: str) -> None:
    with _lock(store):
        _jobs(store)[report_id] = {"status": _STATUS_PENDING}


def set_running(store: dict[str, Any], report_id: str) -> None:
    with _lock(store):
        if report_id in _jobs(store):
            _jobs(store)[report_id]["status"] = _STATUS_RUNNING
            _jobs(store)[report_id]["progress"] = 5
            _jobs(store)[report_id]["stage"] = "Starting research job…"


def set_progress(
    store: dict[str, Any], report_id: str, progress: int, stage: str | None = None
) -> None:
    """Best-effort monotonic progress 0–100 for polling UI; optional short stage label."""
    with _lock(store):
        job = _jobs(store).get(report_id)
        if job is None:
            return
        p = max(0, min(100, int(progress)))
        prev = int(job.get("progress", 0))
        if p < prev:
            return
        job["progress"] = p
        if stage is not None:
            job["stage"] = stage


def set_completed(store: dict[str, Any], report_id: str, report_path: str) -> None:
    with _lock(store):
        if report_id in _jobs(store):
            _jobs(store)[report_id]["status"] = _STATUS_COMPLETED
            _jobs(store)[report_id]["report_path"] = report_path


def set_completed_with_payload(
    store: dict[str, Any], report_id: str, payload: dict, from_cache: bool = False
) -> None:
    """Mark job completed and store the report JSON payload. Optionally set from_cache=True."""
    with _lock(store):
        if report_id in _jobs(store):
            _jobs(store)[report_id]["status"] = _STATUS_COMPLETED
            _jobs(store)[report_id]["report_payload"] = payload
            if from_cache:
                _jobs(store)[report_id]["from_cache"] = True


def set_failed(store: dict[str, Any], report_id: str, error: str) -> None:
    with _lock(store):
        if report_id in _jobs(store):
            _jobs(store)[report_id]["status"] = _STATUS_FAILED
            _jobs(store)[report_id]["error"] = error


def get(store: dict[str, Any], report_id: str) -> dict[str, Any] | None:
    with _lock(store):
        return _jobs(store).get(report_id)
