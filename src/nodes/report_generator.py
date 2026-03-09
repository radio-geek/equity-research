"""Report generator node: state -> schema-aligned JSON payload (no PDF/HTML)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.state import ResearchState

logger = logging.getLogger(__name__)


def _build_report_payload(state: ResearchState) -> dict[str, Any]:
    """Build the single report JSON dict matching report-output-schema.md."""
    symbol = (state.get("symbol") or "unknown").strip().upper()
    exchange = state.get("exchange") or "NSE"
    company_name = state.get("company_name") or symbol
    sector = state.get("sector") or ""
    industry = state.get("industry") or sector

    screener_quote = state.get("screener_quote") or {}
    payload: dict[str, Any] = {
        "meta": {
            "symbol": symbol,
            "exchange": exchange,
            "company_name": company_name,
            "sector": sector,
            "industry": industry,
        },
        "company": {
            "meta": state.get("meta") or {},
            "quote": state.get("quote") or {},
            "shareholding": state.get("shareholding") or [],
            "screener_quote": screener_quote,
        },
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if state.get("executive_summary"):
        payload["executive_summary"] = state["executive_summary"]
    if state.get("company_overview"):
        payload["company_overview"] = state["company_overview"]
    if state.get("management_research"):
        payload["management_research"] = state["management_research"]
    if state.get("financial_risk"):
        payload["financial_risk"] = state["financial_risk"]
    if state.get("auditor_flags") is not None:
        payload["auditor_flags"] = state["auditor_flags"]

    concall = state.get("concall_structured")
    payload["concall"] = concall if isinstance(concall, dict) else None

    sectoral_analysis = state.get("sectoral_analysis") or ""
    sectoral_headwinds = state.get("sectoral_headwinds")
    sectoral_tailwinds = state.get("sectoral_tailwinds")
    payload["sectoral"] = {
        "analysis": sectoral_analysis,
        "headwinds": sectoral_headwinds if isinstance(sectoral_headwinds, list) else [],
        "tailwinds": sectoral_tailwinds if isinstance(sectoral_tailwinds, list) else [],
    }

    financial_ratios = state.get("financial_ratios")
    yearly_metrics = state.get("yearly_metrics")
    qoq_highlights = state.get("qoq_highlights") or {"good": [], "bad": []}
    payload["financials"] = {
        "ratios": financial_ratios if isinstance(financial_ratios, list) else [],
        "yearly_metrics": yearly_metrics if isinstance(yearly_metrics, list) else [],
        "highlights": {
            "good": qoq_highlights.get("good", []) if isinstance(qoq_highlights, dict) else [],
            "bad": qoq_highlights.get("bad", []) if isinstance(qoq_highlights, dict) else [],
        },
        "financial_scorecard": state.get("financial_scorecard"),
        "five_year_trend": state.get("five_year_trend") or {"headers": [], "rows": []},
        "trend_insight_summary": state.get("trend_insight_summary") or "",
    }

    return payload


def report_generator(state: ResearchState) -> dict[str, Any]:
    """Build schema-aligned report JSON from state; return { report_payload }."""
    symbol = state.get("symbol") or ""
    logger.info("report_generator: building payload for %s", symbol)
    try:
        payload = _build_report_payload(state)
        logger.info("report_generator: done for %s, payload keys: %s", symbol, list(payload.keys()))
        return {"report_payload": payload}
    except Exception as e:
        logger.exception("report_generator failed for %s: %s", symbol, e)
        raise
