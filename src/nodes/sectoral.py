"""Sectoral node: headwinds and tailwinds for the sector."""

from __future__ import annotations

import logging
from typing import Any

from src.data.concall import get_transcripts_from_db
from src.state import ResearchState

from .prompts import invoke_llm_structured, sectoral_from_transcripts_prompt, sectoral_prompt
from .schemas import SectoralFromTranscripts, SectoralStructured

logger = logging.getLogger(__name__)

_MIN_ITEMS = 2  # need at least 2 headwinds AND tailwinds to skip web search


def sectoral(state: ResearchState) -> dict[str, Any]:
    """Generate sectoral headwinds/tailwinds; return state update.

    Tries transcript extraction first (management's own words, no web search cost).
    Falls back to web search if transcripts yield fewer than _MIN_ITEMS in either list.
    If both sources contribute, management bullets come first.
    """
    symbol = state.get("symbol") or ""
    logger.info("sectoral: starting for %s", symbol)
    company_name = state.get("company_name") or symbol
    sector = state.get("sector") or state.get("industry") or ""

    mgmt_headwinds: list[str] = []
    mgmt_tailwinds: list[str] = []

    # --- Try 1: extract from transcripts (no web search cost) ---
    try:
        transcripts = get_transcripts_from_db(symbol)
        recent = [t for t in transcripts[:4] if t.get("text")]
        if recent:
            transcript_block = "\n\n".join(
                f"--- Transcript {i + 1} | {t['date']} ---\n{(t['text'] or '')[:8000]}"
                for i, t in enumerate(recent)
            )
            system, user = sectoral_from_transcripts_prompt(company_name, transcript_block)
            parsed = invoke_llm_structured(system, user, SectoralFromTranscripts, use_web_search=False)
            if parsed:
                mgmt_headwinds = [s.strip() for s in parsed.headwinds if s]
                mgmt_tailwinds = [s.strip() for s in parsed.tailwinds if s]
    except Exception as e:
        logger.warning("sectoral: transcript extraction failed (%s) — falling back to web search", e)

    # Rich enough from transcripts alone — skip web search
    if len(mgmt_headwinds) >= _MIN_ITEMS and len(mgmt_tailwinds) >= _MIN_ITEMS:
        logger.info("sectoral: used transcript extraction for %s", symbol)
        return {
            "sectoral_analysis": "",
            "sectoral_headwinds": mgmt_headwinds,
            "sectoral_tailwinds": mgmt_tailwinds,
            "sectoral_source": "management_commentary",
        }

    # --- Try 2: web search (runs when transcripts gave < _MIN_ITEMS in either list) ---
    system, user = sectoral_prompt(company_name, sector)
    parsed_web = invoke_llm_structured(system, user, SectoralStructured, use_web_search=True)
    analysis = ""
    web_headwinds: list[str] = []
    web_tailwinds: list[str] = []
    if parsed_web:
        analysis = parsed_web.analysis
        web_headwinds = [s.strip() for s in parsed_web.headwinds if s]
        web_tailwinds = [s.strip() for s in parsed_web.tailwinds if s]
    else:
        analysis = "Sectoral analysis unavailable (parse failure)."

    # Combine: management bullets first, then web search bullets
    has_mgmt = bool(mgmt_headwinds or mgmt_tailwinds)
    source = "management_commentary_and_web_search" if has_mgmt else "web_search"
    logger.info("sectoral: source=%s for %s", source, symbol)
    return {
        "sectoral_analysis": analysis,
        "sectoral_headwinds": mgmt_headwinds + web_headwinds,
        "sectoral_tailwinds": mgmt_tailwinds + web_tailwinds,
        "sectoral_source": source,
    }
