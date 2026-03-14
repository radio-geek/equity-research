"""Sectoral node: headwinds and tailwinds for the sector."""

from __future__ import annotations

import logging
from typing import Any

from src.state import ResearchState

from .prompts import invoke_llm_structured, sectoral_prompt
from .schemas import SectoralStructured

logger = logging.getLogger(__name__)


def sectoral(state: ResearchState) -> dict[str, Any]:
    """Generate sectoral headwinds/tailwinds; return state update."""
    symbol = state.get("symbol") or ""
    logger.info("sectoral: starting for %s", symbol)
    company_name = state.get("company_name") or state.get("symbol") or ""
    sector = state.get("sector") or state.get("industry") or ""
    system, user = sectoral_prompt(company_name, sector)
    parsed = invoke_llm_structured(system, user, SectoralStructured, use_web_search=True)
    analysis = ""
    headwinds: list[str] = []
    tailwinds: list[str] = []
    if parsed:
        analysis = parsed.analysis
        headwinds = [s.strip() for s in parsed.headwinds if s]
        tailwinds = [s.strip() for s in parsed.tailwinds if s]
    else:
        analysis = "Sectoral analysis unavailable (parse failure)."
    logger.info("sectoral: done for %s", symbol)
    return {
        "sectoral_analysis": analysis,
        "sectoral_headwinds": headwinds,
        "sectoral_tailwinds": tailwinds,
    }
