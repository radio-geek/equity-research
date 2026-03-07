"""Sectoral node: headwinds and tailwinds for the sector."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import invoke_llm, sectoral_prompt

logger = logging.getLogger(__name__)


def _parse_sectoral_response(text: str) -> tuple[str, list[str], list[str]]:
    """Parse LLM response into analysis string and headwinds/tailwinds lists.

    Expects JSON with keys analysis, headwinds, tailwinds. On parse failure returns
    full text as analysis and empty lists.
    """
    analysis = text.strip()
    headwinds: list[str] = []
    tailwinds: list[str] = []

    # Strip markdown code fence if present
    stripped = re.sub(r"^```(?:json)?\s*", "", analysis, flags=re.MULTILINE)
    stripped = re.sub(r"\s*```\s*$", "", stripped, flags=re.MULTILINE).strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            analysis = data.get("analysis") or analysis
            if isinstance(analysis, str):
                pass
            else:
                analysis = text.strip()
            h = data.get("headwinds")
            t = data.get("tailwinds")
            if isinstance(h, list):
                headwinds = [str(x).strip() for x in h if x]
            if isinstance(t, list):
                tailwinds = [str(x).strip() for x in t if x]
    except (json.JSONDecodeError, TypeError) as e:
        logger.debug("sectoral: JSON parse failed, using full text as analysis: %s", e)

    if not isinstance(analysis, str):
        analysis = text.strip()
    return analysis, headwinds, tailwinds


def sectoral(state: ResearchState) -> dict[str, Any]:
    """Generate sectoral headwinds/tailwinds; return state update."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    sector = state.get("sector") or state.get("industry") or ""
    system, user = sectoral_prompt(company_name, sector)
    text = invoke_llm(system, user)
    analysis, headwinds, tailwinds = _parse_sectoral_response(text or "")
    return {
        "sectoral_analysis": analysis,
        "sectoral_headwinds": headwinds,
        "sectoral_tailwinds": tailwinds,
    }
