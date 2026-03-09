"""Concall transcript fetching from NSE corporate announcements + PDF text extraction.

Public API:
  get_concall_transcripts()   — original: fetch live from NSE (kept as fallback)
  refresh_transcript_cache()  — call before pipeline: update DB if needed, return True if stale
  get_transcripts_from_db()   — call inside pipeline: read from DB cache
"""

from __future__ import annotations

import io
import logging
from typing import Any

import requests

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

_NSE_ANNOUNCEMENTS_URL = (
    "https://www.nseindia.com/api/corporate-announcements"
    "?index={index}&symbol={symbol}"
)
_NSE_WARMUP_URL = (
    "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
)
_NSE_SEGMENTS = ["equities", "sme"]

# Max chars extracted per PDF to stay within LLM context window
_MAX_CHARS_PER_PDF = 8000


def _make_session() -> requests.Session:
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


def _fetch_announcement_list(session: requests.Session, symbol: str) -> tuple[list, str]:
    """Try equities then sme segment; return (announcements, segment)."""
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


def fetch_transcript_links(symbol: str, limit: int = 8) -> tuple[list[dict], str]:
    """
    Fetch up to `limit` concall transcript links from NSE for the given symbol.
    Returns (transcripts, segment) where segment is 'equities' or 'sme'.
    Each transcript: {date, link, description}
    """
    symbol = symbol.strip().upper()
    session = _make_session()

    try:
        session.get(_NSE_WARMUP_URL, timeout=10)
    except Exception:
        pass

    announcements, segment = _fetch_announcement_list(session, symbol)
    if not announcements:
        log.warning("concall: no NSE announcements found for %s", symbol)
        return [], ""

    transcripts = []
    for item in announcements:
        desc = (item.get("desc") or "").lower()
        text = (item.get("attchmntText") or "").lower()
        if any(kw in desc or kw in text for kw in _KEYWORDS):
            link = item.get("attchmntFile", "")
            transcripts.append({
                "date": item.get("an_dt", ""),
                "link": link,
                "description": (item.get("attchmntText") or "").strip(),
            })
        if len(transcripts) >= limit:
            break

    return transcripts, segment


def _extract_text_from_pdf_bytes(content: bytes, source: str = "") -> str:
    """Extract plain text from PDF bytes. Returns '' on failure."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages_text).strip()[:_MAX_CHARS_PER_PDF]
    except Exception as e:
        log.warning("concall: PDF extraction failed for %s: %s", source, e)
        return ""


def _extract_text_from_zip_bytes(content: bytes, source: str = "") -> str:
    """Extract and concatenate text from all PDFs inside a ZIP archive."""
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            pdf_names = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
            if not pdf_names:
                log.warning("concall: ZIP contains no PDFs: %s", source)
                return ""
            texts = []
            for name in pdf_names:
                with zf.open(name) as f:
                    text = _extract_text_from_pdf_bytes(f.read(), f"{source}/{name}")
                if text:
                    texts.append(text)
            combined = "\n\n".join(texts)
            return combined[:_MAX_CHARS_PER_PDF]
    except Exception as e:
        log.warning("concall: ZIP extraction failed for %s: %s", source, e)
        return ""


def _extract_pdf_text(link: str, session: requests.Session) -> str:
    """Download a PDF or ZIP from NSE and extract plain text. Returns '' on failure."""
    try:
        resp = session.get(link, timeout=30)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        log.warning("concall: failed to download %s: %s", link, e)
        return ""

    if link.lower().endswith(".zip"):
        return _extract_text_from_zip_bytes(content, link)
    return _extract_text_from_pdf_bytes(content, link)


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
