"""In-memory job store: report_id -> status, report_path, error."""

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


def set_completed(store: dict[str, Any], report_id: str, report_path: str) -> None:
    with _lock(store):
        if report_id in _jobs(store):
            _jobs(store)[report_id]["status"] = _STATUS_COMPLETED
            _jobs(store)[report_id]["report_path"] = report_path


def set_failed(store: dict[str, Any], report_id: str, error: str) -> None:
    with _lock(store):
        if report_id in _jobs(store):
            _jobs(store)[report_id]["status"] = _STATUS_FAILED
            _jobs(store)[report_id]["error"] = error


def get(store: dict[str, Any], report_id: str) -> dict[str, Any] | None:
    with _lock(store):
        return _jobs(store).get(report_id)
