"""Latest annual report link from Screener.in + governance-focused text excerpt for LLM."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.data.concall import _make_session
from src.data.pdf_text import download_and_extract_text, resolve_pdf_url

logger = logging.getLogger(__name__)

SCREENER_COMPANY_PAGE = "https://www.screener.in/company/{symbol}/"

# Full parse budget before keyword windowing
_MAX_FULL_EXTRACT_PDF = 2_000_000
_MAX_ZIP_PER_PDF = 500_000
_MAX_ZIP_TOTAL = 2_000_000

# Governance excerpt for LLM
_MAX_GOVERNANCE_EXCERPT = 120_000
_MIN_EXCERPT_TO_TRUST = 1_500
_SNIPPET_RADIUS = 3_500
_PREFIX_FALLBACK_CHARS = 28_000

GOVERNANCE_SNIPPET_KEYWORDS = [
    "auditor's report",
    "independent auditor's report",
    "report on the audit",
    "statutory audit",
    "caro",
    "companies auditor's report order",
    "secretarial audit report",
    "secretarial audit",
    "internal financial control",
    "internal control over financial reporting",
    "internal control with reference to financial",
    "going concern",
    "emphasis of matter",
    "qualified opinion",
    "modified disclaimer",
    "audit qualification",
    "related party transaction",
    "related party disclosures",
    "corporate governance report",
    "corporate governance",
    "management discussion and analysis",
    "risk management",
    "contingent liabilit",
    "material uncertainty",
    "material litigat",
    "fraud by",
    "whistle",
]


def _parse_fy_year_from_anchor_text(text: str) -> int | None:
    m = re.search(r"financial\s+year\s+(\d{4})", text, re.I)
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2100:
            return y
    m = re.search(r"\bfy\s*(\d{4})\b", text, re.I)
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2100:
            return y
    m = re.search(r"\b(20\d{2})\b", text)
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2100:
            return y
    return None


def _year_to_fy_label(year: int) -> str:
    return f"FY{str(year)[-2:]}"


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    out: list[tuple[int, int]] = [intervals[0]]
    for s, e in intervals[1:]:
        ps, pe = out[-1]
        if s <= pe + 1:
            out[-1] = (ps, max(pe, e))
        else:
            out.append((s, e))
    return out


def build_governance_excerpt(full_text: str, max_chars: int = _MAX_GOVERNANCE_EXCERPT) -> str:
    """Pick keyword-centered windows from annual report plain text; cap total length."""
    text = (full_text or "").strip()
    if not text:
        return ""

    lower = text.lower()
    intervals: list[tuple[int, int]] = []
    for kw in GOVERNANCE_SNIPPET_KEYWORDS:
        start = 0
        while start < len(lower):
            pos = lower.find(kw, start)
            if pos < 0:
                break
            s = max(0, pos - _SNIPPET_RADIUS)
            e = min(len(text), pos + len(kw) + _SNIPPET_RADIUS)
            intervals.append((s, e))
            start = pos + max(1, len(kw))

    merged = _merge_intervals(intervals)
    parts: list[str] = []
    total = 0
    sep = "\n\n... [excerpt gap] ...\n\n"
    for s, e in merged:
        if total >= max_chars:
            break
        chunk = text[s:e].strip()
        if not chunk:
            continue
        add = chunk if not parts else sep + chunk
        if total + len(add) > max_chars:
            remain = max_chars - total - (len(sep) if parts else 0)
            if remain > 200:
                parts.append(text[s : s + remain].strip())
            break
        parts.append(add)
        total += len(add)

    out = "".join(parts) if parts else ""

    if len(out) < _MIN_EXCERPT_TO_TRUST and len(text) > len(out):
        prefix = text[:_PREFIX_FALLBACK_CHARS].strip()
        if prefix:
            if out:
                out = prefix + sep + out
            else:
                out = prefix
            out = out[:max_chars]

    return out[:max_chars].strip()


def parse_annual_report_links_from_html(html: str, base_url: str = "https://www.screener.in") -> list[dict[str, Any]]:
    """Parse Screener company page HTML for Annual reports list.

    Returns list of dicts: year (int), fy_label, anchor_text, url (absolute).
    """
    soup = BeautifulSoup(html, "lxml")
    h3 = soup.find(
        lambda tag: tag.name == "h3"
        and "annual report" in tag.get_text(strip=True).lower()
    )
    if not h3:
        return []

    ul = h3.find_next_sibling("ul")
    if not ul:
        ul = h3.find_next("ul")
    if not ul:
        return []

    results: list[dict[str, Any]] = []
    for li in ul.find_all("li", recursive=False):
        a = li.find("a", href=True)
        if not a:
            continue
        href = a.get("href", "").strip()
        anchor = a.get_text(strip=True)
        if not href:
            continue
        year = _parse_fy_year_from_anchor_text(anchor)
        if year is None:
            continue
        abs_url = urljoin(base_url + "/", href)
        abs_url = resolve_pdf_url(abs_url)
        results.append({
            "year": year,
            "fy_label": _year_to_fy_label(year),
            "anchor_text": anchor,
            "url": abs_url,
        })

    results.sort(key=lambda r: r["year"], reverse=True)
    return results


def fetch_annual_report_links_from_screener(
    symbol: str,
    session: requests.Session | None = None,
    timeout: int = 25,
) -> list[dict[str, Any]]:
    """GET Screener company page and return list of annual report entries (newest year first)."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return []

    own_session = session is None
    sess = session or _make_session()
    url = SCREENER_COMPANY_PAGE.format(symbol=sym)
    html = ""
    try:
        resp = sess.get(url, timeout=timeout)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.warning("screener_annual_report: fetch page failed %s: %s", url, e)
        return []
    finally:
        if own_session:
            sess.close()

    return parse_annual_report_links_from_html(html)


def fetch_latest_annual_report_from_screener(
    symbol: str,
    session: requests.Session | None = None,
) -> dict[str, Any] | None:
    """Return metadata for the newest annual report linked on Screener, or None."""
    links = fetch_annual_report_links_from_screener(symbol, session=session)
    if not links:
        logger.info("screener_annual_report: no annual report links for %s", symbol)
        return None
    row = links[0]
    return {
        "fy_label": row["fy_label"],
        "year": row["year"],
        "url": row["url"],
        "anchor_text": row["anchor_text"],
    }


def fetch_governance_excerpt_from_latest_screener_ar(
    screener_symbol: str,
    session: requests.Session | None = None,
) -> dict[str, Any] | None:
    """Download latest AR (PDF or ZIP), extract text, build governance excerpt.

    `screener_symbol` is the Screener.in slug (e.g. RELIANCE, SIMPLEXCAS).

    Returns dict:
      fy_label, url, year, raw_text_length, excerpt, excerpt_length
    Or None if no link / empty extract.
    """
    meta = fetch_latest_annual_report_from_screener(screener_symbol, session=session)
    if not meta:
        return None

    own = session is None
    sess = session or _make_session()
    try:
        raw = download_and_extract_text(
            meta["url"],
            sess,
            max_pdf_chars=_MAX_FULL_EXTRACT_PDF,
            max_zip_per_pdf=_MAX_ZIP_PER_PDF,
            max_zip_total=_MAX_ZIP_TOTAL,
            timeout=90,
        )
    finally:
        if own:
            sess.close()

    excerpt = build_governance_excerpt(raw)
    if len(excerpt) < _MIN_EXCERPT_TO_TRUST:
        logger.info(
            "screener_annual_report: excerpt too short (%d chars) for %s",
            len(excerpt),
            screener_symbol,
        )
        return None

    logger.info(
        "screener_annual_report: %s %s raw=%d excerpt=%d",
        screener_symbol,
        meta["fy_label"],
        len(raw),
        len(excerpt),
    )
    return {
        "fy_label": meta["fy_label"],
        "year": meta["year"],
        "url": meta["url"],
        "anchor_text": meta["anchor_text"],
        "raw_text_length": len(raw),
        "excerpt": excerpt,
        "excerpt_length": len(excerpt),
    }
