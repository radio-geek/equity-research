"""Shared helpers for finfetch-based financial data. finfetch uses NSE symbol (no .NS)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# finfetch column format: "Mar 2024", "Sep 2024" (month name + year)
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        if hasattr(val, "size") and getattr(val, "size", 1):
            val = val.iloc[0] if hasattr(val, "iloc") else val
        f = float(val)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError, IndexError):
        return None


def finfetch_col_to_period_key(col: str) -> str | None:
    """Convert finfetch column 'Sep 2024' or 'Mar 2025' to period_key 'YYYY-MM-DD' (quarter-end)."""
    s = str(col).strip()
    parts = s.split()
    if len(parts) != 2:
        return None
    try:
        month_str, year_str = parts[0], parts[1]
        year = int(year_str)
        if month_str not in MONTH_NAMES:
            return None
        month = MONTH_NAMES.index(month_str) + 1
        # Quarter-end dates: Mar=31, Jun=30, Sep=30, Dec=31
        if month in (3, 12):
            day = 31
        else:
            day = 30
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        return None


def finfetch_col_to_period_label(col: str) -> str:
    """Convert finfetch column to Indian quarter label (e.g. 'Sep 2024' -> 'Q2 FY25')."""
    period_key = finfetch_col_to_period_key(col)
    if not period_key or len(period_key) < 10:
        return str(col)[:15]
    try:
        y, m, d = int(period_key[:4]), int(period_key[5:7]), int(period_key[8:10])
        from src.data.indian_quarters import calendar_date_to_indian_quarter
        return calendar_date_to_indian_quarter(datetime(y, m, d))
    except Exception:
        return str(col)[:15]


def finfetch_col_to_fy_label(col: str) -> str:
    """Convert finfetch column 'Mar 2024' to 'FY24'."""
    s = str(col).strip()
    parts = s.split()
    if len(parts) != 2:
        return str(col)[:10]
    try:
        year = int(parts[1])
        return f"FY{year % 100}"
    except (ValueError, IndexError):
        return str(col)[:10]


def get_finfetch_ticker(symbol: str, exchange: str, view: str = "consolidated"):
    """Return finfetch Ticker for symbol. Do not access .price (can KeyError for some SME).

    view: 'consolidated' (default) or 'standalone'. Consolidated matches Screener consolidated
    when finfetch uses Screener; primary source is MoneyControl which may differ.
    """
    try:
        import finfetch as ff
    except ImportError as e:
        logger.warning("finfetch not available: %s. Install with: pip install finfetch", e)
        return None
    sym = symbol.strip().upper()
    ticker = ff.Ticker(sym, view=view or "consolidated")
    return ticker


def _value_from_df(df: Any, col: Any, *row_keys: str) -> float | None:
    """Get value from DataFrame for row (first match of row_keys) and column col."""
    if df is None or not hasattr(df, "loc"):
        return None
    for rk in row_keys:
        try:
            if rk not in df.index:
                continue
            v = df.loc[rk, col]
            return _safe_float(v)
        except (KeyError, TypeError):
            continue
    return None
