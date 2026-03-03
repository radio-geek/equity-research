"""NSE India API wrapper: company meta, quote, shareholding.

Uses the unofficial nse package (NseIndiaApi). Rate-limited to avoid overloading NSE.
Transient errors (timeout, connection) are retried once.
"""

import time
from pathlib import Path

from nse import NSE


_RATE_LIMIT_SLEEP = 0.5
_LAST_CALL_TIME: float = 0
_MAX_RETRIES = 2


def _rate_limit() -> None:
    global _LAST_CALL_TIME
    now = time.monotonic()
    elapsed = now - _LAST_CALL_TIME
    if elapsed < _RATE_LIMIT_SLEEP:
        time.sleep(_RATE_LIMIT_SLEEP - elapsed)
    _LAST_CALL_TIME = time.monotonic()


def _call_nse(symbol: str, download_folder: Path | None, op: str, **kwargs) -> dict | list:
    folder = str(download_folder) if download_folder else ""
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            with NSE(folder, server=False) as nse:
                _rate_limit()
                if op == "meta":
                    return nse.equityMetaInfo(symbol)
                if op == "quote":
                    try:
                        out = nse.quote(symbol, section="trade_info")
                    except (ValueError, KeyError, TypeError):
                        out = nse.quote(symbol)
                    return out
                if op == "shareholding":
                    return nse.shareholding(symbol, index="equities")
        except (TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(1.0)
    raise last_err or RuntimeError("NSE call failed")


def get_meta(symbol: str, download_folder: Path | None = None) -> dict:
    """Fetch equity meta info: name, industry, ISIN, status."""
    return _call_nse(symbol, download_folder, "meta")


def get_quote(symbol: str, download_folder: Path | None = None) -> dict:
    """Fetch quote and trade info (price, market cap, etc.)."""
    return _call_nse(symbol, download_folder, "quote")


def get_shareholding(symbol: str, download_folder: Path | None = None) -> list:
    """Fetch shareholding pattern (quarterly). Latest quarter first."""
    return _call_nse(symbol, download_folder, "shareholding")
