"""Store trade journal entries in the trade_journal table."""

from __future__ import annotations

import logging
from backend.db import execute, fetchall, fetchone, fetchone_with_return

logger = logging.getLogger(__name__)


def get_entries_for_user(user_id: int) -> list[dict]:
    """Return all journal entries for a user, ordered by symbol then trade_date."""
    return fetchall(
        """
        SELECT id, symbol, action, trade_date::text AS trade_date, thesis, created_at
        FROM trade_journal
        WHERE user_id = %s
        ORDER BY symbol ASC, trade_date ASC, created_at ASC
        """,
        (user_id,),
    )


def has_buy_entry(user_id: int, symbol: str) -> bool:
    """Return True if the user has at least one buy entry for this symbol."""
    row = fetchone(
        """
        SELECT 1 FROM trade_journal
        WHERE user_id = %s AND symbol = %s AND action = 'buy'
        LIMIT 1
        """,
        (user_id, symbol.upper()),
    )
    return row is not None


def add_entry(
    user_id: int,
    symbol: str,
    action: str,
    trade_date: str,
    thesis: str,
) -> dict:
    """Insert a new journal entry and return the created row."""
    return fetchone_with_return(
        """
        INSERT INTO trade_journal (user_id, symbol, action, trade_date, thesis)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, symbol, action, trade_date::text AS trade_date, thesis, created_at
        """,
        (user_id, symbol.upper(), action, trade_date, thesis),
    )
