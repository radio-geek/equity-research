"""Yearly + TTM financials node: fetch yearly metrics + TTM, scorecard, 5-year trend, highlights, trend insight."""

from __future__ import annotations

import logging
from typing import Any

from src.data import yearly_financials
from src.data.screener_scraper import fetch_company_quote
from src.report.financial_evaluation import (
    build_financial_scorecard,
    build_five_year_trend_table,
    build_trend_insight_summary,
)
from src.state import ResearchState

from .prompts import balance_sheet_highlights_prompt, invoke_llm

logger = logging.getLogger(__name__)


def _parse_highlights(response: str) -> dict[str, list[str]]:
    """Parse GOOD: / BAD: sections from LLM response into {"good": [...], "bad": [...]}."""
    good: list[str] = []
    bad: list[str] = []
    section = None
    for line in response.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("GOOD:"):
            section = "good"
            rest = line[5:].strip()
            if rest and rest.startswith("-"):
                good.append(rest.lstrip("- ").strip())
            continue
        if line.upper().startswith("BAD:"):
            section = "bad"
            rest = line[4:].strip()
            if rest and rest.startswith("-"):
                bad.append(rest.lstrip("- ").strip())
            continue
        if line.startswith("-"):
            bullet = line.lstrip("- ").strip()
            if section == "good" and bullet:
                good.append(bullet)
            elif section == "bad" and bullet:
                bad.append(bullet)
    return {"good": good, "bad": bad}


def qoq_financials(state: ResearchState) -> dict[str, Any]:
    """Fetch yearly + TTM metrics; build scorecard, 5-year trend, highlights, trend insight."""
    symbol = (state.get("symbol") or "").strip().upper()
    exchange = (state.get("exchange") or "NSE").strip().upper()
    company_name = (state.get("company_name") or symbol).strip()
    if not symbol:
        logger.warning("qoq_financials: no symbol in state")
        return {
            "yearly_metrics": [],
            "qoq_highlights": {"good": [], "bad": []},
            "financial_scorecard": None,
            "five_year_trend": {"headers": [], "rows": []},
            "trend_insight_summary": "",
        }

    logger.info("qoq_financials: starting for %s (%s)", symbol, exchange)
    try:
        metrics = yearly_financials.fetch_yearly_financials(symbol, exchange, max_years=8)
        logger.info("qoq_financials: yearly_metrics -> %d rows", len(metrics) if metrics else 0)
    except Exception as e:
        logger.exception("qoq_financials: fetch_yearly_financials failed for %s: %s", symbol, e)
        metrics = []

    financial_ratios = state.get("financial_ratios") or []

    try:
        scorecard = build_financial_scorecard(metrics, financial_ratios)
        logger.info("qoq_financials: scorecard -> score=%s/%s", scorecard.get("score"), scorecard.get("total"))
    except Exception as e:
        logger.exception("qoq_financials: build_financial_scorecard failed: %s", e)
        scorecard = {"score": 0, "total": 6, "verdict": "Error building scorecard", "metrics": []}

    try:
        five_year_trend = build_five_year_trend_table(metrics)
        logger.info("qoq_financials: five_year_trend -> %d headers, %d rows", len(five_year_trend.get("headers") or []), len(five_year_trend.get("rows") or []))
    except Exception as e:
        logger.exception("qoq_financials: build_five_year_trend_table failed: %s", e)
        five_year_trend = {"headers": [], "rows": []}

    trend_insight = build_trend_insight_summary(five_year_trend, company_name)

    highlights = {"good": [], "bad": []}
    try:
        statements = yearly_financials.get_ttm_statements(symbol, exchange)
    except Exception as e:
        logger.warning("qoq_financials: get_ttm_statements failed: %s", e)
        statements = {}
    if statements and (
        statements.get("balance_sheet_text") or statements.get("income_statement_text")
    ):
        system, user = balance_sheet_highlights_prompt(
            company_name,
            symbol,
            statements.get("period_label", "TTM"),
            statements.get("income_statement_text", ""),
            statements.get("balance_sheet_text", ""),
        )
        try:
            response = invoke_llm(system, user, use_web_search=False)
            if response:
                highlights = _parse_highlights(response)
        except Exception as e:
            logger.warning("Balance sheet highlights LLM failed: %s", e)

    screener_quote = {}
    try:
        screener_quote = fetch_company_quote(symbol)
    except Exception as e:
        logger.warning("qoq_financials: fetch_company_quote failed for %s: %s", symbol, e)

    logger.info("qoq_financials: done for %s", symbol)
    return {
        "yearly_metrics": metrics,
        "qoq_highlights": highlights,
        "financial_scorecard": scorecard,
        "five_year_trend": five_year_trend,
        "trend_insight_summary": trend_insight,
        "screener_quote": screener_quote,
    }
