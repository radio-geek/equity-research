"""Concall evaluator node: LLM-powered analysis of last 8 quarters of conference calls."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import concall_prompt, invoke_llm

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
    """Balance unclosed <div> tags to prevent CSS bleeding into subsequent sections."""
    opens = html.count("<div")
    closes = html.count("</div>")
    diff = opens - closes
    if diff > 0:
        logger.warning("Concall HTML has %d unclosed <div> tag(s); auto-closing.", diff)
        html = html + "</div>" * diff
    return html


def _extract_section_title(html: str) -> str:
    """Read data-section-title from the outermost div; default to 'Concall Evaluation'."""
    m = re.search(r'data-section-title=["\']([^"\']+)["\']', html)
    title = m.group(1) if m else "Concall Evaluation"
    logger.debug("concall_evaluator: section title = %r", title)
    return title


def concall_evaluator(state: ResearchState) -> dict[str, Any]:
    """Fetch and analyze last 8 quarters of concalls; return HTML-formatted evaluation."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("concall_evaluator: starting for %s (%s)", symbol, exchange)

    system, user = concall_prompt(company_name, symbol, exchange)

    logger.debug("concall_evaluator: invoking LLM with web search")
    html = invoke_llm(system, user, use_web_search=True)
    logger.debug("concall_evaluator: raw LLM output length=%d chars", len(html))

    html = _clean_html_output(html)
    html = _close_open_divs(html)
    section_title = _extract_section_title(html)

    logger.info("concall_evaluator: done, final HTML length=%d chars, title=%r", len(html), section_title)
    return {"concall_evaluation": html, "concall_section_title": section_title}
