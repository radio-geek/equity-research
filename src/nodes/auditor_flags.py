"""Auditor flags node: surfaces qualification, emphasis of matter, going concern, CARO observations."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.data.screener_annual_report import fetch_governance_excerpt_from_latest_screener_ar
from src.state import ResearchState

from .prompts import (
    auditor_flags_from_annual_report_prompt,
    auditor_flags_prompt,
    invoke_llm_structured,
)
from .schemas import AuditorFlagsStructured, AuditorEvent

logger = logging.getLogger(__name__)


def _normalize_event_date(event: dict[str, Any]) -> str:
    """Ensure event has a sortable date string (YYYY-MM). Derive from fy if date missing or year-only."""
    date_val = event.get("date") or ""
    fy_val = event.get("fy") or ""
    if re.match(r"^\d{4}-\d{2}$", date_val):
        return date_val
    if re.match(r"^\d{4}$", date_val):
        return f"{date_val}-03"
    if fy_val and re.match(r"^FY\d{2}$", fy_val, re.IGNORECASE):
        yy = fy_val[-2:]
        y = 2000 + int(yy) if int(yy) < 50 else 1900 + int(yy)
        return f"{y}-03"
    return "0000-01"


def _signal_rank(event: dict[str, Any]) -> int:
    """Lower = show first (red before yellow before green)."""
    sig = (event.get("signal") or "").strip().lower()
    if sig == "red":
        return 0
    if sig == "yellow":
        return 1
    if sig == "green":
        return 2
    return 1


def _sort_events_for_display(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable sort: primary signal (red first), then date descending within tier."""
    for e in events:
        e["_sort_key"] = _normalize_event_date(e)
    events.sort(key=lambda e: e["_sort_key"], reverse=True)
    events.sort(key=_signal_rank)
    for e in events:
        e.pop("_sort_key", None)
    return events


def _event_to_dict(e: AuditorEvent) -> dict[str, Any]:
    """Convert Pydantic event to dict for sorting and report payload."""
    return {
        "date": e.date,
        "fy": e.fy,
        "category": e.category,
        "type": e.type,
        "signal": e.signal,
        "issue": e.issue,
        "evidence": e.evidence,
        "status": e.status,
    }


def auditor_flags(state: ResearchState) -> dict[str, Any]:
    """Search for auditor qualifications; return structured timeline (summary + events) and summary string."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("auditor_flags: starting for %s (%s)", symbol, exchange)

    parsed = None
    ar_bundle = fetch_governance_excerpt_from_latest_screener_ar(symbol)
    if ar_bundle and (ar_bundle.get("excerpt") or "").strip():
        logger.info(
            "auditor_flags: using Screener AR excerpt (%s, %d chars)",
            ar_bundle.get("fy_label"),
            ar_bundle.get("excerpt_length"),
        )
        system, user = auditor_flags_from_annual_report_prompt(
            company_name,
            symbol,
            exchange,
            ar_bundle["fy_label"],
            ar_bundle["url"],
            ar_bundle["excerpt"],
        )
        parsed = invoke_llm_structured(
            system, user, AuditorFlagsStructured, use_web_search=False
        )
        logger.debug(
            "auditor_flags: AR structured invoke returned %s", "ok" if parsed else "None"
        )

    if parsed is None:
        system, user = auditor_flags_prompt(company_name, symbol, exchange)
        logger.debug("auditor_flags: invoking LLM with web search (fallback)")
        parsed = invoke_llm_structured(
            system, user, AuditorFlagsStructured, use_web_search=True
        )
        logger.debug(
            "auditor_flags: web-search structured invoke returned %s",
            "ok" if parsed else "None",
        )

    verdict = "OK"
    summary = ""
    events: list[dict[str, Any]] = []

    if parsed:
        verdict = (parsed.verdict or "OK").strip().upper()
        if verdict not in ("RISK", "OK", "GOOD"):
            verdict = "OK"
        summary = (parsed.summary or "").strip()
        events = [_event_to_dict(e) for e in parsed.events][:5]
        events = _sort_events_for_display(events)

    if not summary and events:
        summary = f"{len(events)} audit-related event(s) in the last 5 years."
    if not summary:
        summary = "No auditor qualifications or events found in the last 5 years."

    logger.info("auditor_flags: done, verdict=%s, events=%d", verdict, len(events))
    return {
        "auditor_flags": summary,
        "auditor_flags_structured": {"verdict": verdict, "summary": summary, "events": events},
    }
