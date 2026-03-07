"""Concall evaluator node: LLM-powered analysis of last 8 quarters; returns structured JSON."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import concall_structured_prompt, invoke_llm

logger = logging.getLogger(__name__)


def _strip_json_preamble(text: str) -> str:
    """Strip markdown code fences and any non-JSON preamble."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    idx = text.find("{")
    if idx > 0:
        logger.debug("Stripping %d chars of preamble before first {", idx)
        text = text[idx:]
    return text.strip()


def _validate_concall_shape(data: dict) -> bool:
    """Check minimal required keys for report schema."""
    if not isinstance(data, dict):
        return False
    t = data.get("type")
    if t not in ("mainboard_concall", "sme_updates"):
        return False
    if not data.get("sectionTitle"):
        data["sectionTitle"] = "Concall Evaluation" if t == "mainboard_concall" else "Company Updates"
    if "cards" not in data:
        data["cards"] = []
    return True


def concall_evaluator(state: ResearchState) -> dict[str, Any]:
    """Fetch and analyze last 8 quarters of concalls; return structured JSON for report payload."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("concall_evaluator: starting for %s (%s)", symbol, exchange)

    system, user = concall_structured_prompt(company_name, symbol, exchange)

    logger.debug("concall_evaluator: invoking LLM with web search")
    raw = invoke_llm(system, user, use_web_search=True)
    logger.debug("concall_evaluator: raw LLM output length=%d chars", len(raw or ""))

    concall_structured = None
    concall_evaluation = ""
    if raw:
        stripped = _strip_json_preamble(raw)
        try:
            data = json.loads(stripped)
            if _validate_concall_shape(data):
                concall_structured = data
                # Brief text for aggregate node (executive summary)
                parts = [data.get("summary") or ""]
                if data.get("type") == "sme_updates" and data.get("summaryBar", {}).get("text"):
                    parts.append(data["summaryBar"]["text"])
                for card in (data.get("cards") or [])[:3]:
                    period = card.get("period", "")
                    bullets = card.get("bullets", [])
                    if period and bullets:
                        parts.append(f"{period}: {' '.join(bullets[:2])}")
                concall_evaluation = "\n\n".join(p for p in parts if p).strip() or "Concall/company updates analyzed."
                logger.info(
                    "concall_evaluator: done, type=%s, cards=%d",
                    data.get("type"),
                    len(data.get("cards", [])),
                )
            else:
                logger.warning("concall_evaluator: parsed JSON failed shape validation")
        except json.JSONDecodeError as e:
            logger.warning("concall_evaluator: JSON parse failed: %s", e)

    out = {"concall_structured": concall_structured}
    if concall_evaluation:
        out["concall_evaluation"] = concall_evaluation
        out["concall_section_title"] = (
            concall_structured.get("sectionTitle") if concall_structured else "Concall Evaluation"
        )
    return out
