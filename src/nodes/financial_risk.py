"""Financial risk node: ROE, ROCE, D/E, liquidity from ratios and quote."""

from __future__ import annotations

from typing import Any

from src.state import ResearchState

from .prompts import financial_risk_prompt, invoke_llm


def financial_risk(state: ResearchState) -> dict[str, Any]:
    """Generate financial risk summary; return state update."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    ratios = state.get("financial_ratios") or []
    quote = state.get("quote") or {}
    system, user = financial_risk_prompt(company_name, symbol, ratios, quote)
    text = invoke_llm(system, user)
    return {"financial_risk": text}
