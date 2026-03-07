"""Store feedback (thumbs up/down + optional comment) in PostgreSQL."""

from __future__ import annotations

import logging

from backend.db import execute

logger = logging.getLogger(__name__)


def append_feedback(
    report_id: str,
    rating: str,
    comment: str | None = None,
    user_id: int | None = None,
) -> None:
    """Insert one feedback entry. rating is 'up' or 'down'."""
    try:
        execute(
            """
            INSERT INTO feedback (report_id, user_id, rating, comment)
            VALUES (%s, %s, %s, %s)
            """,
            (report_id, user_id, rating, comment or ""),
        )
    except Exception as e:
        logger.warning("feedback write failed for report %s: %s", report_id, e)
