"""Concall transcript access.

NSE/BSE do not publish concall transcripts. Free options (Quartr, Trendlyne) are not
programmatic APIs. This module is a stub: returns empty/placeholder so the graph runs.
"""

from __future__ import annotations


def get_concall_transcripts(symbol: str, exchange: str, limit: int = 5) -> list[dict]:
    """Return list of concall transcript entries. Stub: always empty."""
    return []


def get_concall_stub_message() -> str:
    """Message to put in state when no transcripts are available."""
    return (
        "Concall transcripts are not available when using free NSE/BSE data only. "
        "To evaluate management guidance and 'walking the talk', integrate a transcript "
        "source (e.g. Trendlyne, Quartr) later."
    )
