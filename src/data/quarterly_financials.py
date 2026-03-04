"""Quarterly financials from yfinance (last N quarters, Indian FY, Crores, QoQ)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.data.indian_quarters import get_last_n_quarters

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
    """Normalize column to YYYY-MM-DD for comparison."""
    if hasattr(c, "strftime"):
        return c.strftime("%Y-%m-%d")
    s = str(c)
    return s[:10] if len(s) >= 10 else s


def _value_for_period(df: Any, period_key: str, *row_keys: str) -> float | None:
    """Get value from DataFrame for row (first match of row_keys) and column matching period_key."""
    if df is None or not hasattr(df, "columns"):
        return None
    period_str = period_key if isinstance(period_key, str) else str(period_key)[:10]
    if len(period_str) > 10:
        period_str = period_str[:10]
    col = None
    for c in df.columns:
        if _norm_date(c) == period_str:
            col = c
            break
    if col is None:
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


def fetch_quarterly_financials(
    symbol: str,
    exchange: str,
    max_quarters: int = 8,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fetch quarterly financials via yfinance; return last max_quarters in chronological order.

    Each dict: period, period_label, revenue_cr, ebitda_cr, pat_cr, cfo_cr, debt_equity,
    and *_qoq_pct for each (None for first quarter).
    Values in Crores (divide by 1e7); debt_equity is ratio.
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

    income = None
    balance = None
    cashflow = None
    try:
        if hasattr(ticker, "quarterly_income_stmt"):
            income = getattr(ticker, "quarterly_income_stmt", None)
        if income is None and hasattr(ticker, "get_income_stmt"):
            income = ticker.get_income_stmt(freq="quarterly")
        if hasattr(ticker, "quarterly_balance_sheet"):
            balance = getattr(ticker, "quarterly_balance_sheet", None)
        if balance is None and hasattr(ticker, "get_balance_sheet"):
            balance = ticker.get_balance_sheet(freq="quarterly")
        if hasattr(ticker, "quarterly_cashflow"):
            cashflow = getattr(ticker, "quarterly_cashflow", None)
        if cashflow is None and hasattr(ticker, "get_cashflow"):
            cashflow = ticker.get_cashflow(freq="quarterly")
    except Exception as e:
        logger.warning("yfinance quarterly fetch failed for %s: %s", ticker_str, e)
        return []

    if income is None and balance is None and cashflow is None:
        return []

    quarter_specs = get_last_n_quarters(max_quarters, as_of)
    if not quarter_specs:
        return []

    # Build one row per requested quarter (all quarters); use None where data is missing
    results: list[dict[str, Any]] = []
    for period_key, period_label in quarter_specs:
        revenue = _value_for_period(income, period_key, "Total Revenue", "Revenue")
        ebitda = _value_for_period(income, period_key, "EBITDA", "Normalized EBITDA")
        pat = _value_for_period(
            income, period_key, "Net Income", "Net Income Common Stockholders"
        )
        cfo = _value_for_period(
            cashflow, period_key,
            "Operating Cash Flow",
            "Cash Flow From Continuing Operating Activities",
            "Cash From Operating Activities",
        )
        long_debt = _value_for_period(balance, period_key, "Long Term Debt") or 0.0
        short_debt = _value_for_period(balance, period_key, "Short Term Debt") or 0.0
        equity = _value_for_period(
            balance, period_key,
            "Total Stockholder Equity",
            "Total Equity Gross Minority Interest",
        )
        total_debt = long_debt + short_debt
        debt_equity = None
        if equity and equity != 0:
            raw = total_debt / equity
            debt_equity = _safe_float(raw)
            if debt_equity is not None:
                debt_equity = round(debt_equity, 2)

        def _to_cr(x: float | None) -> float | None:
            if x is None:
                return None
            f = _safe_float(x)
            return round(f / CRORE, 2) if f is not None else None

        revenue_cr = _to_cr(revenue)
        ebitda_cr = _to_cr(ebitda)
        pat_cr = _to_cr(pat)
        cfo_cr = _to_cr(cfo)

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

    # Fill QoQ %
    def _qoq_pct(cur: float | None, prev: float | None) -> float | None:
        if cur is None or prev is None or prev == 0:
            return None
        return round((cur - prev) / prev * 100, 2)

    for i in range(1, len(results)):
        r = results[i]
        p = results[i - 1]
        r["revenue_qoq_pct"] = _qoq_pct(r.get("revenue_cr"), p.get("revenue_cr"))
        r["ebitda_qoq_pct"] = _qoq_pct(r.get("ebitda_cr"), p.get("ebitda_cr"))
        r["pat_qoq_pct"] = _qoq_pct(r.get("pat_cr"), p.get("pat_cr"))
        r["cfo_qoq_pct"] = _qoq_pct(r.get("cfo_cr"), p.get("cfo_cr"))
        r["debt_equity_qoq_pct"] = _qoq_pct(r.get("debt_equity"), p.get("debt_equity"))

    return results


def _series_to_text(df: Any, period_key: str, in_crores: bool = True) -> str:
    """Format one column of a financial DataFrame as 'Line Item: value' lines."""
    if df is None or not hasattr(df, "columns") or not hasattr(df, "index"):
        return ""
    col = None
    for c in df.columns:
        if _norm_date(c) == (period_key[:10] if len(period_key) >= 10 else period_key):
            col = c
            break
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
                lines.append(f"{idx}: {round(f / CRORE, 2)} Cr")
            else:
                lines.append(f"{idx}: {f}")
        except (KeyError, TypeError):
            continue
    return "\n".join(lines)


def _first_column_key(df: Any) -> tuple[str, str] | None:
    """Return (period_key, period_label) for the first (latest) column of df, or None."""
    if df is None or not hasattr(df, "columns") or len(df.columns) == 0:
        return None
    from src.data.indian_quarters import calendar_date_to_indian_quarter
    c = df.columns[0]
    period_key = _norm_date(c)
    try:
        if hasattr(c, "to_pydatetime"):
            dt = c.to_pydatetime()
        elif hasattr(c, "year") and hasattr(c, "month"):
            dt = datetime(int(c.year), int(c.month), 15)
        else:
            parts = period_key.split("-")
            if len(parts) == 3:
                dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            else:
                dt = datetime.now()
        period_label = calendar_date_to_indian_quarter(dt)
    except Exception:
        period_label = period_key
    return (period_key, period_label)


def get_latest_quarter_statements(
    symbol: str,
    exchange: str,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Return latest quarter's income statement and balance sheet as text for prompt.

    Uses the most recent column from yfinance (latest available quarter).
    Keys: period_label, period_key, income_statement_text, balance_sheet_text.
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

    income = None
    balance = None
    try:
        if hasattr(ticker, "quarterly_income_stmt"):
            income = getattr(ticker, "quarterly_income_stmt", None)
        if income is None and hasattr(ticker, "get_income_stmt"):
            income = ticker.get_income_stmt(freq="quarterly")
        if hasattr(ticker, "quarterly_balance_sheet"):
            balance = getattr(ticker, "quarterly_balance_sheet", None)
        if balance is None and hasattr(ticker, "get_balance_sheet"):
            balance = ticker.get_balance_sheet(freq="quarterly")
    except Exception as e:
        logger.warning("get_latest_quarter_statements fetch failed: %s", e)
        return {}

    if income is None and balance is None:
        return {}

    period_key = None
    period_label = None
    for df in (income, balance):
        if df is not None:
            pair = _first_column_key(df)
            if pair:
                period_key, period_label = pair
                break
    if not period_key:
        return {}

    income_text = _series_to_text(income, period_key, in_crores=True) if income is not None else ""
    balance_text = _series_to_text(balance, period_key, in_crores=True) if balance is not None else ""
    return {
        "period_label": period_label,
        "period_key": period_key,
        "income_statement_text": income_text,
        "balance_sheet_text": balance_text,
    }
