"""Symbol suggestions via NSE.lookup(query)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure repo root is on path so src.config is available
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_nse_download_folder

logger = logging.getLogger(__name__)


def suggest(query: str, limit: int = 15) -> tuple[list[dict[str, str]], str | None]:
    """
    Return (list of { "symbol", "name" }, error_message).
    Uses NSE.lookup(query) with server=False (no httpx required). On failure returns ([], error_message).
    """
    query = (query or "").strip()
    if not query:
        return [], None

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
