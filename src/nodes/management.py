"""Management research node: governance, shareholding, quality of management."""

from __future__ import annotations

import logging
from typing import Any

from src.state import ResearchState

from .prompts import invoke_llm, management_prompt

logger = logging.getLogger(__name__)


def management(state: ResearchState) -> dict[str, Any]:
    """Generate management research summary; return state update."""
    symbol = state.get("symbol") or ""
    logger.info("management: starting for %s", symbol)
    company_name = state.get("company_name") or state.get("symbol") or ""
    meta = state.get("meta") or {}
    shareholding = state.get("shareholding") or []
    system, user = management_prompt(company_name, symbol, meta, shareholding)
    text = invoke_llm(system, user)
    logger.info("management: done for %s", symbol)
    return {"management_research": text}
