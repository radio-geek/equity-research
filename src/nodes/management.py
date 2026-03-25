"""Management research node: governance, shareholding, quality of management."""

from __future__ import annotations

import logging
from typing import Any

from src.state import ResearchState

from .prompts import invoke_llm_structured, management_prompt
from .schemas import ManagementStructured

logger = logging.getLogger(__name__)


def management(state: ResearchState) -> dict[str, Any]:
    """Generate management research (structured + narrative); return state update."""
    symbol = state.get("symbol") or ""
    logger.info("management: starting for %s", symbol)
    company_name = state.get("company_name") or state.get("symbol") or ""
    meta = state.get("meta") or {}
    shareholding = state.get("shareholding") or []
    system, user = management_prompt(company_name, symbol, meta, shareholding)
    parsed = invoke_llm_structured(
        system, user, ManagementStructured, use_web_search=True, use_tavily_only=False
    )
    logger.info("management: done for %s", symbol)

    management_people: list[dict] = []
    management_research = ""

    if parsed:
        management_people = [
            {"name": p.name, "designation": p.designation, "description": p.description}
            for p in parsed.people
        ]
        management_research = (parsed.rpt_and_gaps or "").strip()
        if not management_research and management_people:
            management_research = "Related party transactions and gaps: see search results above where available."
        logger.info(
            "management: parsed structured output, people=%d",
            len(management_people),
        )

    if not management_research:
        management_research = "Management data unavailable (parse or search failure)."

    out: dict[str, Any] = {"management_research": management_research}
    if management_people:
        out["management_people"] = management_people
    return out
