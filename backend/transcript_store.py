"""DB helpers for concall_transcripts table."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.db import execute, fetchall, fetchone

log = logging.getLogger(__name__)


def get_stored_transcripts(symbol: str, exchange: str) -> list[dict[str, Any]]:
    """Return up to 8 stored transcripts for symbol/exchange, newest first."""
    try:
        return fetchall(
            """
            SELECT symbol, exchange, segment, transcript_date, link, description, text, stored_at
            FROM concall_transcripts
            WHERE symbol = %s AND exchange = %s
            ORDER BY TO_TIMESTAMP(transcript_date, 'DD-Mon-YYYY HH24:MI:SS') DESC
            LIMIT 8
            """,
            (symbol.upper(), exchange.upper()),
        )
    except Exception as e:
        log.warning("transcript_store.get_stored_transcripts failed: %s", e)
        return []


def get_latest_stored_date(symbol: str, exchange: str) -> str | None:
    """Return the most recent transcript_date string for this symbol, or None."""
    try:
        row = fetchone(
            """
            SELECT transcript_date AS latest FROM concall_transcripts
            WHERE symbol=%s AND exchange=%s
            ORDER BY TO_TIMESTAMP(transcript_date, 'DD-Mon-YYYY HH24:MI:SS') DESC
            LIMIT 1
            """,
            (symbol.upper(), exchange.upper()),
        )
        return row["latest"] if row else None
    except Exception as e:
        log.warning("transcript_store.get_latest_stored_date failed: %s", e)
        return None


def get_latest_stored_at(symbol: str, exchange: str) -> datetime | None:
    """Return MAX(stored_at) for this symbol — used to compare against report generated_at."""
    try:
        row = fetchone(
            "SELECT MAX(stored_at) AS latest FROM concall_transcripts WHERE symbol=%s AND exchange=%s",
            (symbol.upper(), exchange.upper()),
        )
        return row["latest"] if row else None
    except Exception as e:
        log.warning("transcript_store.get_latest_stored_at failed: %s", e)
        return None


def upsert_transcript(
    symbol: str,
    exchange: str,
    segment: str,
    date: str,
    link: str,
    description: str,
    text: str | None,
) -> None:
    """Insert a transcript row. Skips silently on duplicate (symbol, exchange, transcript_date)."""
    try:
        execute(
            """
            INSERT INTO concall_transcripts
              (symbol, exchange, segment, transcript_date, link, description, text)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, exchange, transcript_date) DO NOTHING
            """,
            (
                symbol.upper(),
                exchange.upper(),
                segment,
                date,
                link,
                description,
                text or None,  # Store None (NULL) rather than empty string for retry logic
            ),
        )
    except Exception as e:
        log.warning("transcript_store.upsert_transcript failed for %s/%s %s: %s", symbol, exchange, date, e)


def trim_to_limit(symbol: str, exchange: str, limit: int = 8) -> None:
    """Delete oldest rows beyond `limit`, keeping the most recent ones by transcript_date."""
    try:
        execute(
            """
            DELETE FROM concall_transcripts
            WHERE (symbol, exchange, transcript_date) IN (
                SELECT symbol, exchange, transcript_date
                FROM concall_transcripts
                WHERE symbol = %s AND exchange = %s
                ORDER BY TO_TIMESTAMP(transcript_date, 'DD-Mon-YYYY HH24:MI:SS') DESC
                OFFSET %s
            )
            """,
            (symbol.upper(), exchange.upper(), limit),
        )
    except Exception as e:
        log.warning("transcript_store.trim_to_limit failed for %s/%s: %s", symbol, exchange, e)


def update_transcript_text(symbol: str, exchange: str, date: str, text: str) -> None:
    """Update extracted text for a specific transcript (used when retry succeeds)."""
    try:
        execute(
            """
            UPDATE concall_transcripts
            SET text = %s, stored_at = now()
            WHERE symbol = %s AND exchange = %s AND transcript_date = %s
            """,
            (text, symbol.upper(), exchange.upper(), date),
        )
    except Exception as e:
        log.warning("transcript_store.update_transcript_text failed for %s/%s %s: %s", symbol, exchange, date, e)
