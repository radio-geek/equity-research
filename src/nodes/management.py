"""Management research node: governance, shareholding, quality of management."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import invoke_llm, management_prompt

logger = logging.getLogger(__name__)


def _strip_json_preamble(text: str) -> str:
    """Strip markdown code fences and any non-JSON preamble."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    idx = text.find("{")
    if idx > 0:
        logger.debug("management: stripping %d chars of preamble before first {", idx)
        text = text[idx:]
    return text.strip()


def _validate_management_shape(data: dict) -> bool:
    """Check minimal required keys for structured management output."""
    if not isinstance(data, dict):
        return False
    if "people" not in data or not isinstance(data["people"], list):
        return False
    if "governance_news" not in data or not isinstance(data["governance_news"], list):
        return False
    for p in data["people"]:
        if not isinstance(p, dict) or "name" not in p or "designation" not in p or "description" not in p:
            return False
    for n in data["governance_news"]:
        if not isinstance(n, dict) or "text" not in n or "sentiment" not in n:
            return False
        if n.get("sentiment") not in ("positive", "negative", "neutral"):
            return False
    return True


def _normalize_people(people: list) -> list[dict]:
    """Ensure each person has name, designation, description (strings)."""
    out = []
    for p in people:
        if not isinstance(p, dict):
            continue
        out.append({
            "name": str(p.get("name") or "").strip(),
            "designation": str(p.get("designation") or "").strip(),
            "description": str(p.get("description") or "").strip(),
        })
    return out


def _normalize_governance_news(news: list) -> list[dict]:
    """Ensure each item has text and sentiment (positive|negative|neutral)."""
    out = []
    for n in news:
        if not isinstance(n, dict):
            continue
        sent = (n.get("sentiment") or "neutral").lower()
        if sent not in ("positive", "negative", "neutral"):
            sent = "neutral"
        out.append({
            "text": str(n.get("text") or "").strip(),
            "sentiment": sent,
        })
    return out


def management(state: ResearchState) -> dict[str, Any]:
    """Generate management research (structured + narrative); return state update."""
    symbol = state.get("symbol") or ""
    logger.info("management: starting for %s", symbol)
    company_name = state.get("company_name") or state.get("symbol") or ""
    meta = state.get("meta") or {}
    shareholding = state.get("shareholding") or []
    system, user = management_prompt(company_name, symbol, meta, shareholding)
    raw = invoke_llm(system, user, use_web_search=True, use_tavily_only=False)
    logger.info("management: done for %s", symbol)

    management_people: list[dict] = []
    management_governance_news: list[dict] = []
    management_research = ""

    if raw:
        stripped = _strip_json_preamble(raw)
        try:
            data = json.loads(stripped)
            if _validate_management_shape(data):
                management_people = _normalize_people(data.get("people") or [])
                management_governance_news = _normalize_governance_news(data.get("governance_news") or [])
                management_research = (data.get("rpt_and_gaps") or "").strip()
                if not management_research and (management_people or management_governance_news):
                    management_research = "Related party transactions and gaps: see search results above where available."
                logger.info(
                    "management: parsed structured output, people=%d, news=%d",
                    len(management_people),
                    len(management_governance_news),
                )
            else:
                logger.warning("management: parsed JSON failed shape validation")
                management_research = raw[:5000] if len(raw) > 5000 else raw
        except json.JSONDecodeError as e:
            logger.warning("management: JSON parse failed: %s", e)
            management_research = raw[:5000] if len(raw) > 5000 else raw

    if not management_research:
        management_research = "Management & governance data unavailable (parse or search failure)."

    out: dict[str, Any] = {"management_research": management_research}
    if management_people:
        out["management_people"] = management_people
    if management_governance_news:
        out["management_governance_news"] = management_governance_news
    return out
