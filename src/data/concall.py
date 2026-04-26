"""Concall transcript fetching from NSE corporate announcements + PDF text extraction.

Public API:
  get_concall_transcripts()   — original: fetch live from NSE (kept as fallback)
  refresh_transcript_cache()  — call before pipeline: update DB if needed, return True if stale
  get_transcripts_from_db()   — call inside pipeline: read from DB cache
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

from src.data.pdf_text import download_and_extract_text, resolve_pdf_url

log = logging.getLogger(__name__)

_KEYWORDS = [
    "transcript",
    "concall",
    "con call",
    "earnings call",
    "investor call",
    "conference call",
    "audio and transcript",
]

# Entries matching these are not actual transcripts — skip them
_EXCLUDE_KEYWORDS = [
    "intimation of",
    "notice of conference",
    "scheduled to be held",
    "link of audio",
    "audio link",
    "audio recording",
    "prior to",
]

_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _normalize_date(date_str: str) -> str:
    """Normalise NSE date string (DD-Mon-YYYY HH:MM:SS) to YYYY-MM-DD HH:MM:SS.

    Preserving time is important for same-day deduplication: the resubmission
    (later timestamp, larger PDF) should win over the earlier cover letter.
    """
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})(?:\s+(\d{2}:\d{2}:\d{2}))?", date_str.strip())
    if m:
        d = m.group(1).zfill(2)
        mon = _MONTH_MAP.get(m.group(2).lower(), "00")
        y = m.group(3)
        t = m.group(4) or "00:00:00"
        return f"{y}-{mon}-{d} {t}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if m:
        return m.group(0) + " 00:00:00"
    return date_str


def _iso_week(date_str: str) -> str:
    """Return YYYY-WW string for grouping entries from the same concall event."""
    from datetime import date
    nd = _normalize_date(date_str)[:10]  # take YYYY-MM-DD portion only
    try:
        d = date.fromisoformat(nd)
        iso = d.isocalendar()
        return f"{iso[0]}-{iso[1]:02d}"
    except ValueError:
        return nd

_SCREENER_CONCALL_URL = "https://www.screener.in/company/{symbol}/"

# NSE announcements (used for order wins / press releases when no concalls found)
_NSE_ANNOUNCEMENTS_URL = (
    "https://www.nseindia.com/api/corporate-announcements"
    "?index={index}&symbol={symbol}"
)
_NSE_WARMUP_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
_NSE_SEGMENTS = ["equities", "sme"]

_ORDER_KEYWORDS = [
    "award of order", "receipt of order", "new order", "work order",
    "order bagged", "order received", "order win", "contract awarded",
    "letter of intent", "loi ", "procurement order", "supply order",
    "new business", "new contract",
]
_PRESS_KEYWORDS = [
    "press release", "company update", "investor update",
    "business update", "operational update", "investor presentation",
]

# Max chars extracted per PDF to stay within LLM context window
_MAX_CHARS_PER_PDF = 20000


def _make_session() -> requests.Session:
    """Screener-optimised session (HTML accept headers)."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.bseindia.com/",
    })
    return s


def _make_nse_session() -> requests.Session:
    """NSE-optimised session (JSON accept headers + NSE referer)."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
    })
    return s


def _fetch_nse_announcements(session: requests.Session, symbol: str) -> tuple[list, str]:
    """Try equities then sme; return (announcements, segment)."""
    for index in _NSE_SEGMENTS:
        url = _NSE_ANNOUNCEMENTS_URL.format(index=index, symbol=symbol)
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data:
                return data, index
        except Exception:
            continue
    return [], ""


def _screener_period_to_date(period: str) -> str:
    """Convert Screener period label (e.g. 'Feb 2026') to '01-Feb-2026 00:00:00'."""
    parts = period.strip().split()
    if len(parts) == 2:
        return f"01-{parts[0]}-{parts[1]} 00:00:00"
    return f"01-Jan-2000 00:00:00"


def fetch_transcript_links(symbol: str, limit: int = 8) -> tuple[list[dict], str]:
    """
    Fetch up to `limit` concall transcript links from Screener.in for the given symbol.
    Returns (transcripts, segment) where segment is 'equities' or 'sme'.
    Each transcript: {date, link, description}
    """
    from bs4 import BeautifulSoup

    symbol = symbol.strip().upper()
    url = _SCREENER_CONCALL_URL.format(symbol=symbol)
    session = _make_session()

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        log.warning("concall: Screener fetch failed for %s: %s", symbol, e)
        return [], ""

    soup = BeautifulSoup(resp.text, "lxml")

    # Locate div.documents.concalls → ul.list-links
    container = soup.find("div", class_="concalls")
    if not container:
        log.warning("concall: no concall section on Screener for %s", symbol)
        return [], ""

    items = container.select("ul.list-links li")
    results = []
    for li in items:
        # Period label: e.g. "Feb 2026"
        period_div = li.find("div", class_=lambda c: c and "ink-600" in c)
        period = period_div.get_text(strip=True) if period_div else ""

        # Transcript link: <a title="Raw Transcript"> only
        transcript_a = li.find("a", title="Raw Transcript")
        if not transcript_a:
            continue

        href = transcript_a.get("href", "").strip()
        if not href:
            continue

        href = resolve_pdf_url(href)
        date_str = _screener_period_to_date(period)

        results.append({
            "date": date_str,
            "link": href,
            "description": f"Concall Transcript - {period}",
        })

        if len(results) >= limit:
            break

    # Screener lists newest first — sort just to be safe
    results.sort(key=lambda t: _normalize_date(t["date"]), reverse=True)

    # Segment detection: not available from Screener; default to equities
    segment = "equities"

    log.info("concall: %s — Screener returned %d transcripts", symbol, len(results))
    return results, segment


def fetch_company_updates_data(symbol: str) -> dict[str, list]:
    """Fetch PPT links (Screener) + order wins / press releases (NSE) for companies with no concalls.

    Returns:
      {
        "ppt_links":    [{period, link, description}, ...],   # up to 4
        "order_items":  [{date, description, link}, ...],     # up to 10
        "press_items":  [{date, description, link}, ...],     # up to 10
      }
    """
    from bs4 import BeautifulSoup

    sym = symbol.strip().upper()
    result: dict[str, list] = {"ppt_links": [], "order_items": [], "press_items": []}

    # --- PPT links from Screener concall list ---
    try:
        session = _make_session()
        resp = session.get(_SCREENER_CONCALL_URL.format(symbol=sym), timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        container = soup.find("div", class_="concalls")
        if container:
            for li in container.select("ul.list-links li")[:8]:
                period_div = li.find("div", class_=lambda c: c and "ink-600" in c)
                period = period_div.get_text(strip=True) if period_div else ""
                ppt_a = next(
                    (a for a in li.find_all("a", class_="concall-link")
                     if a.get_text(strip=True).lower() == "ppt"),
                    None,
                )
                if ppt_a and period:
                    href = ppt_a.get("href", "").strip()
                    if href:
                        result["ppt_links"].append({
                            "period": period,
                            "link": href,
                            "description": f"Investor Presentation — {period}",
                        })
                if len(result["ppt_links"]) >= 4:
                    break
    except Exception as e:
        log.debug("concall: Screener PPT fetch failed for %s: %s", sym, e)

    # --- Orders + press releases from NSE announcements ---
    nse_session = _make_nse_session()
    try:
        nse_session.get(_NSE_WARMUP_URL, timeout=10)
    except Exception:
        pass

    try:
        announcements, _ = _fetch_nse_announcements(nse_session, sym)
        for item in announcements:
            cat = (item.get("desc") or "").lower()
            txt = (item.get("attchmntText") or "").lower()
            combined = cat + " " + txt
            entry = {
                "date": item.get("an_dt", ""),
                "description": (item.get("attchmntText") or "").strip(),
                "link": item.get("attchmntFile", ""),
            }
            if len(result["order_items"]) < 10 and any(kw in combined for kw in _ORDER_KEYWORDS):
                result["order_items"].append(entry)
            elif len(result["press_items"]) < 10 and any(kw in combined for kw in _PRESS_KEYWORDS):
                result["press_items"].append(entry)
            if len(result["order_items"]) >= 10 and len(result["press_items"]) >= 10:
                break
    except Exception as e:
        log.debug("concall: NSE updates fetch failed for %s: %s", sym, e)

    log.info(
        "concall: %s updates — ppt=%d orders=%d press=%d",
        sym, len(result["ppt_links"]), len(result["order_items"]), len(result["press_items"]),
    )
    return result


def _extract_pdf_text(link: str, session: requests.Session) -> str:
    """Download a PDF or ZIP and extract plain text (concall cap). Returns '' on failure."""
    return download_and_extract_text(
        link,
        session,
        max_pdf_chars=_MAX_CHARS_PER_PDF,
        max_zip_per_pdf=_MAX_CHARS_PER_PDF,
        max_zip_total=_MAX_CHARS_PER_PDF,
        timeout=30,
    )


def get_concall_transcripts(symbol: str, exchange: str = "NSE", limit: int = 8) -> list[dict[str, Any]]:
    """
    Fetch transcript links from NSE and extract text from each PDF.
    Returns list of {date, link, description, text} sorted newest first.
    Falls back to empty list if NSE is unreachable.
    """
    links, segment = fetch_transcript_links(symbol, limit)
    if not links:
        return []

    session = _make_session()
    results = []
    for entry in links:
        text = _extract_pdf_text(entry["link"], session)
        results.append({
            "date": entry["date"],
            "link": entry["link"],
            "description": entry["description"],
            "text": text,
            "segment": segment,
        })
        log.info(
            "concall: fetched %s (segment=%s, chars=%d)",
            entry["date"], segment, len(text),
        )

    return results


# ---------------------------------------------------------------------------
# DB-backed transcript cache (used by the report pipeline)
# ---------------------------------------------------------------------------

def refresh_transcript_cache(symbol: str, exchange: str = "NSE", limit: int = 8) -> bool:
    """Ensure DB has fresh transcripts for symbol. Returns True if new/updated transcripts stored.

    Steps:
      1. Load what's in DB.
      2. Retry PDF extraction for any row where text is NULL/empty (Gap 4).
      3. Ask NSE for the latest transcript date only (1 fast API call, no PDF download).
         - If NSE is unreachable: use DB as-is, return result of step 2 (Gap 2).
      4. If DB is empty OR NSE has a newer transcript: full scrape → upsert → trim to limit.
      5. Return True if anything changed (report must be regenerated).
    """
    from backend.transcript_store import (
        get_stored_transcripts,
        get_latest_stored_date,
        update_transcript_text,
        upsert_transcript,
        trim_to_limit,
    )

    sym = symbol.strip().upper()
    exch = exchange.strip().upper()
    any_updated = False

    # Step 1 — load DB
    stored = get_stored_transcripts(sym, exch)

    # Step 1b — short-circuit: if transcripts were stored very recently, skip the live Screener
    # freshness check entirely (concalls are quarterly; nothing will have changed in 6h).
    # This makes repeat searches complete in ~1s instead of ~5s.
    _FRESHNESS_SKIP_HOURS = 24 * 10  # 10 days
    if stored and not any(not r.get("text") for r in stored):
        from datetime import datetime, timezone, timedelta
        from backend.transcript_store import get_latest_stored_at
        latest_at = get_latest_stored_at(sym, exch)
        if latest_at and (datetime.now(timezone.utc) - latest_at) < timedelta(hours=_FRESHNESS_SKIP_HOURS):
            log.info(
                "concall: DB fresh enough for %s (stored %s ago < %dh) — skipping Screener check",
                sym, datetime.now(timezone.utc) - latest_at, _FRESHNESS_SKIP_HOURS,
            )
            return False  # no updates → caller will use cached report

    # Step 2 — retry failed PDF extractions only if there are empty-text rows (Gap 3 + Gap 4)
    failed_rows = [r for r in stored if not r.get("text")] if stored else []
    if failed_rows:
        retry_session = _make_session()
        for row in failed_rows:
            new_text = _extract_pdf_text(row["link"], retry_session)
            if new_text:
                log.info("concall: retry succeeded for %s %s", sym, row["transcript_date"])
                update_transcript_text(sym, exch, row["transcript_date"], new_text)
                any_updated = True
            else:
                log.debug("concall: retry still failed for %s %s", sym, row["transcript_date"])

    # Step 3 — NSE freshness check: fetch limit=8 links upfront so Step 4 can reuse them
    # (Gap 2: avoids a second NSE API call; Gap 2: all exceptions caught → fall back to DB)
    try:
        all_links, segment = fetch_transcript_links(sym, limit=limit)
    except Exception as e:
        log.warning("concall: NSE freshness check failed for %s (%s) — using DB as-is", sym, e)
        return any_updated

    if not all_links:
        log.warning("concall: NSE returned no transcripts for %s — using DB as-is", sym)
        return any_updated

    latest_nse_date = all_links[0]["date"]
    latest_db_date = get_latest_stored_date(sym, exch)

    if stored and latest_db_date == latest_nse_date:
        log.info("concall: DB is up to date for %s (latest=%s)", sym, latest_db_date)
        return any_updated

    # Step 4 — DB empty or new transcript found: full scrape using already-fetched links
    log.info(
        "concall: DB stale for %s (db=%s, nse=%s) — full scrape",
        sym, latest_db_date, latest_nse_date,
    )
    session = _make_session()
    for entry in all_links:
        text = _extract_pdf_text(entry["link"], session)
        upsert_transcript(
            sym, exch, segment,
            entry["date"], entry["link"], entry["description"],
            text or None,  # None = retry next time (Gap 4)
        )
        log.info("concall: stored %s (segment=%s, chars=%d)", entry["date"], segment, len(text or ""))

    trim_to_limit(sym, exch, limit)
    return True


def get_transcripts_from_db(symbol: str, exchange: str = "NSE") -> list[dict[str, Any]]:
    """Read cached transcripts from DB. Called inside the pipeline after refresh_transcript_cache().

    Returns same shape as get_concall_transcripts(): [{date, link, description, text, segment}].
    """
    from backend.transcript_store import get_stored_transcripts
    rows = get_stored_transcripts(symbol.strip().upper(), exchange.strip().upper())
    # Normalise key name: DB uses 'transcript_date', pipeline expects 'date'
    return [
        {
            "date": r["transcript_date"],
            "link": r["link"],
            "description": r.get("description") or "",
            "text": r.get("text") or "",
            "segment": r.get("segment") or "equities",
        }
        for r in rows
    ]
