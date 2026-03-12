"""Company overview node: structured JSON (opening, value chain, table, products, timeline)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import company_overview_structured_prompt, invoke_llm

logger = logging.getLogger(__name__)


def _strip_json_preamble(text: str) -> str:
    """Strip markdown code fences and any non-JSON preamble."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    idx = text.find("{")
    if idx > 0:
        logger.debug("company_overview: stripping %d chars of preamble before first {", idx)
        text = text[idx:]
    return text.strip()


def _validate_company_overview_shape(data: dict) -> bool:
    """Check minimal required keys for structured company overview."""
    if not isinstance(data, dict):
        return False
    if not data.get("opening") or not isinstance(data["opening"], str):
        return False
    vc = data.get("value_chain")
    if not isinstance(vc, dict) or "stages" not in vc:
        return False
    if not isinstance(vc.get("stages"), list):
        return False
    if not vc.get("company_position") and not vc.get("company_position_description"):
        return False
    bmt = data.get("business_model_table")
    if not isinstance(bmt, dict):
        return False
    if "rows" not in bmt or not isinstance(bmt["rows"], list):
        return False
    if not isinstance(data.get("key_products"), list):
        return False
    if not isinstance(data.get("recent_developments"), list):
        return False
    return True


def _summary_from_structured(data: dict) -> str:
    """Build a short string summary for aggregate and PDF fallback."""
    parts = [data.get("opening") or ""]
    vc = data.get("value_chain") or {}
    desc = vc.get("company_position_description")
    pos = vc.get("company_position")
    if desc:
        parts.append(f"Value chain: {desc}")
    elif pos:
        parts.append(f"Value chain position: {pos}")
    return "\n\n".join(p for p in parts if p).strip()


def company_overview(state: ResearchState) -> dict[str, Any]:
    """Generate structured company overview; return state update with company_overview_structured and company_overview."""
    symbol = state.get("symbol") or ""
    logger.info("company_overview: starting for %s", symbol)
    company_name = state.get("company_name") or state.get("symbol") or ""
    meta = state.get("meta") or {}
    quote = state.get("quote") or {}
    system, user = company_overview_structured_prompt(company_name, symbol, meta, quote)
    raw = invoke_llm(system, user, use_web_search=True, use_tavily_only=False)
    logger.debug("company_overview: raw LLM output length=%d chars", len(raw or ""))

    company_overview_structured = None
    company_overview = ""

    if raw:
        stripped = _strip_json_preamble(raw)
        try:
            data = json.loads(stripped)
            if _validate_company_overview_shape(data):
                company_overview_structured = data
                company_overview = _summary_from_structured(data)
                logger.info("company_overview: done for %s (structured)", symbol)
            else:
                logger.warning("company_overview: parsed JSON failed shape validation")
                company_overview = raw[:4000] if len(raw) > 4000 else raw
        except json.JSONDecodeError as e:
            logger.warning("company_overview: JSON parse failed: %s", e)
            company_overview = raw[:4000] if len(raw) > 4000 else raw

    out: dict[str, Any] = {"company_overview": company_overview or "Overview unavailable."}
    if company_overview_structured is not None:
        out["company_overview_structured"] = company_overview_structured
    return out
