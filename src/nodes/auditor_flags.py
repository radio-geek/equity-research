"""Auditor flags node: surfaces qualification, emphasis of matter, going concern, CARO observations."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import auditor_flags_prompt, invoke_llm

logger = logging.getLogger(__name__)


def _clean_html_output(text: str) -> str:
    """Strip markdown code fences and any non-HTML preamble from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    idx = text.find("<div")
    if idx > 0:
        logger.debug("Stripping %d chars of preamble before first <div", idx)
        text = text[idx:]
    return text.strip()


def _close_open_divs(html: str) -> str:
    """Balance unclosed <div> tags to prevent CSS bleeding."""
    opens = html.count("<div")
    closes = html.count("</div>")
    diff = opens - closes
    if diff > 0:
        logger.warning("Auditor flags HTML has %d unclosed <div> tag(s); auto-closing.", diff)
        html = html + "</div>" * diff
    return html


def auditor_flags(state: ResearchState) -> dict[str, Any]:
    """Search for auditor qualifications and return HTML-formatted flag section."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("auditor_flags: starting for %s (%s)", symbol, exchange)

    system, user = auditor_flags_prompt(company_name, symbol, exchange)

    logger.debug("auditor_flags: invoking LLM with web search")
    html = invoke_llm(system, user, use_web_search=True)
    logger.debug("auditor_flags: raw LLM output length=%d chars", len(html))

    html = _clean_html_output(html)
    html = _close_open_divs(html)

    logger.info("auditor_flags: done, final HTML length=%d chars", len(html))
    return {"auditor_flags": html}
