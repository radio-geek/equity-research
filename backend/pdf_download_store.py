"""Track PDF download attempts (requested / success / failed) in PostgreSQL."""

from __future__ import annotations

import logging

from backend.db import execute

logger = logging.getLogger(__name__)


def log_pdf_download(
    symbol: str,
    status: str,  # 'requested' | 'success' | 'failed'
    user_id: int | None = None,
    error_detail: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Insert one pdf_downloads row. Silently ignores DB errors."""
    try:
        execute(
            """
            INSERT INTO pdf_downloads (symbol, user_id, status, error_detail, duration_ms)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (symbol, user_id, status, error_detail, duration_ms),
        )
    except Exception as e:
        logger.warning("pdf_downloads write failed for %s: %s", symbol, e)
