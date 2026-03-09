"""Quarterly financials from finfetch (last N quarters, Indian FY, Crores, QoQ)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.data.finfetch_helpers import (
    _safe_float,
    get_finfetch_ticker,
    _value_from_df,
    finfetch_col_to_period_key,
    finfetch_col_to_period_label,
)
logger = logging.getLogger(__name__)

# finfetch returns values in Crores already
CRORE = 1e7


def fetch_quarterly_financials(
    symbol: str,
    exchange: str,
    max_quarters: int = 8,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fetch quarterly financials via finfetch; return last max_quarters in chronological order.

    Each dict: period, period_label, revenue_cr, ebitda_cr, pat_cr, cfo_cr, debt_equity,
    and *_qoq_pct (None for first quarter). Values in Crores; debt_equity is ratio.
    """
    ticker = get_finfetch_ticker(symbol, exchange)
    if ticker is None:
        return []

    try:
        q = ticker.quarterly_financials
        if q is None or not hasattr(q, "columns") or len(q.columns) == 0:
            return []
    except Exception as e:
        logger.warning("finfetch quarterly_financials failed for %s: %s", symbol, e)
        return []

    bs = None
    cf = None
    try:
        bs = ticker.balance_sheet
        cf = ticker.cashflow
    except Exception:
        pass

    # Build (col, period_key, period_label) for each quarter column, sort chronological, take last max_quarters
    col_order: list[tuple[Any, str, str]] = []
    for col in q.columns:
        pk = finfetch_col_to_period_key(str(col))
        pl = finfetch_col_to_period_label(str(col)) if pk else str(col)
        col_order.append((col, pk or str(col), pl))
    col_order.sort(key=lambda x: x[1] if len(x[1]) == 10 else "0000-00-00")
    col_order = col_order[-max_quarters:]

    results: list[dict[str, Any]] = []
    for col, period_key, period_label in col_order:
        revenue_cr = _value_from_df(q, col, "revenue")
        if revenue_cr is not None:
            revenue_cr = round(revenue_cr, 2)  # finfetch already in Cr
        ebitda_cr = _value_from_df(q, col, "operating_profit", "pbdit")  # proxy for ebitda
        if ebitda_cr is not None:
            ebitda_cr = round(ebitda_cr, 2)
        pat_cr = _value_from_df(q, col, "net_profit")
        if pat_cr is not None:
            pat_cr = round(pat_cr, 2)

        cfo_cr = None
        if cf is not None and hasattr(cf, "columns") and col in cf.columns:
            cfo_cr = _value_from_df(cf, col, "cfo")
            if cfo_cr is not None:
                cfo_cr = round(cfo_cr, 2)

        debt_equity = None
        if bs is not None and hasattr(bs, "columns") and col in bs.columns:
            borrowings = _value_from_df(bs, col, "total_borrowings") or 0.0
            equity = _value_from_df(bs, col, "shareholders_funds")
            if equity is not None and equity != 0:
                debt_equity = round(borrowings / equity, 2)

        results.append({
            "period": period_key,
            "period_label": period_label,
            "revenue_cr": revenue_cr,
            "ebitda_cr": ebitda_cr,
            "pat_cr": pat_cr,
            "cfo_cr": cfo_cr,
            "debt_equity": debt_equity,
            "revenue_qoq_pct": None,
            "ebitda_qoq_pct": None,
            "pat_qoq_pct": None,
            "cfo_qoq_pct": None,
            "debt_equity_qoq_pct": None,
        })

    def _qoq_pct(cur: float | None, prev: float | None) -> float | None:
        if cur is None or prev is None or prev == 0:
            return None
        return round((cur - prev) / prev * 100, 2)

    for i in range(1, len(results)):
        r, p = results[i], results[i - 1]
        r["revenue_qoq_pct"] = _qoq_pct(r.get("revenue_cr"), p.get("revenue_cr"))
        r["ebitda_qoq_pct"] = _qoq_pct(r.get("ebitda_cr"), p.get("ebitda_cr"))
        r["pat_qoq_pct"] = _qoq_pct(r.get("pat_cr"), p.get("pat_cr"))
        r["cfo_qoq_pct"] = _qoq_pct(r.get("cfo_cr"), p.get("cfo_cr"))
        r["debt_equity_qoq_pct"] = _qoq_pct(r.get("debt_equity"), p.get("debt_equity"))

    return results


def _series_to_text_finfetch(df: Any, col: Any, in_crores: bool = True) -> str:
    """Format one column of a finfetch DataFrame as 'Line Item: value' lines. finfetch already in Cr."""
    if df is None or not hasattr(df, "index"):
        return ""
    lines: list[str] = []
    for idx in df.index:
        try:
            v = df.loc[idx, col]
            f = _safe_float(v)
            if f is None:
                continue
            if in_crores:
                lines.append(f"{idx}: {round(f, 2)} Cr")
            else:
                lines.append(f"{idx}: {f}")
        except (KeyError, TypeError):
            continue
    return "\n".join(lines)


def get_latest_quarter_statements(
    symbol: str,
    exchange: str,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Return latest quarter's income statement and balance sheet as text for prompt.

    Uses the most recent column from finfetch quarterly data.
    Keys: period_label, period_key, income_statement_text, balance_sheet_text.
    """
    ticker = get_finfetch_ticker(symbol, exchange)
    if ticker is None:
        return {}

    try:
        q = ticker.quarterly_financials
        bs = ticker.balance_sheet
    except Exception as e:
        logger.warning("get_latest_quarter_statements finfetch failed for %s: %s", symbol, e)
        return {}

    if q is None or not hasattr(q, "columns") or len(q.columns) == 0:
        return {}

    col = q.columns[0]
    period_key = finfetch_col_to_period_key(str(col)) or str(col)
    period_label = finfetch_col_to_period_label(str(col))

    income_text = _series_to_text_finfetch(q, col, in_crores=True)
    balance_text = ""
    if bs is not None and hasattr(bs, "columns") and len(bs.columns) > 0:
        if col in bs.columns:
            balance_text = _series_to_text_finfetch(bs, col, in_crores=True)
        else:
            balance_text = _series_to_text_finfetch(bs, bs.columns[0], in_crores=True)

    return {
        "period_label": period_label,
        "period_key": period_key,
        "income_statement_text": income_text,
        "balance_sheet_text": balance_text,
    }
