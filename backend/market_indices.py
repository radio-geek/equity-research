"""Fetch live Indian market index quotes via yfinance.

Indices:
  ^NSEI      → Nifty 50
  ^BSESN     → Sensex
  ^NSEBANK   → Nifty Bank

In-memory cache (60 s TTL) so we don't hit Yahoo Finance on every page load.
yfinance is sync; fetch_market_indices() runs it in a thread pool.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_SYMBOLS = ["^NSEI", "^BSESN", "^NSEBANK"]
_DISPLAY_NAMES = {"^NSEI": "Nifty 50", "^BSESN": "Sensex", "^NSEBANK": "Nifty Bank"}
_CACHE_TTL = 60  # seconds

_cache: dict[str, Any] = {"data": None, "ts": 0.0}


def _fmt_value(price: float) -> str:
    return f"{price:,.2f}"


def _fmt_change(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _fetch_sync() -> list[dict]:
    import yfinance as yf
    data: list[dict] = []
    for sym in _SYMBOLS:
        try:
            fi = yf.Ticker(sym).fast_info
            price: float = fi.last_price
            prev_close: float = fi.regular_market_previous_close
            if price and prev_close:
                pct = ((price - prev_close) / prev_close) * 100
                data.append({
                    "name": _DISPLAY_NAMES.get(sym, sym),
                    "value": _fmt_value(price),
                    "change": _fmt_change(pct),
                    "positive": pct >= 0,
                })
        except Exception as e:
            logger.warning("market_indices: failed for %s: %s", sym, e)
    return data


async def fetch_market_indices() -> list[dict]:
    """Return live index data. Uses 60 s cache; falls back to last good data on error."""
    now = time.monotonic()
    if _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]

    try:
        data = await asyncio.get_event_loop().run_in_executor(None, _fetch_sync)
    except Exception as e:
        logger.warning("market_indices: fetch failed: %s", e)
        return _cache["data"] or []

    if data:
        _cache["data"] = data
        _cache["ts"] = now

    return data or (_cache["data"] or [])
