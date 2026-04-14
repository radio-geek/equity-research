"""Report cache: store/load report JSON per symbol+exchange in PostgreSQL (24h TTL).

get_cached_report()          — simple 24h TTL check (kept for compatibility)
get_cached_report_if_fresh() — checks 24h TTL AND transcript freshness (used by pipeline)
set_cached_report()          — upsert with 24h TTL
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from backend.db import fetchone, fetchone_with_return

CACHE_TTL_HOURS = 24
NO_CONCALL_TTL_DAYS = 7
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


def set_cached_report(
    symbol: str,
    exchange: str,
    payload: dict,
    requested_by: int | None = None,
    generation_ms: int | None = None,
) -> None:
    """Upsert report payload into the reports table with a 24h TTL."""
    try:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=CACHE_TTL_HOURS)
        fetchone_with_return(
            """
            INSERT INTO reports (symbol, exchange, payload, generated_at, expires_at, requested_by, generation_ms)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
            ON CONFLICT (symbol, exchange) DO UPDATE
              SET payload      = EXCLUDED.payload,
                  generated_at = EXCLUDED.generated_at,
                  expires_at   = EXCLUDED.expires_at,
                  requested_by = EXCLUDED.requested_by,
                  generation_ms = EXCLUDED.generation_ms
            RETURNING id
            """,
            (symbol.upper(), exchange.upper(), json.dumps(payload), now, expires_at, requested_by, generation_ms),
        )
    except Exception as e:
        logger.warning("cache write failed for %s/%s: %s", symbol, exchange, e)


def get_cached_report_if_fresh(
    symbol: str, exchange: str, latest_transcript_stored_at: datetime | None
) -> dict | None:
    """Return cached report unless a newer transcript has been stored since it was generated.

    For concall companies: invalidated when a new transcript arrives (quarterly cadence).
    For no-concall companies: invalidated after NO_CONCALL_TTL_DAYS days.
    The expires_at column is ignored here.
    """
    try:
        row = fetchone(
            """
            SELECT payload, generated_at FROM reports
            WHERE symbol = %s AND exchange = %s
            """,
            (symbol.upper(), exchange.upper()),
        )
        if not row:
            return None
        # For concall companies: stale if a newer transcript exists
        if latest_transcript_stored_at and row["generated_at"] < latest_transcript_stored_at:
            logger.info(
                "cache: report for %s/%s is stale (generated=%s, latest_transcript=%s)",
                symbol, exchange, row["generated_at"], latest_transcript_stored_at,
            )
            return None
        # For no-concall companies: apply a time-based TTL
        if latest_transcript_stored_at is None:
            age = datetime.now(timezone.utc) - row["generated_at"]
            if age.days >= NO_CONCALL_TTL_DAYS:
                logger.info(
                    "cache: no-concall report for %s/%s is %d days old, regenerating",
                    symbol, exchange, age.days,
                )
                return None
        return row["payload"]
    except Exception as e:
        logger.warning("cache freshness lookup failed for %s/%s: %s", symbol, exchange, e)
        return None
