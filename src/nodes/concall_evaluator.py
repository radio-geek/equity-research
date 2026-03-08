"""Concall evaluator node: reads cached NSE transcripts from DB, analyses with LLM.

Transcripts are pre-loaded into DB by refresh_transcript_cache() before the pipeline runs.
Falls back to web search if DB has no transcripts for this symbol.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.state import ResearchState
from src.data.concall import get_transcripts_from_db

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
    """Fetch NSE transcripts, extract PDF text, analyse with LLM (no web search)."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("concall_evaluator: starting for %s (%s)", symbol, exchange)

    # Step 1: Load transcripts from DB cache (populated by refresh_transcript_cache before pipeline)
    transcripts = []
    use_web_search = False
    try:
        transcripts = get_transcripts_from_db(symbol, exchange)
        if transcripts:
            logger.info(
                "concall_evaluator: got %d transcripts from DB (segment=%s)",
                len(transcripts), transcripts[0].get("segment", "?"),
            )
        else:
            logger.warning(
                "concall_evaluator: no DB transcripts for %s — falling back to web search", symbol
            )
            use_web_search = True
    except Exception as e:
        logger.warning("concall_evaluator: DB read failed (%s) — falling back to web search", e)
        use_web_search = True

    # Step 2: Build prompt — with real transcripts (no web search) or web search fallback
    system, user = concall_structured_prompt(
        company_name, symbol, exchange,
        transcripts=transcripts if not use_web_search else None,
    )

    logger.info(
        "concall_evaluator: invoking LLM (use_web_search=%s, transcripts=%d)",
        use_web_search, len(transcripts),
    )
    raw = invoke_llm(system, user, use_web_search=use_web_search)
    logger.debug("concall_evaluator: raw LLM output length=%d chars", len(raw or ""))

    # Step 3: Parse and validate JSON output
    concall_structured = None
    concall_evaluation = ""
    if raw:
        stripped = _strip_json_preamble(raw)
        try:
            data = json.loads(stripped)
            if _validate_concall_shape(data):
                concall_structured = data
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
                    "concall_evaluator: done, type=%s, cards=%d, source=%s",
                    data.get("type"),
                    len(data.get("cards", [])),
                    "nse_transcripts" if not use_web_search else "web_search",
                )
            else:
                logger.warning("concall_evaluator: parsed JSON failed shape validation")
        except json.JSONDecodeError as e:
            logger.warning("concall_evaluator: JSON parse failed: %s", e)

    # Build transcript links list for state (date + link, no raw text to keep state lean)
    transcript_links = [
        {"date": t["date"], "link": t["link"], "description": t["description"]}
        for t in transcripts
    ]

    out: dict[str, Any] = {
        "concall_structured": concall_structured,
        "concall_transcript_links": transcript_links,
    }
    if concall_evaluation:
        out["concall_evaluation"] = concall_evaluation
        out["concall_section_title"] = (
            concall_structured.get("sectionTitle") if concall_structured else "Concall Evaluation"
        )
    return out
