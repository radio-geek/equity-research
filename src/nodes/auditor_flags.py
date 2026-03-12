"""Auditor flags node: surfaces qualification, emphasis of matter, going concern, CARO observations."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.state import ResearchState

from .prompts import auditor_flags_prompt, invoke_llm

logger = logging.getLogger(__name__)


def _strip_json_fences(text: str) -> str:
    """Strip optional code fences and leading/trailing junk from LLM JSON output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


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


def _sort_events_desc(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort events by date descending (latest first). Mutates and returns the same list."""
    for e in events:
        e["_sort_key"] = _normalize_event_date(e)
    events.sort(key=lambda e: e["_sort_key"], reverse=True)
    for e in events:
        e.pop("_sort_key", None)
    return events


def auditor_flags(state: ResearchState) -> dict[str, Any]:
    """Search for auditor qualifications; return structured timeline (summary + events) and summary string."""
    company_name = state.get("company_name") or state.get("symbol") or ""
    symbol = state.get("symbol") or ""
    exchange = state.get("exchange") or "NSE"

    logger.info("auditor_flags: starting for %s (%s)", symbol, exchange)

    system, user = auditor_flags_prompt(company_name, symbol, exchange)

    logger.debug("auditor_flags: invoking LLM with web search")
    raw = invoke_llm(system, user, use_web_search=True)
    logger.debug("auditor_flags: raw LLM output length=%d chars", len(raw))

    raw = _strip_json_fences(raw)
    summary = ""
    events: list[dict[str, Any]] = []

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            summary = (data.get("summary") or "").strip()
            raw_events = data.get("events")
            if isinstance(raw_events, list):
                events = [e for e in raw_events if isinstance(e, dict)]
                events = _sort_events_desc(events)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("auditor_flags: JSON parse failed, using fallback summary: %s", e)
        summary = "Auditor report data could not be parsed; raw response may be in report."
        if raw and len(raw) < 2000:
            summary = raw[:1500].strip()

    if not summary and events:
        summary = f"{len(events)} audit-related event(s) in the last 5 years."
    if not summary:
        summary = "No auditor qualifications or events found in the last 5 years."

    logger.info("auditor_flags: done, summary=%s, events=%d", summary[:60], len(events))
    return {
        "auditor_flags": summary,
        "auditor_flags_structured": {"summary": summary, "events": events},
    }
