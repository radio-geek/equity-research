"""Concall evaluator node: reads cached NSE transcripts from DB, analyses with LLM.

Mainboard companies: one focused LLM call per transcript (no web search), deterministic
missing cards for uncovered quarters, one summary+guidance call at the end.

SME companies: existing single-call flow unchanged.
No transcripts: existing company-updates flow unchanged.

Transcripts are pre-loaded into DB by refresh_transcript_cache() before the pipeline runs.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any

from src.state import ResearchState
from src.data.concall import get_transcripts_from_db, fetch_company_updates_data
from src.data.indian_quarters import get_last_n_quarters

from .prompts import (
    concall_structured_prompt,
    concall_single_card_prompt,
    concall_summary_prompt,
    company_updates_prompt,
    invoke_llm,
    invoke_llm_structured,
    _last_8_quarters,
)
from .schemas import ConcallCardExtraction, ConcallSummaryExtraction

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
    if t not in ("mainboard_concall", "sme_updates", "no_concall_updates"):
        return False
    if not data.get("sectionTitle"):
        data["sectionTitle"] = (
            "Concall Evaluation" if t == "mainboard_concall"
            else "Company Updates"
        )
    if t in ("mainboard_concall", "sme_updates") and "cards" not in data:
        data["cards"] = []
    return True


def _extract_single_card(company_name: str, quarter_label: str, transcript: dict) -> dict:
    """Call LLM to extract one card from one transcript. No web search."""
    system, user = concall_single_card_prompt(company_name, quarter_label, transcript)
    parsed = invoke_llm_structured(system, user, ConcallCardExtraction, use_web_search=False)
    card: dict = {
        "period": quarter_label,
        "badge": "concall",
        "link": transcript.get("link") or None,
        "events": [],
        "qaHighlights": [],
        "bullets": [],
        "guidance": None,
        "_capex": [],  # temp key — collected and removed below
    }
    if parsed:
        card["bullets"] = [b.strip() for b in parsed.bullets if b]
        card["events"] = [e.model_dump() for e in parsed.events]
        card["qaHighlights"] = [q.model_dump() for q in parsed.qaHighlights]
        card["guidance"] = parsed.guidance
        card["_capex"] = [c.model_dump() for c in parsed.capex]
    return card


def _make_missing_card(quarter_label: str) -> dict:
    """Deterministic missing card — zero LLM calls."""
    return {
        "period": quarter_label,
        "badge": "missing",
        "link": None,
        "events": [],
        "qaHighlights": [],
        "bullets": [],
        "guidance": None,
    }


def _short_quarter(label: str) -> str:
    """Strip month range suffix: 'Q3 FY26 (Oct–Dec 2025)' → 'Q3 FY26'."""
    return label.split(" (")[0].strip()


def _transcript_to_quarter(date_str: str, quarter_end_dates: dict[str, date]) -> str | None:
    """Map a transcript date to the most recent quarter that ended before it (within 140 days).

    Uses quarter-end dates directly instead of a fixed offset heuristic, so Q4 concalls
    held 13+ weeks after quarter-end (e.g. June for Mar quarter) are mapped correctly.
    """
    try:
        td = datetime.strptime(date_str.split()[0], "%d-%b-%Y").date()
    except Exception:
        return None
    best_label: str | None = None
    best_end: date | None = None
    for label, q_end in quarter_end_dates.items():
        if q_end < td:
            days_after = (td - q_end).days
            if days_after <= 140 and (best_end is None or q_end > best_end):
                best_label = label
                best_end = q_end
    return best_label


def _mainboard_flow(company_name: str, symbol: str, transcripts: list[dict]) -> dict[str, Any]:
    """Per-transcript extraction for mainboard companies."""
    quarters = _last_8_quarters()  # newest first, e.g. "Q3 FY26 (Oct–Dec 2025)"

    # Build quarter-end date map: short_label ("Q4 FY25") → end date (2025-03-31)
    # get_last_n_quarters returns (period_key, label) oldest-first; label is short form.
    quarter_end_dates: dict[str, date] = {}
    for period_key, label in get_last_n_quarters(8):
        try:
            quarter_end_dates[label] = date.fromisoformat(period_key)
        except Exception:
            pass

    # Map each transcript to a quarter using end-date proximity (no fixed offset).
    transcript_map: dict[str, dict] = {}  # short_label → transcript (first match wins)
    for t in transcripts:
        ql = _transcript_to_quarter(t.get("date", ""), quarter_end_dates)
        if ql and ql not in transcript_map:
            transcript_map[ql] = t

    logger.info(
        "concall_evaluator: mainboard per-transcript flow for %s — "
        "%d transcripts mapping to quarters: %s",
        symbol,
        len(transcripts),
        list(transcript_map.keys()),
    )

    # Build one card per quarter: extract from transcript or make missing
    cards: list[dict] = []
    for quarter_label in quarters:
        t = transcript_map.get(_short_quarter(quarter_label))
        if t:
            logger.info("concall_evaluator: extracting card for %s %s", symbol, quarter_label)
            card = _extract_single_card(company_name, quarter_label, t)
        else:
            card = _make_missing_card(quarter_label)
        cards.append(card)

    # Trim trailing missing cards (mirrors processCards() in frontend)
    while cards and cards[-1]["badge"] == "missing":
        cards.pop()

    # Collect capex across cards, remove temp key
    all_capex: list[dict] = []
    for card in cards:
        all_capex.extend(card.pop("_capex", []))

    # Summary + guidance table — one call across all extracted content
    covered_quarters = [c["period"] for c in cards if c["badge"] == "concall"]
    summary = ""
    guidance_table: dict = {}
    if covered_quarters:
        system, user = concall_summary_prompt(company_name, covered_quarters, cards)
        parsed_summary = invoke_llm_structured(
            system, user, ConcallSummaryExtraction, use_web_search=False
        )
        if parsed_summary:
            summary = parsed_summary.summary or ""
            if parsed_summary.guidance_table_rows:
                guidance_table = {
                    "headers": ["Metric"] + covered_quarters,
                    "rows": [r.model_dump() for r in parsed_summary.guidance_table_rows],
                }

    data: dict = {
        "sectionTitle": "Concall Evaluation",
        "type": "mainboard_concall",
        "summary": summary,
        "cards": cards,
        "capex": all_capex,
        "guidanceTable": guidance_table,
        "noConcallAlerts": [],
    }

    if not _validate_concall_shape(data):
        logger.warning("concall_evaluator: mainboard shape validation failed for %s", symbol)

    # Build concall_evaluation plain-text for state
    parts = [summary]
    for card in cards[:3]:
        if card.get("badge") == "concall" and card.get("bullets"):
            parts.append(f"{card['period']}: {' '.join(card['bullets'][:2])}")
    concall_text = "\n\n".join(p for p in parts if p).strip() or "Concall analysis complete."

    logger.info(
        "concall_evaluator: mainboard done for %s — %d cards (%d concall, %d missing)",
        symbol,
        len(cards),
        sum(1 for c in cards if c["badge"] == "concall"),
        sum(1 for c in cards if c["badge"] == "missing"),
    )

    return data, concall_text


def concall_evaluator(state: ResearchState) -> dict[str, Any]:
    """Fetch NSE transcripts, extract PDF text, analyse with LLM."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("concall_evaluator: starting for %s (%s)", symbol, exchange)

    # Load transcripts from DB cache (populated by refresh_transcript_cache before pipeline)
    transcripts: list[dict] = []
    try:
        transcripts = get_transcripts_from_db(symbol, exchange)
        if transcripts:
            logger.info(
                "concall_evaluator: got %d transcripts from DB (segment=%s)",
                len(transcripts), transcripts[0].get("segment", "?"),
            )
        else:
            logger.warning("concall_evaluator: no DB transcripts for %s", symbol)
    except Exception as e:
        logger.warning("concall_evaluator: DB read failed (%s)", e)

    is_sme = any(t.get("segment") == "sme" for t in transcripts)

    concall_structured = None
    concall_evaluation = ""

    if not transcripts:
        # No concalls — fetch order wins / PPTs and use company_updates_prompt
        logger.info("concall_evaluator: no transcripts — fetching company updates for %s", symbol)
        updates_data = fetch_company_updates_data(symbol)
        system, user = company_updates_prompt(company_name, symbol, exchange, updates_data)
        logger.info(
            "concall_evaluator: company_updates_prompt (ppt=%d orders=%d press=%d)",
            len(updates_data.get("ppt_links") or []),
            len(updates_data.get("order_items") or []),
            len(updates_data.get("press_items") or []),
        )
        raw = invoke_llm(system, user, use_web_search=True)
        if raw:
            stripped = _strip_json_preamble(raw)
            try:
                data = json.loads(stripped)
                if _validate_concall_shape(data):
                    concall_structured = data
                    parts = [data.get("noConcallMessage") or "No concalls held in last 8 quarters"]
                    for section_key in ("orderBook", "pressReleases"):
                        for bullet in (data.get(section_key, {}).get("bullets") or [])[:2]:
                            parts.append(bullet)
                    concall_evaluation = "\n\n".join(p for p in parts if p).strip()
                    logger.info("concall_evaluator: done, type=no_concall_updates")
                else:
                    logger.warning("concall_evaluator: no_concall shape validation failed")
            except json.JSONDecodeError as e:
                logger.warning("concall_evaluator: JSON parse failed: %s", e)

    elif is_sme:
        # SME: keep existing single-call flow unchanged
        logger.info("concall_evaluator: SME single-call flow for %s", symbol)
        system, user = concall_structured_prompt(
            company_name, symbol, exchange, transcripts=transcripts,
        )
        raw = invoke_llm(system, user, use_web_search=True)
        if raw:
            stripped = _strip_json_preamble(raw)
            try:
                data = json.loads(stripped)
                if _validate_concall_shape(data):
                    concall_structured = data
                    parts = [data.get("summary") or ""]
                    if data.get("summaryBar", {}).get("text"):
                        parts.append(data["summaryBar"]["text"])
                    for card in (data.get("cards") or [])[:3]:
                        if card.get("period") and card.get("bullets"):
                            parts.append(f"{card['period']}: {' '.join(card['bullets'][:2])}")
                    concall_evaluation = "\n\n".join(p for p in parts if p).strip() or "SME updates analyzed."
                    logger.info("concall_evaluator: SME done, cards=%d", len(data.get("cards", [])))
                else:
                    logger.warning("concall_evaluator: SME shape validation failed")
            except json.JSONDecodeError as e:
                logger.warning("concall_evaluator: SME JSON parse failed: %s", e)

    else:
        # Mainboard: per-transcript extraction (new flow)
        concall_structured, concall_evaluation = _mainboard_flow(company_name, symbol, transcripts)

    # Build transcript links list for state (date + link only — no raw text)
    transcript_links = [
        {"date": t["date"], "link": t["link"], "description": t.get("description", "")}
        for t in transcripts
        if t.get("link")
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
