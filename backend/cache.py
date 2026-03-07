"""Report cache: store/load report JSON per symbol+exchange in PostgreSQL (24h TTL)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from backend.db import fetchone, fetchone_with_return

CACHE_TTL_HOURS = 24
logger = logging.getLogger(__name__)


def get_cached_report(symbol: str, exchange: str) -> dict | None:
    """Return cached report payload if present and not expired; else None."""
    try:
        row = fetchone(
            """
            SELECT payload FROM reports
            WHERE symbol = %s AND exchange = %s AND expires_at > now()
            """,
            (symbol.upper(), exchange.upper()),
        )
        return row["payload"] if row else None
    except Exception as e:
        logger.warning("cache lookup failed for %s/%s: %s", symbol, exchange, e)
        return None


def set_cached_report(symbol: str, exchange: str, payload: dict) -> None:
    """Upsert report payload into the reports table with a 24h TTL."""
    try:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=CACHE_TTL_HOURS)
        fetchone_with_return(
            """
            INSERT INTO reports (symbol, exchange, payload, generated_at, expires_at)
            VALUES (%s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (symbol, exchange) DO UPDATE
              SET payload = EXCLUDED.payload,
                  generated_at = EXCLUDED.generated_at,
                  expires_at = EXCLUDED.expires_at
            RETURNING id
            """,
            (
                symbol.upper(),
                exchange.upper(),
                json.dumps(payload),
                now,
                expires_at,
            ),
        )
    except Exception as e:
        logger.warning("cache write failed for %s/%s: %s", symbol, exchange, e)
