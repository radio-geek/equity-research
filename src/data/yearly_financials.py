"""Yearly financials + TTM from yfinance (Crores, YoY %). TTM statements for LLM highlights."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CRORE = 1e7


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        if hasattr(val, "size") and getattr(val, "size", 1) and hasattr(val, "iloc"):
            val = val.iloc[0] if val.size else None
        if val is None:
            return None
        f = float(val)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError, IndexError):
        return None


def _norm_date(c: Any) -> str:
    if hasattr(c, "strftime"):
        return c.strftime("%Y-%m-%d")
    s = str(c)
    return s[:10] if len(s) >= 10 else s


def _value_for_column(df: Any, col, *row_keys: str) -> float | None:
    """Get value from DataFrame for row (first match of row_keys) and column col."""
    if df is None or not hasattr(df, "loc"):
        return None
    for rk in row_keys:
        try:
            v = df.loc[rk, col]
            f = _safe_float(v)
            if f is not None:
                return f
        except (KeyError, TypeError):
            continue
    return None


def _column_to_fy_label(col) -> str:
    """Convert year-end column (e.g. 2025-03-31) to FY label (e.g. FY25)."""
    try:
        if hasattr(col, "year"):
            y = int(col.year)
            return f"FY{y % 100}"
        s = _norm_date(col)
        if len(s) >= 4:
            return f"FY{int(s[:4]) % 100}"
    except Exception:
        pass
    return str(col)[:10]


def _dataframe_to_text(df: Any, col, in_crores: bool = True) -> str:
    """Format one column of a financial DataFrame as 'Line Item: value' lines."""
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
                lines.append(f"{idx}: {round(f / CRORE, 2)} Cr")
            else:
                lines.append(f"{idx}: {f}")
        except (KeyError, TypeError):
            continue
    return "\n".join(lines)


def fetch_yearly_financials(
    symbol: str,
    exchange: str,
    max_years: int = 8,
) -> list[dict[str, Any]]:
    """Fetch yearly financials + TTM via yfinance; return chronological order (oldest first), then TTM last.

    Each dict: period_label (FY24, FY25, ..., TTM), revenue_cr, ebitda_cr, pat_cr, cfo_cr, debt_equity,
    and *_yoy_pct (None for first year and for TTM).
    """
    try:
        import yfinance as yf
    except ImportError as e:
        logger.warning("yfinance not available: %s", e)
        return []

    ticker_str = f"{symbol.upper()}.NS" if (exchange or "").upper() == "NSE" else symbol.upper()
    try:
        ticker = yf.Ticker(ticker_str)
    except Exception as e:
        logger.warning("yfinance Ticker failed for %s: %s", ticker_str, e)
        return []

    try:
        income_y = ticker.get_income_stmt(freq="yearly")
        balance_y = ticker.get_balance_sheet(freq="yearly")
        cashflow_y = ticker.get_cashflow(freq="yearly")
    except Exception as e:
        logger.warning("yfinance yearly fetch failed for %s: %s", ticker_str, e)
        return []

    if income_y is None or not hasattr(income_y, "columns") or len(income_y.columns) == 0:
        return []

    # Yearly columns (usually newest first in yfinance)
    y_cols = list(income_y.columns)[:max_years]
    y_cols.reverse()
    results: list[dict[str, Any]] = []

    rev_keys = ("Total Revenue", "TotalRevenue", "Revenue", "Operating Revenue", "OperatingRevenue")
    ebitda_keys = ("EBITDA", "Normalized EBITDA", "NormalizedEBITDA")
    ebit_keys = ("EBIT", "Operating Income", "OperatingIncome", "Earnings Before Interest and Taxes")
    pat_keys = ("Net Income", "Net Income Common Stockholders", "NetIncome", "NetIncomeCommonStockholders")
    cfo_keys = ("Operating Cash Flow", "OperatingCashFlow", "Cash Flow From Continuing Operating Activities", "CashFromOperatingActivities")
    long_debt_keys = ("Long Term Debt", "LongTermDebt")
    short_debt_keys = ("Short Term Debt", "ShortTermDebt")
    equity_keys = ("Total Stockholder Equity", "TotalStockholderEquity", "Total Equity Gross Minority Interest", "TotalEquityGrossMinorityInterest")

    for col in y_cols:
        revenue = _value_for_column(income_y, col, *rev_keys)
        ebitda = _value_for_column(income_y, col, *ebitda_keys)
        ebit = _value_for_column(income_y, col, *ebit_keys)
        pat = _value_for_column(income_y, col, *pat_keys)
        cfo = _value_for_column(cashflow_y, col, *cfo_keys) if cashflow_y is not None else None
        long_debt = _value_for_column(balance_y, col, *long_debt_keys) or 0.0
        short_debt = _value_for_column(balance_y, col, *short_debt_keys) or 0.0
        equity = _value_for_column(balance_y, col, *equity_keys)
        total_debt = long_debt + short_debt
        debt_equity = None
        if equity and equity != 0:
            raw = total_debt / equity
            debt_equity = _safe_float(raw)
            if debt_equity is not None:
                debt_equity = round(debt_equity, 2)

        roe = None
        if pat is not None and equity is not None and equity != 0:
            roe = _safe_float(100 * pat / equity)
            if roe is not None:
                roe = round(roe, 2)
        roce = None
        capital = (equity or 0) + total_debt
        if ebit is not None and capital and capital != 0:
            roce = _safe_float(100 * ebit / capital)
            if roce is not None:
                roce = round(roce, 2)

        def _to_cr(x: float | None) -> float | None:
            if x is None:
                return None
            f = _safe_float(x)
            return round(f / CRORE, 2) if f is not None else None

        results.append({
            "period_label": _column_to_fy_label(col),
            "revenue_cr": _to_cr(revenue),
            "ebitda_cr": _to_cr(ebitda),
            "pat_cr": _to_cr(pat),
            "cfo_cr": _to_cr(cfo),
            "debt_equity": debt_equity,
            "roe": roe,
            "roce": roce,
            "revenue_yoy_pct": None,
            "ebitda_yoy_pct": None,
            "pat_yoy_pct": None,
            "cfo_yoy_pct": None,
            "debt_equity_yoy_pct": None,
            "roe_yoy_pct": None,
            "roce_yoy_pct": None,
        })

    # YoY %
    def _yoy(cur: float | None, prev: float | None) -> float | None:
        if cur is None or prev is None or prev == 0:
            return None
        return round((cur - prev) / prev * 100, 2)

    for i in range(1, len(results)):
        r = results[i]
        p = results[i - 1]
        r["revenue_yoy_pct"] = _yoy(r.get("revenue_cr"), p.get("revenue_cr"))
        r["ebitda_yoy_pct"] = _yoy(r.get("ebitda_cr"), p.get("ebitda_cr"))
        r["pat_yoy_pct"] = _yoy(r.get("pat_cr"), p.get("pat_cr"))
        r["cfo_yoy_pct"] = _yoy(r.get("cfo_cr"), p.get("cfo_cr"))
        r["debt_equity_yoy_pct"] = _yoy(r.get("debt_equity"), p.get("debt_equity"))
        r["roe_yoy_pct"] = _yoy(r.get("roe"), p.get("roe"))
        r["roce_yoy_pct"] = _yoy(r.get("roce"), p.get("roce"))

    # Append TTM row
    try:
        income_t = ticker.get_income_stmt(freq="trailing")
        cashflow_t = ticker.get_cashflow(freq="trailing")
        balance_t = balance_y
        ttm_col = income_t.columns[0] if income_t is not None and len(income_t.columns) > 0 else None
        bal_col = balance_y.columns[0] if balance_y is not None and len(balance_y.columns) > 0 else None
    except Exception as e:
        logger.warning("yfinance TTM fetch failed for %s: %s", ticker_str, e)
        return results

    if ttm_col is not None and income_t is not None:
        revenue = _value_for_column(income_t, ttm_col, *rev_keys)
        ebitda = _value_for_column(income_t, ttm_col, *ebitda_keys)
        ebit = _value_for_column(income_t, ttm_col, *ebit_keys)
        pat = _value_for_column(income_t, ttm_col, *pat_keys)
        cfo = _value_for_column(cashflow_t, ttm_col, *cfo_keys) if cashflow_t is not None else None
        long_debt = short_debt = equity = 0.0
        if balance_t is not None and bal_col is not None:
            long_debt = _value_for_column(balance_t, bal_col, *long_debt_keys) or 0.0
            short_debt = _value_for_column(balance_t, bal_col, *short_debt_keys) or 0.0
            equity = _value_for_column(balance_t, bal_col, *equity_keys) or 0.0
        total_debt = long_debt + short_debt
        debt_equity = None
        if equity and equity != 0:
            raw = total_debt / equity
            debt_equity = _safe_float(raw)
            if debt_equity is not None:
                debt_equity = round(debt_equity, 2)

        roe = None
        if pat is not None and equity is not None and equity != 0:
            roe = _safe_float(100 * pat / equity)
            if roe is not None:
                roe = round(roe, 2)
        roce = None
        capital = (equity or 0) + total_debt
        if ebit is not None and capital and capital != 0:
            roce = _safe_float(100 * ebit / capital)
            if roce is not None:
                roce = round(roce, 2)

        def _to_cr(x: float | None) -> float | None:
            if x is None:
                return None
            f = _safe_float(x)
            return round(f / CRORE, 2) if f is not None else None

        results.append({
            "period_label": "TTM",
            "revenue_cr": _to_cr(revenue),
            "ebitda_cr": _to_cr(ebitda),
            "pat_cr": _to_cr(pat),
            "cfo_cr": _to_cr(cfo),
            "debt_equity": debt_equity,
            "roe": roe,
            "roce": roce,
            "revenue_yoy_pct": None,
            "ebitda_yoy_pct": None,
            "pat_yoy_pct": None,
            "cfo_yoy_pct": None,
            "debt_equity_yoy_pct": None,
            "roe_yoy_pct": None,
            "roce_yoy_pct": None,
        })

    return results


def get_ttm_statements(symbol: str, exchange: str) -> dict[str, Any]:
    """Return TTM income statement and latest balance sheet as text for LLM prompt.

    Keys: period_label ('TTM'), income_statement_text, balance_sheet_text.
    Balance sheet is latest available (yearly first column) since yfinance has no trailing balance sheet.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {}

    ticker_str = f"{symbol.upper()}.NS" if (exchange or "").upper() == "NSE" else symbol.upper()
    try:
        ticker = yf.Ticker(ticker_str)
    except Exception:
        return {}

    try:
        income_t = ticker.get_income_stmt(freq="trailing")
        cashflow_t = ticker.get_cashflow(freq="trailing")
        balance_y = ticker.get_balance_sheet(freq="yearly")
    except Exception as e:
        logger.warning("get_ttm_statements fetch failed: %s", e)
        return {}

    if income_t is None or (not hasattr(income_t, "columns")) or len(income_t.columns) == 0:
        return {}

    ttm_col = income_t.columns[0]
    income_text = _dataframe_to_text(income_t, ttm_col, in_crores=True)
    balance_text = ""
    if balance_y is not None and len(balance_y.columns) > 0:
        balance_text = _dataframe_to_text(balance_y, balance_y.columns[0], in_crores=True)
    return {
        "period_label": "TTM",
        "income_statement_text": income_text,
        "balance_sheet_text": balance_text,
    }
