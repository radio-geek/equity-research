"""Management research node: governance, shareholding, quality of management."""

from __future__ import annotations

from typing import Any

from src.state import ResearchState

from .prompts import invoke_llm, management_prompt


def management(state: ResearchState) -> dict[str, Any]:
    """Generate management research summary; return state update."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    meta = state.get("meta") or {}
    shareholding = state.get("shareholding") or []
    system, user = management_prompt(company_name, symbol, meta, shareholding)
    text = invoke_llm(system, user)
    return {"management_research": text}
