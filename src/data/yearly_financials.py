"""Yearly financials + TTM from Screener.in (scraped). Crores, YoY %. Replaces finfetch for this flow."""

from __future__ import annotations

import logging
from typing import Any

from src.data.finfetch_helpers import _safe_float
from src.data.screener_scraper import fetch_consolidated

logger = logging.getLogger(__name__)


def _screener_col_to_fy_label(col: str) -> str:
    """Convert Screener column 'Mar 2024' to 'FY24'; 'TTM' stays 'TTM'."""
    s = str(col).strip()
    if s.upper() == "TTM":
        return "TTM"
    parts = s.split()
    if len(parts) != 2:
        return s[:10]
    try:
        year = int(parts[1])
        return f"FY{year % 100}"
    except (ValueError, IndexError):
        return s[:10]


def _value_from_screener_df(df: Any, col: Any, *row_keys: str) -> float | None:
    """Get value from Screener DataFrame for column col (first matching row in row_keys)."""
    if df is None or not hasattr(df, "loc"):
        return None
    cols = getattr(df, "columns", None)
    if cols is None or len(cols) == 0:
        return None
    try:
        if col not in cols:
            col = list(cols)[-1]
    except (TypeError, ValueError):
        col = list(cols)[-1]
    if col is None:
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


def fetch_yearly_financials(
    symbol: str,
    exchange: str,
    max_years: int = 8,
) -> list[dict[str, Any]]:
    """Fetch yearly financials from Screener.in (scraped). Chronological order (oldest first), then TTM last.

    URL is built dynamically: https://www.screener.in/company/{symbol}/consolidated/

    Each dict: period_label (FY21, ..., TTM), revenue_cr, ebitda_cr, pat_cr, cfo_cr, debt_cr, debt_equity,
    roe, roce, eps, and *_yoy_pct (None for first year and for TTM).
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return []

    try:
        data = fetch_consolidated(symbol)
    except Exception as e:
        logger.warning("Screener fetch_consolidated failed for %s: %s", symbol, e)
        return []

    pl = data.get("profit_loss")
    bs = data.get("balance_sheet")
    cf = data.get("cash_flow")
    ratios = data.get("ratios")

    if pl is None or not hasattr(pl, "columns") or len(pl.columns) == 0:
        logger.debug("Screener: no P&L for %s", symbol)
        return []

    non_ttm = [c for c in pl.columns if str(c).strip().upper() != "TTM"]
    year_cols = non_ttm[-max_years:] if len(non_ttm) >= max_years else non_ttm
    if not year_cols:
        return []

    bs_cols = list(bs.columns) if bs is not None and hasattr(bs, "columns") else []
    cf_cols = list(cf.columns) if cf is not None and hasattr(cf, "columns") else []
    ratio_cols = list(ratios.columns) if ratios is not None and hasattr(ratios, "columns") else []

    def _col_at(i: int, cols: list) -> Any:
        if not cols:
            return year_cols[i] if i < len(year_cols) else None
        return cols[min(i, len(cols) - 1)]

    results: list[dict[str, Any]] = []
    n = len(year_cols)
    for i in range(n):
        col = year_cols[i]
        col_bs = _col_at(i, bs_cols)
        col_cf = _col_at(i, cf_cols)
        col_ratio = _col_at(i, ratio_cols)

        # Revenue: standard (Sales) and bank (Revenue +)
        revenue = _value_from_screener_df(pl, col, "Sales", "Sales +", "Revenue +", "Revenue")
        revenue_cr = round(revenue, 2) if revenue is not None else None
        # Operating profit: standard; bank uses Profit before tax or Financing Profit as proxy
        op = _value_from_screener_df(pl, col, "Operating Profit", "Profit before tax", "Financing Profit")
        ebitda_cr = round(op, 2) if op is not None else None
        pat = _value_from_screener_df(pl, col, "Net Profit", "Net Profit +")
        pat_cr = round(pat, 2) if pat is not None else None
        eps_val = _value_from_screener_df(pl, col, "EPS in Rs", "EPS")

        cfo_cr = None
        if cf is not None and col_cf and col_cf in cf_cols:
            cfo = _value_from_screener_df(cf, col_cf, "Cash from Operating Activity", "Cash from Operating Activity +")
            cfo_cr = round(cfo, 2) if cfo is not None else None

        debt = None
        equity = None
        if bs is not None and col_bs:
            # Debt: standard (Borrowings); bank often uses "Borrowing" (singular)
            debt = _value_from_screener_df(bs, col_bs, "Borrowings", "Borrowings +", "Borrowing")
            reserves = _value_from_screener_df(bs, col_bs, "Reserves")
            eq_cap = _value_from_screener_df(bs, col_bs, "Equity Capital")
            equity = (reserves or 0) + (eq_cap or 0) or None
        debt_cr = round(debt, 2) if debt is not None else None
        total_borrowings = debt or 0.0
        debt_equity = round(total_borrowings / equity, 2) if equity and equity != 0 and debt is not None else None

        roe = round(100 * pat / equity, 2) if pat is not None and equity and equity != 0 else None
        roce = None
        if ratios is not None and col_ratio and col_ratio in ratio_cols:
            roce = _value_from_screener_df(ratios, col_ratio, "ROCE %", "ROCE%")
        if roce is None and op is not None and equity is not None and (equity + total_borrowings):
            roce = round(100 * op / (equity + total_borrowings), 2)

        results.append({
            "period_label": _screener_col_to_fy_label(str(col)),
            "revenue_cr": revenue_cr,
            "ebitda_cr": ebitda_cr,
            "pat_cr": pat_cr,
            "cfo_cr": cfo_cr,
            "debt_cr": debt_cr,
            "debt_equity": debt_equity,
            "roe": roe,
            "roce": roce,
            "eps": round(eps_val, 2) if eps_val is not None else None,
            "revenue_yoy_pct": None,
            "ebitda_yoy_pct": None,
            "pat_yoy_pct": None,
            "cfo_yoy_pct": None,
            "debt_equity_yoy_pct": None,
            "roe_yoy_pct": None,
            "roce_yoy_pct": None,
        })

    def _yoy(cur: float | None, prev: float | None) -> float | None:
        if cur is None or prev is None or prev == 0:
            return None
        return round((cur - prev) / prev * 100, 2)

    for i in range(1, len(results)):
        r, p = results[i], results[i - 1]
        r["revenue_yoy_pct"] = _yoy(r.get("revenue_cr"), p.get("revenue_cr"))
        r["ebitda_yoy_pct"] = _yoy(r.get("ebitda_cr"), p.get("ebitda_cr"))
        r["pat_yoy_pct"] = _yoy(r.get("pat_cr"), p.get("pat_cr"))
        r["cfo_yoy_pct"] = _yoy(r.get("cfo_cr"), p.get("cfo_cr"))
        r["debt_equity_yoy_pct"] = _yoy(r.get("debt_equity"), p.get("debt_equity"))
        r["roe_yoy_pct"] = _yoy(r.get("roe"), p.get("roe"))
        r["roce_yoy_pct"] = _yoy(r.get("roce"), p.get("roce"))

    # TTM row from P&L TTM column and latest BS column
    if "TTM" not in pl.columns:
        return results
    ttm_col = "TTM"
    latest_bs_col = bs_cols[-1] if bs_cols else None

    ttm_revenue = _value_from_screener_df(pl, ttm_col, "Sales", "Sales +", "Revenue +", "Revenue")
    ttm_op = _value_from_screener_df(pl, ttm_col, "Operating Profit", "Profit before tax", "Financing Profit")
    ttm_pat = _value_from_screener_df(pl, ttm_col, "Net Profit", "Net Profit +")
    ttm_eps = _value_from_screener_df(pl, ttm_col, "EPS in Rs", "EPS")
    ttm_equity = None
    ttm_debt = None
    if bs is not None and latest_bs_col:
        r = _value_from_screener_df(bs, latest_bs_col, "Reserves")
        e = _value_from_screener_df(bs, latest_bs_col, "Equity Capital")
        ttm_equity = (r or 0) + (e or 0) or None
        ttm_debt = _value_from_screener_df(bs, latest_bs_col, "Borrowings", "Borrowings +", "Borrowing")
    ttm_debt_equity = round(ttm_debt / ttm_equity, 2) if ttm_equity and ttm_equity != 0 and ttm_debt is not None else None
    ttm_roe = round(100 * ttm_pat / ttm_equity, 2) if ttm_pat is not None and ttm_equity and ttm_equity != 0 else None
    ttm_roce = None
    if ttm_equity is not None and ttm_debt is not None and (ttm_equity + ttm_debt):
        ttm_roce = round(100 * ttm_op / (ttm_equity + ttm_debt), 2) if ttm_op is not None else None

    # Prefer ROE/ROCE from Screener ratios table (latest column or TTM) when available
    if ratios is not None and hasattr(ratios, "columns") and len(ratios.columns) > 0:
        ratio_col = "TTM" if "TTM" in ratios.columns else list(ratios.columns)[-1]
        roe_from_ratio = _value_from_screener_df(ratios, ratio_col, "ROE %", "ROE")
        roce_from_ratio = _value_from_screener_df(ratios, ratio_col, "ROCE %", "ROCE")
        if roe_from_ratio is not None:
            ttm_roe = round(roe_from_ratio, 2)
        if roce_from_ratio is not None:
            ttm_roce = round(roce_from_ratio, 2)

    results.append({
        "period_label": "TTM",
        "revenue_cr": round(ttm_revenue, 2) if ttm_revenue is not None else None,
        "ebitda_cr": round(ttm_op, 2) if ttm_op is not None else None,
        "pat_cr": round(ttm_pat, 2) if ttm_pat is not None else None,
        "cfo_cr": None,  # Screener CF has no TTM column
        "debt_cr": round(ttm_debt, 2) if ttm_debt is not None else None,
        "debt_equity": ttm_debt_equity,
        "roe": ttm_roe,
        "roce": ttm_roce,
        "eps": round(ttm_eps, 2) if ttm_eps is not None else None,
        "revenue_yoy_pct": None,
        "ebitda_yoy_pct": None,
        "pat_yoy_pct": None,
        "cfo_yoy_pct": None,
        "debt_equity_yoy_pct": None,
        "roe_yoy_pct": None,
        "roce_yoy_pct": None,
    })
    return results


def _dataframe_column_to_text(df: Any, col: Any, in_crores: bool = True) -> str:
    """Format one column of a DataFrame as 'Line Item: value' lines (Screener or finfetch-style)."""
    if df is None or not hasattr(df, "index"):
        return ""
    cols = getattr(df, "columns", None)
    if cols is None or len(cols) == 0:
        return ""
    if col not in cols:
        col = list(cols)[-1]
    if col is None:
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


def get_ttm_statements(symbol: str, exchange: str) -> dict[str, Any]:
    """Return TTM income statement and latest balance sheet as text for LLM prompt.

    Uses Screener.in consolidated page (URL built from symbol). P&L TTM column + BS latest column.
    Keys: period_label ('TTM'), income_statement_text, balance_sheet_text.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {}

    try:
        data = fetch_consolidated(symbol)
    except Exception as e:
        logger.warning("get_ttm_statements Screener failed for %s: %s", symbol, e)
        return {}

    pl = data.get("profit_loss")
    bs = data.get("balance_sheet")

    if pl is None or not hasattr(pl, "columns") or len(pl.columns) == 0:
        return {}

    income_text = ""
    if "TTM" in pl.columns:
        income_text = _dataframe_column_to_text(pl, "TTM", in_crores=True)

    balance_text = ""
    if bs is not None and hasattr(bs, "columns") and len(bs.columns) > 0:
        balance_text = _dataframe_column_to_text(bs, bs.columns[-1], in_crores=True)

    return {
        "period_label": "TTM",
        "income_statement_text": income_text,
        "balance_sheet_text": balance_text,
    }
