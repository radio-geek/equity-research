"""Shared PDF/ZIP text extraction for filings (concalls, annual reports, etc.)."""

from __future__ import annotations

import io
import logging
import zipfile

import requests

logger = logging.getLogger(__name__)


def resolve_pdf_url(href: str) -> str:
    """Resolve Screener/BSE view_pdf.php wrappers to a direct-download URL."""
    if "view_pdf.php" in href:
        from urllib.parse import parse_qs, urljoin, urlparse

        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        path = (qs.get("path") or [""])[0]
        if path:
            base = f"{parsed.scheme}://{parsed.netloc}"
            return urljoin(base, "/" + path.lstrip("/"))
    return href


def extract_text_from_pdf_bytes(content: bytes, max_chars: int, source: str = "") -> str:
    """Extract plain text from PDF bytes. Truncates to max_chars. Returns '' on failure."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            if total >= max_chars:
                break
            chunk = page.extract_text() or ""
            if not chunk:
                continue
            remaining = max_chars - total
            if len(chunk) <= remaining:
                parts.append(chunk)
                total += len(chunk)
            else:
                parts.append(chunk[:remaining])
                total = max_chars
                break
        return "\n".join(parts).strip()
    except Exception as e:
        logger.warning("pdf_text: PDF extraction failed for %s: %s", source, e)
        return ""


def extract_text_from_zip_bytes(
    content: bytes,
    max_chars_per_pdf: int,
    max_total: int,
    source: str = "",
) -> str:
    """Concatenate text from all PDFs inside a ZIP; cap per-file and total length."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            pdf_names = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
            if not pdf_names:
                logger.warning("pdf_text: ZIP contains no PDFs: %s", source)
                return ""
            texts: list[str] = []
            for name in pdf_names:
                with zf.open(name) as f:
                    text = extract_text_from_pdf_bytes(
                        f.read(), max_chars_per_pdf, f"{source}/{name}"
                    )
                if text:
                    texts.append(text)
            combined = "\n\n".join(texts)
            return combined[:max_total].strip()
    except Exception as e:
        logger.warning("pdf_text: ZIP extraction failed for %s: %s", source, e)
        return ""


def download_and_extract_text(
    link: str,
    session: requests.Session,
    *,
    max_pdf_chars: int,
    max_zip_per_pdf: int,
    max_zip_total: int,
    timeout: int = 60,
) -> str:
    """Download PDF or ZIP from URL and return extracted plain text."""
    try:
        resp = session.get(link, timeout=timeout)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        logger.warning("pdf_text: failed to download %s: %s", link, e)
        return ""

    lower = link.lower()
    if lower.endswith(".zip"):
        return extract_text_from_zip_bytes(
            content, max_zip_per_pdf, max_zip_total, link
        )
    return extract_text_from_pdf_bytes(content, max_pdf_chars, link)
