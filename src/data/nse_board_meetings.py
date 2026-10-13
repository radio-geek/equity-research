"""NSE board-meeting intimations: fetch + attribute each meeting to a fiscal period.

Source is https://www.nseindia.com/api/corporate-board-meetings via the nse package's
boardMeetings(), which serves both forthcoming and historical date windows, market-wide.

Attributing a meeting to the period it reports is the hard part. The free-text bm_desc is too
variable to parse as the primary mechanism (a naive regex matches well under half the rows;
real examples that defeat keyword anchoring include "for the period ended September 30, 2025"
and "for the quarter and year ended March 31, 2025"). So the period is derived from the meeting
DATE by quarter-end proximity, and the text is used only to refine and to set period_type.

All parsing of the NSE row shape lives in this module so a future endpoint change is contained.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any

from nse import NSE

from src.config import get_nse_download_folder
from src.data.nse_client import _MAX_RETRIES, _rate_limit

logger = logging.getLogger(__name__)

SEGMENTS = ("equities", "sme")

# Proximity window, matching the rule already used by concall_evaluator._transcript_to_quarter.
# Quarter-ends are ~92 days apart, so at most one candidate normally qualifies.
_PROXIMITY_WINDOW_DAYS = 140

# SEBI Reg 33: 45 days quarterly / 60 days annual. These are those plus slack, and they are
# deliberately tight -- a loose bound admits a period attributed a full year wrong, which would
# silently make the YoY peer the current period. Mirrored by ed_lag_sane in migration 008.
_MAX_LAG_DAYS = 180
_MAX_LAG_DAYS_ANNUAL = 210

_QUARTER_END_MONTH_DAY = ((3, 31), (6, 30), (9, 30), (12, 31))

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Anchored on the word "ended" rather than on "quarter"/"half yearly", because the period noun
# varies far more than the verb does. Handles both "30th June, 2025" and "September 30, 2025".
_PERIOD_END_RE = re.compile(
    r"""
    # The -ly forms are essential: "Quarterly ended June 2026" is a very common phrasing, and
    # a bare `quarter` alternative matches "Quarter" then fails on the "ly", so the whole match
    # fails and the row falls back to proximity -- silently attributing it to the wrong quarter.
    (?:period|quarter(?:ly)?|half[\s-]?year(?:ly)?|year(?:ly)?|nine[\s-]months?
      |six[\s-]months?|three[\s-]months?)
    (?:\s+and\s+(?:year|half[\s-]?year|nine[\s-]months?))?
    \s+end(?:ed|ing)\s*(?:on\s+)?
    (?:(?P<d1>\d{1,2})(?:st|nd|rd|th)?\s+)?
    (?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*
    \s*,?\s*
    (?:(?P<d2>\d{1,2})\s*,?\s*)?
    (?P<yr>(?:19|20)\d{2})
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RESULTS_KEYWORDS = (
    "financial result",
    "financial results",
    "quarterly result",
    "unaudited",
    "audited",
)

_RESULTS_RE = re.compile(
    r"(?:un)?audited\s+(?:standalone|consolidated|financial)|financial\s+results"
    r"|quarterly\s+results",
    re.IGNORECASE,
)


# ── fetching ──────────────────────────────────────────────────────────────────────

def fetch_board_meetings(
    from_date: date,
    to_date: date,
    segments: tuple[str, ...] = SEGMENTS,
) -> list[dict[str, Any]]:
    """Fetch board-meeting intimations for a date window across the given NSE segments.

    Returns raw NSE rows with a 'segment' key added. Both dates must be supplied: the nse
    package ignores the range unless from_date and to_date are both present.
    """
    folder = str(get_nse_download_folder())
    out: list[dict[str, Any]] = []
    for segment in segments:
        rows = _fetch_segment(folder, segment, from_date, to_date)
        for row in rows:
            if isinstance(row, dict):
                row = dict(row)
                row["segment"] = segment
                out.append(row)
    logger.info(
        "board_meetings: fetched %d rows for %s..%s", len(out), from_date, to_date
    )
    return out


def _fetch_segment(
    folder: str, segment: str, from_date: date, to_date: date
) -> list[dict[str, Any]]:
    """One segment, with the shared NSE throttle and the same retry budget as nse_client."""
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            with NSE(folder, server=False) as nse:
                _rate_limit()
                return nse.boardMeetings(
                    index=segment,
                    from_date=datetime.combine(from_date, datetime.min.time()),
                    to_date=datetime.combine(to_date, datetime.min.time()),
                )
        except (TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(1.0)
        except Exception as e:  # noqa: BLE001 - one bad segment must not kill the run
            logger.warning("board_meetings: %s segment failed: %s", segment, e)
            return []
    logger.warning("board_meetings: %s segment failed after retries: %s", segment, last_err)
    return []


# ── row parsing ───────────────────────────────────────────────────────────────────

def parse_nse_date(value: str | None) -> date | None:
    """Parse '12-Oct-2026' (optionally with a trailing time) to a date."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value).split()[0], "%d-%b-%Y").date()
    except (ValueError, IndexError):
        return None


def parse_nse_timestamp(value: str | None) -> datetime | None:
    """Parse '01-Oct-2026 12:37:30' to a naive datetime.

    NSE sends no timezone; the value is IST wall clock and is stored as such (see the
    announced_at column comment in migration 008).
    """
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def is_results_meeting(purpose: str | None, description: str | None) -> bool:
    """True if this board meeting is about financial results.

    The gate matters: 'Fund Raising' and 'Other business matters' meetings are not earnings
    events, and if they were allowed to claim a (symbol, period_end) slot they would block the
    real financial-results intimation for that quarter. A company can file both for one meeting.
    """
    p = (purpose or "").lower()
    if "financial result" in p:
        return True
    # 'Board Meeting Intimation' is a generic label covering roughly half the feed; its real
    # subject is only in the free text.
    if "board meeting intimation" in p or not p:
        return bool(_RESULTS_RE.search(description or ""))
    return False


# ── period attribution ────────────────────────────────────────────────────────────

def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _quarter_ends_before(d: date) -> list[date]:
    """Legal Indian quarter-ends strictly before d, nearest-last."""
    out: list[date] = []
    for year in (d.year - 2, d.year - 1, d.year):
        for month, day in _QUARTER_END_MONTH_DAY:
            qe = date(year, month, day)
            if qe < d:
                out.append(qe)
    return sorted(out)


def _proximity_period_end(results_date: date) -> date | None:
    """Most recent legal quarter-end strictly before results_date, within the window.

    This generalizes concall_evaluator._transcript_to_quarter, which draws its candidates from
    get_last_n_quarters() relative to now() and so silently breaks on backfills. Candidates here
    are derived from results_date itself.
    """
    candidates = [
        qe
        for qe in _quarter_ends_before(results_date)
        if (results_date - qe).days <= _PROXIMITY_WINDOW_DAYS
    ]
    return max(candidates) if candidates else None


def _text_period_end(description: str | None) -> date | None:
    """Period end stated explicitly in the text, if it resolves to a legal quarter-end."""
    if not description:
        return None
    m = _PERIOD_END_RE.search(description)
    if not m:
        return None
    month = _MONTHS.get(m.group("mon").lower()[:3])
    if month is None or month not in (3, 6, 9, 12):
        # Non-quarter-end month: the filing is describing something else. Fall back to proximity.
        return None
    try:
        year = int(m.group("yr"))
    except (TypeError, ValueError):
        return None
    return _month_end(year, month)


def _detect_period_type(description: str | None) -> tuple[str | None, bool]:
    """Return (period_type, covers_full_year) from the text, or (None, False) if unclear.

    'quarter' dominates, and that is the whole trick. Indian quarterly filers routinely report
    cumulative figures in the same filing -- "the quarter and half year ended September 30",
    "the quarter and year ended March 31" -- so a filing that mentions a quarter at all is a
    quarterly filing, whatever else it also mentions. Testing for 'half' first instead labels
    every quarterly filer's Q2 as half-yearly, which then suppresses their QoQ comparison and
    shows up as a spurious cadence_change against the other three quarters.

    Only a filing that never mentions a quarter is genuinely H / 9M / FY.
    """
    d = (description or "").lower()
    if not d:
        return None, False

    if "quarter" in d or "three month" in d:
        # Covers the full year too when the same filing reports the annual figures.
        covers_full_year = bool(re.search(r"quarter\s+and\s+(the\s+)?(year|twelve)", d))
        return "Q", covers_full_year
    if "nine month" in d or "9 month" in d:
        return "9M", False
    if "half" in d or "six month" in d:
        return "H", False
    if "year ended" in d or "year ending" in d:
        return "FY", True
    return None, False


def _period_type_from_cadence(cadence_months: set[int] | None) -> tuple[str | None, bool]:
    """Infer period_type from the filer's own history of period-end months.

    Used for the large share of rows whose text states no period noun. Far safer than guessing
    from the month alone, because cadence is a stable property of the filer.
    """
    if not cadence_months:
        return None, False
    if {6, 12} & cadence_months:
        return "Q", False
    if cadence_months == {3, 9} or cadence_months == {9}:
        return "H", False
    if cadence_months == {3}:
        return "FY", True
    return None, False


def attribute_period(
    results_date: date,
    description: str | None,
    cadence_months: set[int] | None = None,
) -> dict[str, Any]:
    """Attribute a board meeting to the fiscal period it reports.

    cadence_months is the set of period-end months this filer has used historically (from
    earnings_date_store.get_filer_cadence). Passed in rather than queried here, to keep the
    data layer free of DB coupling.

    Returns period_end / period_type / covers_full_year / period_source / period_confidence /
    attribution_note. period_end is None when attribution failed; such rows are still real
    upcoming results and must stay on the calendar with comparisons suppressed.
    """
    prox_end = _proximity_period_end(results_date)
    text_end = _text_period_end(description)
    ptype, covers_full_year = _detect_period_type(description)

    note: str | None = None
    if ptype is None:
        ptype, covers_full_year = _period_type_from_cadence(cadence_months)
        if ptype is not None:
            note = "period_type from filer cadence"
    elif ptype in ("H", "9M") and cadence_months and ({6, 12} & cadence_months):
        # The filer demonstrably reports quarterly: only quarterly filers ever have Jun-30 or
        # Dec-31 period ends. So this filing's "half year ended" wording is the cumulative H1
        # figures reported alongside the quarter, not a half-yearly cadence.
        #
        # Text alone cannot settle this, because such a company files two intimations for one
        # meeting -- one saying "the quarter and half year ended", one saying only "the half
        # year ended" -- both parse with full confidence, so whichever was filed later would
        # otherwise win and mislabel the company.
        ptype, covers_full_year = "Q", False
        note = "period_type corrected to Q from filer cadence"

    if text_end is not None and prox_end is not None and text_end == prox_end:
        period_end, source, confidence = text_end, "text_explicit", 95
    elif text_end is not None:
        period_end, source, confidence = text_end, "text_explicit", 75
        note = _join_note(note, f"text/proximity disagree prox={prox_end}")
    elif prox_end is not None:
        period_end, source, confidence = prox_end, "proximity", 65
    else:
        return _unattributed("no quarter-end within %dd" % _PROXIMITY_WINDOW_DAYS)

    # Sanity bound. Fall back to proximity before giving up, since a bad text match is the more
    # likely culprit.
    if not _lag_ok(results_date, period_end, covers_full_year):
        if prox_end is not None and period_end != prox_end and _lag_ok(
            results_date, prox_end, covers_full_year
        ):
            period_end, source, confidence = prox_end, "proximity", 50
            note = _join_note(note, "text lag out of bounds, used proximity")
        else:
            lag = (results_date - period_end).days
            return _unattributed(f"lag {lag}d out of bounds")

    if ptype is None:
        # Period is known but cadence is not. Default to the dominant case and mark it down
        # rather than leaving period_type NULL, which the schema ties to period_end being NULL.
        ptype, covers_full_year = "Q", period_end.month == 3
        confidence = min(confidence, 40)
        note = _join_note(note, "period_type defaulted")

    return {
        "period_end": period_end,
        "period_type": ptype,
        "covers_full_year": covers_full_year,
        "period_source": source,
        "period_confidence": confidence,
        "attribution_note": note,
    }


def _lag_ok(results_date: date, period_end: date, covers_full_year: bool) -> bool:
    lag = (results_date - period_end).days
    limit = _MAX_LAG_DAYS_ANNUAL if covers_full_year else _MAX_LAG_DAYS
    return 0 < lag <= limit


def _join_note(existing: str | None, addition: str) -> str:
    return f"{existing}; {addition}" if existing else addition


def _unattributed(note: str) -> dict[str, Any]:
    return {
        "period_end": None,
        "period_type": None,
        "covers_full_year": False,
        "period_source": None,
        "period_confidence": 0,
        "attribution_note": note,
    }


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse records to one per (symbol, exchange, period_end), best attribution winning.

    Companies almost always file two rows for one meeting -- a generic 'Board Meeting Intimation'
    and a 'Financial Results' row -- so nearly every key collides. Resolving by announced_at
    alone picks the wrong row about one time in seven, and the usual failure is a half-yearly
    filer (period_type 'H', confidence 95) being overwritten by a defaulted 'Q' at confidence 40.

    Purpose specificity is NOT a usable tiebreak: in practice the generic intimation often
    carries the better text. Rank by confidence first, then recency.

    Unattributed records (period_end None) are passed through untouched -- they are keyed
    separately in the schema and each one is a distinct real event.
    """
    best: dict[tuple[str, str, date], dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for rec in records:
        period_end = rec.get("period_end")
        if period_end is None:
            passthrough.append(rec)
            continue
        key = (rec["symbol"], rec.get("exchange", "NSE"), period_end)
        current = best.get(key)
        if current is None or _rank(rec) > _rank(current):
            best[key] = rec
    return list(best.values()) + passthrough


def _rank(rec: dict[str, Any]) -> tuple[int, datetime]:
    """Sort key for picking the winning record: confidence, then recency."""
    announced = rec.get("announced_at") or datetime.combine(
        rec["bm_date"], datetime.min.time()
    )
    return (rec.get("period_confidence") or 0, announced)


def normalize_row(
    row: dict[str, Any], cadence_months: set[int] | None = None
) -> dict[str, Any] | None:
    """Turn one raw NSE board-meeting row into a storable record.

    Returns None only when the row has no usable symbol or meeting date.
    """
    symbol = (row.get("bm_symbol") or "").strip().upper()
    bm_date = parse_nse_date(row.get("bm_date"))
    if not symbol or bm_date is None:
        return None

    purpose = (row.get("bm_purpose") or "").strip()
    description = (row.get("bm_desc") or "").strip()
    is_earnings = is_results_meeting(purpose, description)

    record: dict[str, Any] = {
        "symbol": symbol,
        "exchange": "NSE",
        "segment": row.get("segment") or "equities",
        "company_name": (row.get("sm_name") or "").strip() or None,
        "isin": (row.get("sm_isin") or "").strip() or None,
        "bm_date": bm_date,
        "purpose": purpose,
        "description": description or None,
        "announced_at": parse_nse_timestamp(row.get("bm_timestamp")),
        "attachment": (row.get("attachment") or "").strip() or None,
        "is_earnings": is_earnings,
    }

    if is_earnings:
        record.update(attribute_period(bm_date, description, cadence_months))
    else:
        # Non-earnings meetings are logged but must never claim a period slot.
        record.update(_unattributed("not an earnings meeting"))

    return record
