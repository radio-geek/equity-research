"""Financial risk node: ROE, ROCE, D/E, liquidity from ratios and quote."""

from __future__ import annotations

import logging
from typing import Any

from src.state import ResearchState

from .prompts import financial_risk_prompt, invoke_llm

logger = logging.getLogger(__name__)


def financial_risk(state: ResearchState) -> dict[str, Any]:
    """Generate financial risk summary; return state update."""
    symbol = state.get("symbol") or ""
    logger.info("financial_risk: starting for %s", symbol)
    company_name = state.get("company_name") or state.get("symbol") or ""
    ratios = state.get("financial_ratios") or []
    quote = state.get("quote") or {}
    system, user = financial_risk_prompt(company_name, symbol, ratios, quote)
    text = invoke_llm(system, user)
    logger.info("financial_risk: done for %s", symbol)
    return {"financial_risk": text}
