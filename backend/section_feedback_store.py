"""Store per-section star ratings and suggestion text in PostgreSQL."""

from __future__ import annotations

import json
import logging

from backend.db import execute

logger = logging.getLogger(__name__)


def append_section_feedback(
    symbol: str,
    section_ratings: dict,
    suggestion: str | None = None,
    user_id: int | None = None,
) -> None:
    """Insert one section-feedback entry.

    section_ratings: dict mapping section name → int rating (1-5)
    """
    try:
        execute(
            """
            INSERT INTO section_feedback (symbol, user_id, section_ratings, suggestion)
            VALUES (%s, %s, %s, %s)
            """,
            (symbol, user_id, json.dumps(section_ratings), suggestion or None),
        )
    except Exception as e:
        logger.warning("section_feedback write failed for symbol %s: %s", symbol, e)
