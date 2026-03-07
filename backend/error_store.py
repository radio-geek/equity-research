"""Centralised error logging to the error_logs table.

Usage:
    from backend.error_store import log_error

    log_error("report_generate", "Graph raised RuntimeError", detail=traceback, symbol="RELIANCE")

Node names used across the codebase:
    report_generate  – LangGraph pipeline failure
    auth_signin      – Google OAuth callback error
    auth_token       – JWT / session verification error
    pdf_download     – PDF render / download failure
    env_load         – Missing required environment variable
    report_cache     – DB read/write for cached report
    feedback         – Feedback submission error
"""

from __future__ import annotations

import logging
import traceback as tb
from typing import Any

log = logging.getLogger(__name__)


def log_error(
    node: str,
    message: str,
    *,
    detail: str | None = None,
    symbol: str | None = None,
    user_id: int | None = None,
    exc: BaseException | None = None,
) -> None:
    """Insert one row into error_logs. Never raises — DB failures are logged to stderr only."""
    if exc is not None and detail is None:
        detail = "".join(tb.format_exception(type(exc), exc, exc.__traceback__))

    try:
        from backend.db import execute
        execute(
            """
            INSERT INTO error_logs (node, message, detail, symbol, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (node, message, detail, symbol, user_id),
        )
    except Exception as db_err:
        # Don't let DB errors cascade into the caller
        log.error("error_store: failed to write error_log row: %s", db_err)
