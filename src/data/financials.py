"""Financial ratios (ROE, ROCE, D/E, etc.) from NSE/fundamental data.

Uses nifpy when available (expects symbol.NS e.g. RELIANCE.NS). Falls back to empty list if unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _nifpy_ratios(symbol_ns: str) -> list[dict[str, Any]]:
    """Fetch financials via nifpy and derive ratios. Returns list of {metric, value, period}."""
    try:
        import nifpy
    except ImportError as e:
        logger.warning(
            "nifpy unavailable (missing dependency?): %s. Financial ratios will be empty. "
            "Install with: pip install nifpy yfinance lxml beautifulsoup4 requests",
            e,
        )
        return []

    ratios: list[dict[str, Any]] = []
    try:
        income = nifpy.get_income_statement(symbol_ns)
        balance = nifpy.get_balance_sheet(symbol_ns)
        if income is None or balance is None:
            return ratios
        # nifpy returns pandas DataFrames: index = line items, columns = dates (latest first)
        def _first(df, *keys):
            for k in keys:
                try:
                    row = df.loc[k]
                    val = row.iloc[0] if hasattr(row, "iloc") else row
                    if val is not None and (isinstance(val, (int, float)) or (hasattr(val, "size") and val.size)):
                        return float(val)
                except (KeyError, IndexError, TypeError):
                    continue
            return None

        rev = _first(income, "Total Revenue", "Revenue")
        net_income = _first(income, "Net Income", "Net Income Common Stockholders")
        equity = _first(balance, "Total Stockholder Equity", "Total Equity Gross Minority Interest")
        total_assets = _first(balance, "Total Assets")
        long_debt = _first(balance, "Long Term Debt") or 0.0
        short_debt = _first(balance, "Short Term Debt") or 0.0
        total_debt = long_debt + short_debt

        if rev and net_income and rev != 0:
            ratios.append({"metric": "Net Margin %", "value": round(100 * net_income / rev, 2), "period": "TTM"})
        if equity and net_income and equity != 0:
            ratios.append({"metric": "ROE %", "value": round(100 * net_income / equity, 2), "period": "TTM"})
        if total_assets and total_assets != 0:
            ratios.append({"metric": "Debt/Assets", "value": round(total_debt / total_assets, 2), "period": "Latest"})
        if equity and equity != 0:
            ratios.append({"metric": "Debt/Equity", "value": round(total_debt / equity, 2), "period": "Latest"})
    except Exception as e:
        logger.warning("nifpy financials failed for %s: %s", symbol_ns, e)
    return ratios


def get_financial_ratios(symbol: str, exchange: str) -> list[dict[str, Any]]:
    """Return list of ratio dicts (metric, value, period) for the given symbol.

    For NSE, symbol is converted to SYMBOL.NS for nifpy.
    """
    if exchange.upper() == "NSE":
        symbol_ns = f"{symbol.upper()}.NS"
    else:
        symbol_ns = symbol.upper()
    return _nifpy_ratios(symbol_ns)
