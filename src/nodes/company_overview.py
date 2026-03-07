"""Company overview node: summarize business, sector, key products from NSE data."""

from __future__ import annotations

from typing import Any

from src.state import ResearchState

from .prompts import company_overview_prompt, invoke_llm


def company_overview(state: ResearchState) -> dict[str, Any]:
    """Generate company overview from meta and quote; return state update."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    meta = state.get("meta") or {}
    quote = state.get("quote") or {}
    system, user = company_overview_prompt(company_name, symbol, meta, quote)
    text = invoke_llm(system, user, use_tavily_only=True)
    return {"company_overview": text}
