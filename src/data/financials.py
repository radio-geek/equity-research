"""Financial ratios (ROE, ROCE, D/E, etc.) from fundamental data.

Uses finfetch when available (NSE symbol). Returns list of {metric, value, period}.
"""

from __future__ import annotations

import logging
from typing import Any

from src.data.finfetch_helpers import _safe_float, get_finfetch_ticker, _value_from_df

logger = logging.getLogger(__name__)


def _finfetch_ratios(symbol: str, exchange: str) -> list[dict[str, Any]]:
    """Fetch ratios via finfetch. Returns list of {metric, value, period}."""
    ticker = get_finfetch_ticker(symbol, exchange)
    if ticker is None:
        return []

    ratios: list[dict[str, Any]] = []
    try:
        r = ticker.ratios
        if r is None or not hasattr(r, "columns") or len(r.columns) == 0:
            return ratios
        col = r.columns[0]  # latest period
        period = "Latest"

        # finfetch ratios index: return_on_networth_equity, net_profit_margin, total_debt_equity_x, roce_pct
        roe = _value_from_df(r, col, "return_on_networth_equity", "roe_pct")
        if roe is not None:
            ratios.append({"metric": "ROE %", "value": round(roe, 2), "period": period})

        npm = _value_from_df(r, col, "net_profit_margin", "npm_pct")
        if npm is not None:
            ratios.append({"metric": "Net Margin %", "value": round(npm, 2), "period": period})

        de = _value_from_df(r, col, "total_debt_equity_x", "debt_equity_ratio", "total_debt_equity")
        if de is not None:
            ratios.append({"metric": "Debt/Equity", "value": round(de, 2), "period": period})

        # Debt/Assets: from balance sheet if not in ratios
        bs = ticker.balance_sheet
        if bs is not None and len(bs.columns) > 0:
            c = bs.columns[0]
            total_assets = _value_from_df(bs, c, "total_assets")
            total_borrowings = _value_from_df(bs, c, "total_borrowings")
            if total_assets is not None and total_assets != 0 and total_borrowings is not None:
                ratios.append({
                    "metric": "Debt/Assets",
                    "value": round(total_borrowings / total_assets, 2),
                    "period": period,
                })
    except Exception as e:
        logger.warning("finfetch ratios failed for %s: %s", symbol, e)
    return ratios


def get_financial_ratios(symbol: str, exchange: str) -> list[dict[str, Any]]:
    """Return list of ratio dicts (metric, value, period) for the given symbol."""
    return _finfetch_ratios(symbol, exchange)
