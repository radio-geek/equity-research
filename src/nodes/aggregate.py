"""Aggregate node: executive summary from all research sections."""

from __future__ import annotations

import logging
from typing import Any

from src.state import ResearchState

from .prompts import aggregate_prompt, invoke_llm

logger = logging.getLogger(__name__)


def aggregate(state: ResearchState) -> dict[str, Any]:
    """Generate executive summary from all research fields; return state update."""
    symbol = state.get("symbol") or ""
    logger.info("aggregate: starting for %s", symbol)
    company_overview = state.get("company_overview") or ""
    management_research = state.get("management_research") or ""
    financial_risk = state.get("financial_risk") or ""
    concall_evaluation = state.get("concall_evaluation") or ""
    sectoral_analysis = state.get("sectoral_analysis") or ""
    try:
        system, user = aggregate_prompt(
            company_overview,
            management_research,
            financial_risk,
            concall_evaluation,
            sectoral_analysis,
        )
        text = invoke_llm(system, user)
        logger.info("aggregate: done for %s, executive_summary len=%d", symbol, len(text or ""))
        return {"executive_summary": text}
    except Exception as e:
        logger.exception("aggregate failed for %s: %s", symbol, e)
        raise
