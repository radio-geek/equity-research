"""Financial evaluation section: 30-second scorecard, 5-year trend table, trend insight.

Adheres to PR: Financial Strength Scorecard (6 signals), 5-Year Financial Trend, short interpretation.
"""

from __future__ import annotations

from typing import Any


def _n(val: Any) -> float | None:
    """Coerce to float or None."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None  # reject NaN
    except (TypeError, ValueError):
        return None


def _latest_yearly(metrics: list[dict]) -> dict | None:
    """Latest completed year (exclude TTM)."""
    for m in reversed(metrics or []):
        if (m.get("period_label") or "").strip().upper() != "TTM":
            return m
    return None


def _ttm_row(metrics: list[dict]) -> dict | None:
    """TTM row if present."""
    for m in metrics or []:
        if (m.get("period_label") or "").strip().upper() == "TTM":
            return m
    return None


def _prev_yearly(metrics: list[dict], after_label: str | None) -> dict | None:
    """Year row before the given period_label (for YoY or margin comparison)."""
    if not after_label or not metrics:
        return None
    found = False
    for m in reversed(metrics):
        lbl = (m.get("period_label") or "").strip().upper()
        if lbl == "TTM":
            continue
        if found:
            return m
        if lbl == (after_label or "").strip().upper():
            found = True
    return None


def build_financial_scorecard(
    yearly_metrics: list[dict[str, Any]],
    financial_ratios: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build 30-Second Financial Scorecard. Score 0-6, verdict, and 6 metric lines.

    Rules:
    1. Revenue Growth YoY > 10%
    2. Profit Growth YoY > Revenue Growth
    3. ROE > 15%
    4. Debt/Equity < 0.5
    5. Operating Cash Flow TTM positive
    6. Margins stable or improving YoY
    """
    total = 6
    metrics_out: list[dict[str, Any]] = []
    passed = 0

    latest = _latest_yearly(yearly_metrics)
    ttm = _ttm_row(yearly_metrics)
    prev = _prev_yearly(yearly_metrics, latest.get("period_label") if latest else None)

    # ROE and D/E: prefer TTM (from same scraped data), else latest year, else ratios list
    roe_val = None
    de_val = None
    if ttm:
        roe_val = _n(ttm.get("roe"))
        de_val = _n(ttm.get("debt_equity"))
    if roe_val is None or de_val is None:
        for r in financial_ratios or []:
            if (r.get("metric") or "").strip() == "ROE %" and roe_val is None:
                roe_val = _n(r.get("value"))
            if (r.get("metric") or "").strip() in ("Debt/Equity", "Debt/Equity ") and de_val is None:
                de_val = _n(r.get("value"))
    if roe_val is None and latest:
        roe_val = _n(latest.get("roe"))
    if de_val is None and latest:
        de_val = _n(latest.get("debt_equity"))

    rev_yoy = _n(latest.get("revenue_yoy_pct")) if latest else None
    pat_yoy = _n(latest.get("pat_yoy_pct")) if latest else None
    cfo_ttm = _n(ttm.get("cfo_cr")) if ttm else _n(latest.get("cfo_cr")) if latest else None

    # 1. Revenue Growth YoY > 10%
    rev_ok = rev_yoy is not None and rev_yoy > 10
    if rev_ok:
        passed += 1
    metrics_out.append({
        "name": "Revenue Growth",
        "display_value": f"{rev_yoy:.0f}% YoY" if rev_yoy is not None else "N/A",
        "passed": rev_ok,
        "signal": "Growth quality",
    })

    # 2. Profit Growth YoY > Revenue Growth
    profit_ok = (
        pat_yoy is not None
        and rev_yoy is not None
        and pat_yoy > rev_yoy
    )
    if profit_ok:
        passed += 1
    metrics_out.append({
        "name": "Profit Growth",
        "display_value": f"{pat_yoy:.0f}% YoY" if pat_yoy is not None else "N/A",
        "passed": profit_ok,
        "signal": "Operating leverage",
    })

    # 3. ROE > 15%
    roe_ok = roe_val is not None and roe_val > 15
    if roe_ok:
        passed += 1
    metrics_out.append({
        "name": "ROE",
        "display_value": f"{roe_val:.0f}%" if roe_val is not None else "N/A",
        "passed": roe_ok,
        "signal": "Capital efficiency",
    })

    # 4. Debt/Equity < 0.5
    de_ok = de_val is not None and de_val < 0.5
    if de_ok:
        passed += 1
    metrics_out.append({
        "name": "Debt / Equity",
        "display_value": f"{de_val:.2f}" if de_val is not None else "N/A",
        "passed": de_ok,
        "signal": "Balance sheet strength",
    })

    # 5. Operating Cash Flow TTM positive
    cfo_ok = cfo_ttm is not None and cfo_ttm > 0
    if cfo_ok:
        passed += 1
    metrics_out.append({
        "name": "Operating Cash Flow",
        "display_value": "Positive" if cfo_ok else ("Negative" if cfo_ttm is not None and cfo_ttm <= 0 else "N/A"),
        "passed": cfo_ok,
        "signal": "Cash quality",
    })

    # 6. Margins stable or improving YoY (compare latest vs prev net profit margin)
    margin_ok = False
    margin_display = "N/A"
    if latest and prev:
        rev_l = _n(latest.get("revenue_cr"))
        pat_l = _n(latest.get("pat_cr"))
        rev_p = _n(prev.get("revenue_cr"))
        pat_p = _n(prev.get("pat_cr"))
        if rev_l and rev_l != 0 and rev_p and rev_p != 0:
            npm_l = 100 * (pat_l or 0) / rev_l
            npm_p = 100 * (pat_p or 0) / rev_p
            margin_ok = npm_l >= npm_p - 0.5  # allow tiny rounding
            margin_display = "Stable" if abs(npm_l - npm_p) < 0.5 else ("Improving" if npm_l > npm_p else "Declining")
        elif rev_l and rev_l != 0:
            margin_display = "Stable"
    if margin_ok:
        passed += 1
    metrics_out.append({
        "name": "Margins",
        "display_value": margin_display,
        "passed": margin_ok,
        "signal": "Profit sustainability",
    })

    if passed >= 5:
        verdict = "The company appears financially strong with healthy growth, strong returns, and controlled leverage."
        verdict_tier = "strong"
    elif passed >= 3:
        verdict = "The company shows average financial strength with a mixed profile on growth, returns, and leverage."
        verdict_tier = "average"
    else:
        verdict = "The company shows weak financials; growth, returns, or balance sheet metrics need improvement."
        verdict_tier = "weak"

    # Letter grade for report-card feel: 6→A, 5→A-, 4→B, 3→C, 2→D, 0-1→F
    if passed >= 6:
        letter_grade = "A"
    elif passed == 5:
        letter_grade = "A-"
    elif passed == 4:
        letter_grade = "B"
    elif passed == 3:
        letter_grade = "C"
    elif passed == 2:
        letter_grade = "D"
    else:
        letter_grade = "F"

    return {
        "score": passed,
        "total": total,
        "verdict": verdict,
        "verdict_tier": verdict_tier,
        "letter_grade": letter_grade,
        "metrics": metrics_out,
    }


def build_five_year_trend_table(yearly_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Build 5-Year Financial Trend table. Latest 5 completed years + TTM column (scraped from Screener).

    Rows: Revenue, Revenue Growth, PAT, PAT Growth, EPS, EBITDA Margin, Net Profit Margin,
    Debt, Debt/Equity, Gross NPA %, Net NPA % (if available, e.g. banks), Operating Cash Flow (TTM = —).
    Missing values as N/A. Monetary in ₹ Cr.
    """
    all_metrics = yearly_metrics or []
    years_only = [m for m in all_metrics if (m.get("period_label") or "").strip().upper() != "TTM"]
    years_only = years_only[-5:]
    ttm = _ttm_row(all_metrics)
    if not years_only:
        return {"headers": [], "rows": []}

    headers = [m.get("period_label", "") for m in years_only]
    if ttm:
        headers.append("TTM")
    n_cols = len(headers)
    rows: list[dict[str, Any]] = []

    def cell(val: Any, fmt: str = "num") -> str:
        if val is None:
            return "N/A"
        try:
            f = float(val)
            if f != f:
                return "N/A"
            if fmt == "pct":
                return f"{f:.0f}%"
            if fmt == "int":
                return f"{int(round(f))}"
            return f"{f:.2f}" if abs(f) < 1e6 else f"{int(round(f))}"
        except (TypeError, ValueError):
            return "N/A"

    last_rev = _n(years_only[-1].get("revenue_cr")) if years_only else None
    last_pat = _n(years_only[-1].get("pat_cr")) if years_only else None
    ttm_rev = _n(ttm.get("revenue_cr")) if ttm else None
    ttm_pat = _n(ttm.get("pat_cr")) if ttm else None
    rev_growth_ttm = (cell((ttm_rev - last_rev) / last_rev * 100, "pct") if last_rev and ttm_rev is not None else "—")
    pat_growth_ttm = (cell((ttm_pat - last_pat) / last_pat * 100, "pct") if last_pat and ttm_pat is not None else "—")

    # Revenue (₹ Cr)
    cells = [cell(m.get("revenue_cr")) for m in years_only]
    if ttm:
        cells.append(cell(ttm.get("revenue_cr")))
    rows.append({"metric": "Revenue", "unit": "₹ Cr", "cells": cells})

    # Revenue Growth %
    rev_growth = []
    for i, m in enumerate(years_only):
        rev_growth.append("—" if i == 0 else cell(m.get("revenue_yoy_pct"), "pct"))
    if ttm:
        rev_growth.append(rev_growth_ttm)
    rows.append({"metric": "Revenue Growth", "unit": "%", "cells": rev_growth})

    # PAT (₹ Cr)
    cells = [cell(m.get("pat_cr")) for m in years_only]
    if ttm:
        cells.append(cell(ttm.get("pat_cr")))
    rows.append({"metric": "PAT", "unit": "₹ Cr", "cells": cells})

    # PAT Growth %
    pat_growth = []
    for i, m in enumerate(years_only):
        pat_growth.append("—" if i == 0 else cell(m.get("pat_yoy_pct"), "pct"))
    if ttm:
        pat_growth.append(pat_growth_ttm)
    rows.append({"metric": "PAT Growth", "unit": "%", "cells": pat_growth})

    # EPS (₹)
    cells = [cell(m.get("eps")) for m in years_only]
    if ttm:
        cells.append(cell(ttm.get("eps")))
    rows.append({"metric": "EPS", "unit": "₹", "cells": cells})

    # EBITDA Margin %
    ebitda_margin = []
    for m in years_only:
        rev, ebitda = _n(m.get("revenue_cr")), _n(m.get("ebitda_cr"))
        ebitda_margin.append(cell(100 * ebitda / rev, "pct") if rev and rev != 0 and ebitda is not None else "N/A")
    if ttm:
        rev_t, op_t = _n(ttm.get("revenue_cr")), _n(ttm.get("ebitda_cr"))
        ebitda_margin.append(cell(100 * op_t / rev_t, "pct") if rev_t and rev_t != 0 and op_t is not None else "N/A")
    rows.append({"metric": "EBITDA Margin", "unit": "%", "cells": ebitda_margin})

    # Net Profit Margin %
    npm = []
    for m in years_only:
        rev, pat = _n(m.get("revenue_cr")), _n(m.get("pat_cr"))
        npm.append(cell(100 * pat / rev, "pct") if rev and rev != 0 and pat is not None else "N/A")
    if ttm:
        rev_t, pat_t = _n(ttm.get("revenue_cr")), _n(ttm.get("pat_cr"))
        npm.append(cell(100 * pat_t / rev_t, "pct") if rev_t and rev_t != 0 and pat_t is not None else "N/A")
    rows.append({"metric": "Net Profit Margin", "unit": "%", "cells": npm})

    # Debt (₹ Cr)
    cells = [cell(m.get("debt_cr")) for m in years_only]
    if ttm:
        cells.append(cell(ttm.get("debt_cr")))
    rows.append({"metric": "Debt", "unit": "₹ Cr", "cells": cells})

    # Debt / Equity
    cells = [cell(m.get("debt_equity")) for m in years_only]
    if ttm:
        cells.append(cell(ttm.get("debt_equity")))
    rows.append({"metric": "Debt / Equity", "unit": "Ratio", "cells": cells})

    # Gross NPA % (if available, e.g. banks/NBFCs)
    cells = [cell(m.get("gross_npa_pct"), "pct") for m in years_only]
    if ttm:
        cells.append(cell(ttm.get("gross_npa_pct"), "pct"))
    rows.append({"metric": "Gross NPA", "unit": "%", "cells": cells})

    # Net NPA % (if available, e.g. banks/NBFCs)
    cells = [cell(m.get("net_npa_pct"), "pct") for m in years_only]
    if ttm:
        cells.append(cell(ttm.get("net_npa_pct"), "pct"))
    rows.append({"metric": "Net NPA", "unit": "%", "cells": cells})

    # Operating Cash Flow (₹ Cr) — TTM column = — (Screener has no CF TTM)
    cells = [cell(m.get("cfo_cr")) for m in years_only]
    if ttm:
        cells.append("—")
    rows.append({"metric": "Operating Cash Flow", "unit": "₹ Cr", "cells": cells})

    # Drop rows where every cell is N/A (e.g. Gross NPA / Net NPA when not reported)
    def _row_has_data(row: dict[str, Any]) -> bool:
        cells_val = row.get("cells") or []
        return any(c != "N/A" for c in cells_val)

    rows = [r for r in rows if _row_has_data(r)]
    return {"headers": headers, "rows": rows}


def build_key_metrics(yearly_metrics: list[dict[str, Any]]) -> dict[str, str]:
    """Build key TTM metrics for report header from yearly_metrics (TTM row). All from same scraped data."""
    ttm = _ttm_row(yearly_metrics or [])
    if not ttm:
        return {}

    def _fmt_num(val: Any) -> str:
        if val is None:
            return "—"
        try:
            f = float(val)
            if f != f:
                return "—"
            return f"{int(round(f))}" if abs(f) >= 1 else f"{f:.2f}"
        except (TypeError, ValueError):
            return "—"

    def _fmt_pct(val: Any) -> str:
        if val is None:
            return "—"
        try:
            f = float(val)
            if f != f:
                return "—"
            return f"{f:.0f}%"
        except (TypeError, ValueError):
            return "—"

    # PAT margin % and EBITDA margin %: use TTM table values (from Screener OPM % and computed PAT margin)
    pat_margin_pct = _n(ttm.get("pat_margin_pct"))
    if pat_margin_pct is None:
        rev = _n(ttm.get("revenue_cr"))
        pat = _n(ttm.get("pat_cr"))
        pat_margin_pct = (100 * pat / rev) if rev and rev != 0 and pat is not None else None
    ebitda_margin_pct = _n(ttm.get("ebitda_margin_pct"))
    if ebitda_margin_pct is None:
        rev = _n(ttm.get("revenue_cr"))
        ebitda = _n(ttm.get("ebitda_cr"))
        ebitda_margin_pct = (100 * ebitda / rev) if rev and rev != 0 and ebitda is not None else None
    return {
        "revenue_cr": _fmt_num(ttm.get("revenue_cr")),
        "pat_cr": _fmt_num(ttm.get("pat_cr")),
        "roe": _fmt_pct(ttm.get("roe")),
        "roce": _fmt_pct(ttm.get("roce")),
        "debt_equity": _fmt_num(ttm.get("debt_equity")),
        "eps": _fmt_num(ttm.get("eps")),
        "debt_cr": _fmt_num(ttm.get("debt_cr")),
        "pat_margin": _fmt_pct(pat_margin_pct),
        "ebitda_margin": _fmt_pct(ebitda_margin_pct),
    }


def build_trend_insight_summary(
    five_year_table: dict[str, Any],
    company_name: str,
) -> str:
    """Return a short 2-3 line interpretation of the 5-year trend. Placeholder; override with LLM in node."""
    if not five_year_table.get("rows") or not five_year_table.get("headers"):
        return "Insufficient data for trend summary."
    # Simple template summary; caller can replace with LLM-generated text
    return (
        "Revenue and profits over the past five years, along with margin and leverage trends, "
        "are summarised in the table above. Refer to the Financial Strength Scorecard for a quick health check."
    )
