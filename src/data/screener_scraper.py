"""Scrape P&L, Balance Sheet, and Cash Flow from Screener.in (consolidated or company page).

P&L may include a TTM column only after Screener has rolled latest results into TTM; until then
the same table can be yearly and/or quarter columns only. Detection must not require TTM.

Used when finfetch's Screener source returns incorrect TTM. Direct HTML parsing matches the site.

Typical consolidated layout: P&L first, then Balance Sheet, Cash Flow, ratios (indices vary).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)
BASE_URL = "https://www.screener.in/company"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def screener_company_url(symbol: str) -> str:
    """Main company page URL (quote, market cap, key ratios)."""
    sym = (symbol or "").strip().upper()
    return f"{BASE_URL}/{sym}/" if sym else ""


def screener_consolidated_url(symbol: str) -> str:
    """Build consolidated page URL for the given symbol (e.g. RELIANCE -> .../RELIANCE/consolidated/)."""
    sym = (symbol or "").strip().upper()
    return f"{BASE_URL}/{sym}/consolidated/" if sym else ""


def _parse_number(s: str) -> float | None:
    """Parse Screener cell text: '1,024,548', '17%', '(1,234)' (negative), trailing 'Cr', em-dash blanks."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    if s in ("-", "—", "–", "NA", "N/A", "na", "N/a"):
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    s = re.sub(r"\s*Cr\.?\s*$", "", s, flags=re.IGNORECASE).strip()
    s = s.replace(",", "").replace("%", "").strip()
    if not s:
        return None
    if s.startswith("−"):  # unicode minus
        neg = True
        s = s[1:].strip()
    elif s.startswith("-"):
        neg = not neg
        s = s[1:].strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _normalize_row_label(label: str) -> str:
    """Normalize row names so 'Sales+' -> 'Sales +' for compatibility with existing lookups."""
    if not label:
        return label
    # "Sales+", "Net Profit+" -> "Sales +", "Net Profit +"
    label = label.strip()
    if label.endswith("+") and not label.endswith(" +"):
        return label[:-1] + " +"
    return label


def _table_to_dataframe(soup_table: Any) -> pd.DataFrame | None:
    """Parse a <table> into DataFrame: first column = index (row labels), rest = columns."""
    if soup_table is None:
        return None
    rows = soup_table.find_all("tr")
    if not rows:
        return None
    header_cells = rows[0].find_all(["th", "td"])
    if not header_cells:
        return None
    columns = [c.get_text(strip=True) for c in header_cells]
    if not columns:
        return None
    # First column is row label (empty in header); rest are period columns
    col_names = columns[1:] if len(columns) > 1 else []
    data = []
    for tr in rows[1:]:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        row_label = _normalize_row_label(cells[0].get_text(strip=True))
        values = []
        for cell in cells[1 : len(col_names) + 1]:
            raw = cell.get_text(strip=True)
            values.append(_parse_number(raw))
        while len(values) < len(col_names):
            values.append(None)
        data.append([row_label] + values)
    if not data:
        return None
    df = pd.DataFrame(data, columns=["_index"] + col_names)
    df = df.set_index("_index")
    df.index.name = None
    return df


def _find_tables_by_content(soup: BeautifulSoup) -> dict[str, Any]:
    """Find P&L, Balance Sheet, Cash Flow, Ratios tables by scanning content.

    P&L: Detects both standard (Sales, Operating Profit, Net Profit) and bank/financial
    (Revenue +, Profit before tax / Financing Profit, Net Profit +) structures.
    TTM is optional on Screener until latest results feed the TTM column.
    Balance Sheet: Accepts Borrowings or Borrowing (banks often use singular).
    """
    tables = soup.find_all("table")
    result = {}
    for i, t in enumerate(tables):
        text = t.get_text()
        # Standard P&L: Sales (incl. "Sales +"), Operating Profit, Net Profit (incl. "Net Profit +")
        is_standard_pl = "Sales" in text and "Operating Profit" in text and "Net Profit" in text
        # Bank/financial P&L: revenue row, Net Profit, and PBT or financing profit (TTM optional)
        is_bank_pl = (
            ("Revenue +" in text or "Revenue" in text)
            and "Net Profit" in text
            and ("Profit before tax" in text or "Financing Profit" in text)
        )
        if is_standard_pl or is_bank_pl:
            result["profit_loss"] = (i, t)
        elif ("Borrowings" in text or "Borrowing" in text) and "Equity Capital" in text and "Reserves" in text:
            result["balance_sheet"] = (i, t)
        elif "Cash from Operating" in text or "Operating Activity" in text:
            result["cash_flow"] = (i, t)
        elif "ROCE %" in text or "ROCE%" in text:
            result["ratios"] = (i, t)
    return result


# Quote block is in the first ~2500 chars; avoid matching ₹ from news/body (e.g. "₹0.07 Cr").
_QUOTE_BLOCK_MAX_LEN = 3500


def _page_has_quote_data(soup: BeautifulSoup) -> bool:
    """Return True if page shows valid quote data (current price or market cap); False if NA/empty.

    Only inspects the top-of-page quote block so we do not treat body text (e.g. news "₹0.07 Cr")
    as valid quote data. Used to detect when consolidated page is empty so we fall back to
    the standalone company page.
    """
    text = soup.get_text()
    block = text[:_QUOTE_BLOCK_MAX_LEN]
    # Current price: in quote block look for "Current Price" then ₹ and a number (min 0.5 to skip noise)
    price_m = re.search(
        r"Current Price\s*[₹]\s*([\d,]+(?:\.\d+)?)",
        block,
        re.IGNORECASE,
    )
    if price_m:
        raw = price_m.group(1).replace(",", "").strip()
        if raw.upper() not in ("NA", "N/A", ""):
            try:
                p = float(raw)
                if p >= 0.5:  # ignore placeholder/tiny values
                    return True
            except ValueError:
                pass
    # Market cap: in quote block "Market Cap ₹ 19,26,475 Cr." (must have digits)
    mc = re.search(r"Market Cap\s*[₹]\s*([\d,\s]+)(?:\s*Cr\.?)?", block, re.IGNORECASE)
    if mc:
        val = mc.group(1).strip().replace(",", "").replace(" ", "")
        if val and val.upper() not in ("NA", "N/A", "") and any(c.isdigit() for c in val):
            return True
    return False


_TABLE_KEYS = ("profit_loss", "balance_sheet", "cash_flow", "ratios")


def _df_usable(df: pd.DataFrame | None) -> bool:
    return df is not None and hasattr(df, "columns") and len(df.columns) > 0


def _tables_complete(data: dict[str, pd.DataFrame | None]) -> bool:
    """True when all four financial tables were parsed with at least one period column."""
    return all(_df_usable(data.get(k)) for k in _TABLE_KEYS)


def _parse_tables_from_soup(soup: BeautifulSoup) -> dict[str, pd.DataFrame | None]:
    located = _find_tables_by_content(soup)
    out: dict[str, pd.DataFrame | None] = {}
    for key in _TABLE_KEYS:
        if key in located:
            _, table = located[key]
            out[key] = _table_to_dataframe(table)
        else:
            out[key] = None
    return out


def _empty_tables() -> dict[str, pd.DataFrame | None]:
    return {k: None for k in _TABLE_KEYS}


def _table_score(data: dict[str, pd.DataFrame | None]) -> int:
    """Count financial tables with at least one period column (for picking best partial parse)."""
    return sum(1 for k in _TABLE_KEYS if _df_usable(data.get(k)))


def _parse_tables_from_html(html: str) -> dict[str, pd.DataFrame | None]:
    return _parse_tables_from_soup(BeautifulSoup(html, "lxml"))


def fetch_consolidated(symbol: str) -> dict[str, pd.DataFrame | None]:
    """Fetch Screener financial tables: **consolidated URL first**, then company page if needed.

    Attempt 1: ``https://www.screener.in/company/{symbol}/consolidated/``

    Attempt 2 (same symbol, no ``/consolidated/``): when attempt 1 HTTP fails, or parsed tables
    are incomplete (not all four sections with data). Returns **one** parse only, never mixed
    columns from both pages.

    If both are partial, returns whichever has more usable tables; if tied, prefers consolidated
    when it has any data.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _empty_tables()
    url_c = screener_consolidated_url(symbol)
    company_url = screener_company_url(symbol)
    out_c = _empty_tables()
    consolidated_ok = False
    try:
        resp = requests.get(url_c, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        consolidated_ok = True
        out_c = _parse_tables_from_html(resp.text)
    except requests.RequestException as e:
        logger.info("Screener: consolidated request failed for %s: %s", symbol, e)

    if _tables_complete(out_c):
        return out_c

    try:
        resp2 = requests.get(company_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp2.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Screener: company page request failed for %s: %s", symbol, e)
        return out_c

    out_co = _parse_tables_from_html(resp2.text)
    if _tables_complete(out_co):
        logger.info(
            "Screener: using company page %s (consolidated incomplete or unavailable)",
            company_url,
        )
        return out_co

    score_c, score_o = _table_score(out_c), _table_score(out_co)
    if score_o > score_c:
        logger.info("Screener: partial data from company page for %s (more tables than consolidated)", symbol)
        return out_co
    if score_c > score_o or (score_c > 0 and consolidated_ok):
        return out_c
    return out_co if score_o > 0 else out_c


def fetch_company_quote(symbol: str) -> dict[str, Any]:
    """Fetch main company page and extract current price, % change, market cap, P/E, and last price time.

    Returns dict with: current_price (float | None), price_change_pct (str), market_cap (str),
    stock_pe (float | None), last_price_updated (str, e.g. '09 Mar - close price').
    """
    sym = (symbol or "").strip().upper()
    out: dict[str, Any] = {
        "current_price": None,
        "price_change_pct": None,
        "market_cap": None,
        "stock_pe": None,
        "last_price_updated": None,
    }
    if not sym:
        return out
    url = screener_company_url(sym)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return out
    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text()

    # Top-of-page price and % change: "₹ 1,424 1.37%" or "₹ 1,424 +1.37%" or "₹ 1,424 -0.5%"
    top_price_pct = re.search(
        r"[₹]\s*([\d,]+(?:\.\d+)?)\s*([+-]?\d+\.?\d*%)\s*",
        text,
        re.IGNORECASE,
    )
    if top_price_pct:
        raw_price = top_price_pct.group(1).replace(",", "")
        try:
            out["current_price"] = float(raw_price)
        except ValueError:
            pass
        pct_str = top_price_pct.group(2).strip()
        if pct_str and not pct_str.startswith("+") and not pct_str.startswith("-"):
            pct_str = "+" + pct_str
        out["price_change_pct"] = pct_str

    if out["current_price"] is None:
        for pattern in [r"Current Price\s*[₹]\s*([\d,]+(?:\.\d+)?)", r"[₹]\s*([\d,]+(?:\.\d+)?)\s*(?:\d+\.\d+%|%)?"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                raw = m.group(1).replace(",", "")
                try:
                    out["current_price"] = float(raw)
                    break
                except ValueError:
                    pass

    # Market cap: "Market Cap ₹ 19,26,475 Cr." or "Market Cap ₹ 1,234 Cr."
    mc = re.search(r"Market Cap\s*[₹]\s*([\d,]+)", text, re.IGNORECASE)
    if mc:
        out["market_cap"] = mc.group(1).strip()

    # Stock P/E: "Stock P/E 47.0" in the key ratios block
    pe_m = re.search(r"Stock P/E\s*([\d.]+)", text, re.IGNORECASE)
    if pe_m:
        try:
            out["stock_pe"] = float(pe_m.group(1).strip())
        except ValueError:
            pass

    # Last updated: "09 Mar - close price" or "Mar 09 - close" (near the big price)
    date_m = re.search(r"(\d{1,2}\s+[A-Za-z]+\s*-\s*close\s*price|\d{1,2}\s+[A-Za-z]+\s*-\s*close)", text, re.IGNORECASE)
    if date_m:
        out["last_price_updated"] = re.sub(r"\s+", " ", date_m.group(1).strip()).strip()

    return out
