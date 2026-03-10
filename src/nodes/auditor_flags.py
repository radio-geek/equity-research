"""Auditor flags node: surfaces qualification, emphasis of matter, going concern, CARO observations."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import auditor_flags_prompt, invoke_llm

logger = logging.getLogger(__name__)


def _clean_markdown_output(text: str) -> str:
    """Strip markdown code fences and leading/trailing junk from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def auditor_flags(state: ResearchState) -> dict[str, Any]:
    """Search for auditor qualifications and return Markdown-formatted flag section."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("auditor_flags: starting for %s (%s)", symbol, exchange)

    system, user = auditor_flags_prompt(company_name, symbol, exchange)

    logger.debug("auditor_flags: invoking LLM with web search")
    markdown = invoke_llm(system, user, use_web_search=True)
    logger.debug("auditor_flags: raw LLM output length=%d chars", len(markdown))

    markdown = _clean_markdown_output(markdown)
    logger.info("auditor_flags: done, final markdown length=%d chars", len(markdown))
    return {"auditor_flags": markdown}
