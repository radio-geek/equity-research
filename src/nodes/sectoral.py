"""Sectoral node: headwinds and tailwinds for the sector."""

from __future__ import annotations

from typing import Any

from src.state import ResearchState

from .prompts import invoke_llm, sectoral_prompt


def sectoral(state: ResearchState) -> dict[str, Any]:
    """Generate sectoral headwinds/tailwinds; return state update."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    sector = state.get("sector") or state.get("industry") or ""
    system, user = sectoral_prompt(company_name, sector)
    text = invoke_llm(system, user)
    return {"sectoral_analysis": text}
