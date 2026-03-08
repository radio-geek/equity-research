"""Concall transcript fetching from NSE corporate announcements + PDF text extraction."""

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
            # Skip ZIP files (video/audio recordings — not readable text)
            if link.lower().endswith(".zip"):
                log.info("concall: skipping zip file %s", link)
                continue
            transcripts.append({
                "date": item.get("an_dt", ""),
                "link": link,
                "description": (item.get("attchmntText") or "").strip(),
            })
        if len(transcripts) >= limit:
            break

    return transcripts, segment


def _extract_pdf_text(link: str, session: requests.Session) -> str:
    """Download a PDF from NSE archives and extract plain text. Returns '' on failure."""
    try:
        resp = session.get(link, timeout=30)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        log.warning("concall: failed to download %s: %s", link, e)
        return ""

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        text = "\n".join(pages_text).strip()
        return text[:_MAX_CHARS_PER_PDF]
    except Exception as e:
        log.warning("concall: PDF extraction failed for %s: %s", link, e)
        return ""


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
