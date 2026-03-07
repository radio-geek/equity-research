"""Report cache: store/load report JSON per symbol+exchange with 24h TTL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _REPO_ROOT / "cache_data" / "reports"
CACHE_TTL_HOURS = 24


def _cache_path(symbol: str, exchange: str) -> Path:
    key = f"{symbol.upper()}_{exchange.upper()}.json"
    return CACHE_DIR / key


def get_cached_report(symbol: str, exchange: str) -> dict | None:
    """Return cached report payload if present and younger than 24h; else None."""
    path = _cache_path(symbol, exchange)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        generated = data.get("generated_at")
        if not generated:
            return None
        # Parse ISO format
        try:
            if generated.endswith("Z"):
                dt = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(generated)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - dt > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return data.get("payload")
    except (json.JSONDecodeError, OSError):
        return None


def set_cached_report(symbol: str, exchange: str, payload: dict) -> None:
    """Write report payload to cache with current timestamp."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, exchange)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {"generated_at": now, "payload": payload}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
