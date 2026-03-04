"""Yearly + TTM financials node: fetch yearly metrics + TTM, then LLM highlights from TTM data."""

from __future__ import annotations

import logging
from typing import Any

from src.data import yearly_financials
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
    """Fetch yearly + TTM metrics, then get good/bad highlights from TTM statements via LLM."""
    symbol = (state.get("symbol") or "").strip().upper()
    exchange = (state.get("exchange") or "NSE").strip().upper()
    company_name = (state.get("company_name") or symbol).strip()
    if not symbol:
        return {"yearly_metrics": [], "qoq_highlights": {"good": [], "bad": []}}

    metrics = yearly_financials.fetch_yearly_financials(symbol, exchange, max_years=8)

    highlights = {"good": [], "bad": []}
    statements = yearly_financials.get_ttm_statements(symbol, exchange)
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

    return {"yearly_metrics": metrics, "qoq_highlights": highlights}
