"""Symbol suggestions via NSE.lookup(query), with a Screener.in search fallback.

NSE's autocomplete API sits behind Akamai bot protection that can block server-side
requests (even with valid session cookies) with a spoofed 404 page. When that happens,
fall back to Screener.in's public search API, which returns the NSE/BSE symbol in its
result URL (e.g. "/company/RELIANCE/consolidated/").
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import requests

# Ensure repo root is on path so src.config is available
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_nse_download_folder

logger = logging.getLogger(__name__)

SCREENER_SEARCH_URL = "https://www.screener.in/api/company/search/"
SCREENER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _suggest_via_nse(query: str, limit: int) -> tuple[list[dict[str, str]], str | None]:
    try:
        from nse import NSE
    except ModuleNotFoundError as e:
        if e.name == "nse":
            return [], (
                "Backend is missing the 'nse' package. "
                "Activate your project venv and run: pip install -r requirements.txt"
            )
        raise

    try:
        folder = get_nse_download_folder()
        with NSE(str(folder), server=False) as nse:
            result = nse.lookup(query=query)
    except Exception as e:
        logger.warning("NSE lookup failed: %s", e, exc_info=True)
        return [], str(e)

    symbols = result.get("symbols") if isinstance(result, dict) else None
    if not isinstance(symbols, list):
        return [], None

    out: list[dict[str, str]] = []
    for item in symbols[:limit]:
        if not isinstance(item, dict):
            continue
        sym = item.get("symbol") or ""
        name = item.get("symbol_info") or sym
        if sym:
            out.append({"symbol": str(sym).strip(), "name": str(name).strip()})
    return out, None


def _suggest_via_screener(query: str, limit: int) -> tuple[list[dict[str, str]], str | None]:
    try:
        r = requests.get(
            SCREENER_SEARCH_URL,
            params={"q": query},
            headers={"User-Agent": SCREENER_USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json()
    except Exception as e:
        logger.warning("Screener search fallback failed: %s", e, exc_info=True)
        return [], str(e)

    if not isinstance(results, list):
        return [], None

    out: list[dict[str, str]] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or ""
        parts = [p for p in url.split("/") if p]
        sym = parts[1] if len(parts) > 1 and parts[0] == "company" else ""
        name = item.get("name") or sym
        if sym:
            out.append({"symbol": str(sym).strip().upper(), "name": str(name).strip()})
    return out, None


def suggest(query: str, limit: int = 15) -> tuple[list[dict[str, str]], str | None]:
    """
    Return (list of { "symbol", "name" }, error_message).
    Tries NSE.lookup(query) first; falls back to Screener.in search if NSE is
    unreachable/blocked. Error is only returned if both sources fail.
    """
    query = (query or "").strip()
    if not query:
        return [], None

    out, error = _suggest_via_nse(query, limit)
    if out:
        return out, None

    fallback_out, fallback_error = _suggest_via_screener(query, limit)
    if fallback_out:
        return fallback_out, None

    return [], fallback_error or error
