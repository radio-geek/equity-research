"""Corporate filings / governance data.

Thin adapter: fetches what is available from NSE (e.g. shareholding is in nse_client).
Full annual report text is not fetched here; optional for future.
"""

from __future__ import annotations

# Filings list/links could be added via NSE announcements or similar.
# For v1 we rely on shareholding + meta from nse_client; no extra filings fetch.
# This module exists for a future filings adapter.


def get_filings_summary(symbol: str) -> str:
    """Return a short placeholder. Real implementation would fetch NSE filings list."""
    return f"No additional filings data fetched for {symbol}. Use shareholding and company meta from NSE."
