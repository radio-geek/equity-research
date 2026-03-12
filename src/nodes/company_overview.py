"""Company overview node: structured JSON (opening, value chain, table, products, timeline)."""

from __future__ import annotations

import logging
from typing import Any

from src.state import ResearchState

from .prompts import company_overview_structured_prompt, invoke_llm_structured
from .schemas import CompanyOverviewStructured

logger = logging.getLogger(__name__)


def _summary_from_structured(data: CompanyOverviewStructured) -> str:
    """Build a short string summary for aggregate and PDF fallback."""
    parts = [data.opening or ""]
    vc = data.value_chain
    if vc.company_position_description:
        parts.append(f"Value chain: {vc.company_position_description}")
    elif vc.company_position:
        parts.append(f"Value chain position: {vc.company_position}")
    return "\n\n".join(p for p in parts if p).strip()


def _structured_to_payload(data: CompanyOverviewStructured) -> dict[str, Any]:
    """Convert Pydantic model to report payload (dict) for state and templates."""
    vc = data.value_chain
    return {
        "opening": data.opening,
        "value_chain": {
            "stages": vc.stages,
            "company_stage_indices": vc.company_stage_indices,
            "company_position_description": vc.company_position_description,
            "company_position": vc.company_position,
        },
        "business_model_table": {
            "rows": [
                {"segment": r.segment, "importance": r.importance, "description": r.description}
                for r in data.business_model_table.rows
            ],
        },
        "key_products": data.key_products,
        "recent_developments": [{"year": rd.year, "event": rd.event} for rd in data.recent_developments],
    }


def company_overview(state: ResearchState) -> dict[str, Any]:
    """Generate structured company overview; return state update with company_overview_structured and company_overview."""
    symbol = state.get("symbol") or ""
    logger.info("company_overview: starting for %s", symbol)
    company_name = state.get("company_name") or state.get("symbol") or ""
    meta = state.get("meta") or {}
    quote = state.get("quote") or {}
    system, user = company_overview_structured_prompt(company_name, symbol, meta, quote)
    parsed = invoke_llm_structured(
        system, user, CompanyOverviewStructured, use_web_search=True, use_tavily_only=False
    )
    logger.debug("company_overview: structured invoke returned %s", "ok" if parsed else "None")

    company_overview_structured = None
    company_overview = ""

    if parsed:
        company_overview_structured = _structured_to_payload(parsed)
        company_overview = _summary_from_structured(parsed)
        logger.info("company_overview: done for %s (structured)", symbol)
    else:
        company_overview = "Overview unavailable."

    out: dict[str, Any] = {"company_overview": company_overview or "Overview unavailable."}
    if company_overview_structured is not None:
        out["company_overview_structured"] = company_overview_structured
    return out
