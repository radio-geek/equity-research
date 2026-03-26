#!/usr/bin/env python3
"""Build a basic 5-year financial table from NSE or BSE filings.

Uses docs/scraper.md strategy:
- NSE: Session warming + results-comparision API; parse JSON into P&L/BS table.
- BSE: Scrip code resolution + Corporate Action API for filing links; table from
  available BSE APIs or XBRL placeholder.

Usage:
  python scripts/five_year_financial_table.py --symbol RELIANCE --exchange NSE
  python scripts/five_year_financial_table.py --symbol 500325 --exchange BSE
  python scripts/five_year_financial_table.py --symbol RELIANCE --exchange NSE --output csv
"""

from __future__ import annotations

import argparse
from typing import Any
import csv
import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

# Allow running from repo root or from scripts/
if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NSE
# ---------------------------------------------------------------------------

NSE_HOME = "https://www.nseindia.com/"
NSE_QUOTES_BASE = "https://www.nseindia.com/get-quotes/equity?symbol="
NSE_RESULTS_COMPARISION = "https://www.nseindia.com/api/results-comparision"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": NSE_HOME,
}


def _purify_symbol(symbol: str) -> str:
    """URL-encode symbol for NSE (e.g. & -> %26)."""
    return quote(symbol.strip().upper(), safe="")


def _nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def _nse_warmup(session: requests.Session, symbol: str) -> None:
    """Warm NSE session: homepage then quotes page so API accepts request."""
    try:
        session.get(NSE_HOME, timeout=10)
        time.sleep(0.5)
    except Exception as e:
        log.warning("NSE homepage warmup failed: %s", e)
    try:
        session.get(NSE_QUOTES_BASE + _purify_symbol(symbol), timeout=10)
        session.headers["Referer"] = NSE_QUOTES_BASE + _purify_symbol(symbol)
        time.sleep(0.5)
    except Exception as e:
        log.warning("NSE quotes warmup failed: %s", e)


def fetch_nse_results_comparision(symbol: str) -> dict | list | None:
    """Fetch NSE results-comparision JSON. Returns parsed JSON or None."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None
    session = _nse_session()
    _nse_warmup(session, symbol)
    url = f"{NSE_RESULTS_COMPARISION}?symbol={_purify_symbol(symbol)}"
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        log.warning("NSE results-comparision request failed: %s", e)
        return None
    except json.JSONDecodeError as e:
        log.warning("NSE results-comparision invalid JSON: %s", e)
        return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if val != val:
            return None
        return float(val)
    try:
        s = str(val).strip().replace(",", "")
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_nse_yearly_from_annual(data: dict) -> list[dict]:
    """Try to extract yearly rows from NSE annual results structure.

    NSE may return e.g. yearlyResults list or annualData with year keys.
    Each row: { period_label, revenue_cr, pat_cr, ebitda_cr, eps, ... }
    """
    out: list[dict] = []
    yearly = data.get("yearlyResults") or data.get("annualResults") or data.get("yearly")
    if isinstance(yearly, list) and yearly:
        for row in yearly:
            if not isinstance(row, dict):
                continue
            period = row.get("year") or row.get("period") or row.get("finYear") or ""
            if not period:
                continue
            rev = _safe_float(row.get("sales") or row.get("revenue") or row.get("income") or row.get("totalIncome"))
            pat = _safe_float(row.get("netProfit") or row.get("pat") or row.get("profitAfterTax"))
            ebitda = _safe_float(row.get("operatingProfit") or row.get("ebitda") or row.get("op"))
            eps = _safe_float(row.get("eps") or row.get("earningsPerShare"))
            out.append({
                "period_label": str(period).strip()[:20],
                "revenue_cr": round(rev, 2) if rev is not None else None,
                "pat_cr": round(pat, 2) if pat is not None else None,
                "ebitda_cr": round(ebitda, 2) if ebitda is not None else None,
                "eps": round(eps, 2) if eps is not None else None,
            })
        return out

    # Try annualData as dict of year -> metrics
    annual = data.get("annualData") or data.get("yearlyData")
    if isinstance(annual, dict):
        for year_key, row in sorted(annual.items(), reverse=True):
            if not isinstance(row, dict):
                continue
            rev = _safe_float(row.get("sales") or row.get("revenue") or row.get("totalIncome"))
            pat = _safe_float(row.get("netProfit") or row.get("pat"))
            ebitda = _safe_float(row.get("operatingProfit") or row.get("ebitda"))
            eps = _safe_float(row.get("eps"))
            out.append({
                "period_label": str(year_key).strip()[:20],
                "revenue_cr": round(rev, 2) if rev is not None else None,
                "pat_cr": round(pat, 2) if pat is not None else None,
                "ebitda_cr": round(ebitda, 2) if ebitda is not None else None,
                "eps": round(eps, 2) if eps is not None else None,
            })
        out.reverse()
        return out

    return out


def _parse_nse_res_cmp_data(data: dict) -> list[dict]:
    """Parse NSE resCmpData (quarterly results). Pick annual rows (re_to_dt 31-MAR-*); values in lakhs -> Cr (÷100)."""
    out: list[dict] = []
    rows = data.get("resCmpData") or data.get("rescmpdata")
    if not isinstance(rows, list):
        return out
    # NSE sends amounts in lakhs (1 Cr = 100 lakhs). Divide by 100 for Crores.
    LAKHS_TO_CR = 100.0
    for r in rows:
        if not isinstance(r, dict):
            continue
        to_dt = (r.get("re_to_dt") or "").strip().upper()
        if "31-MAR" not in to_dt and "31 MAR" not in to_dt:
            continue
        # Parse year from "31-MAR-2024"
        parts = to_dt.replace("-", " ").split()
        year = None
        for p in parts:
            if len(p) == 4 and p.isdigit():
                year = int(p)
                break
        if year is None:
            continue
        period_label = f"FY{year % 100}"
        net_sale = _safe_float(r.get("re_net_sale"))
        net_profit = _safe_float(r.get("re_net_profit"))
        eps = _safe_float(r.get("re_basic_eps_for_cont_dic_opr") or r.get("re_dilut_eps_for_cont_dic_opr"))
        op_profit = _safe_float(r.get("re_con_pro_loss") or r.get("re_pro_loss_bef_tax"))
        if net_sale is not None:
            net_sale = round(net_sale / LAKHS_TO_CR, 2)
        if net_profit is not None:
            net_profit = round(net_profit / LAKHS_TO_CR, 2)
        if op_profit is not None:
            op_profit = round(op_profit / LAKHS_TO_CR, 2)
        out.append({
            "period_label": period_label,
            "revenue_cr": net_sale,
            "pat_cr": net_profit,
            "ebitda_cr": op_profit,
            "eps": round(eps, 2) if eps is not None else None,
        })
    out.sort(key=lambda x: x["period_label"])
    return out[-5:]


def _parse_nse_results_comparision(data: dict | list) -> list[dict]:
    """Parse NSE results-comparision response into list of yearly metrics (last 5 years)."""
    if isinstance(data, dict):
        # NSE actual response: { "resCmpData": [ quarterly rows ] }
        res_cmp = _parse_nse_res_cmp_data(data)
        if res_cmp:
            return res_cmp
        inner = data.get("data") or data.get("result")
        if inner is not None:
            data = inner
    if isinstance(data, list):
        # Sometimes API returns list of period objects
        rows = []
        for item in data:
            if isinstance(item, dict):
                period = item.get("year") or item.get("period") or item.get("finYear") or ""
                if period:
                    rows.append({
                        "period_label": str(period).strip()[:20],
                        "revenue_cr": round(_safe_float(item.get("sales") or item.get("revenue") or item.get("totalIncome")), 2) if _safe_float(item.get("sales") or item.get("revenue") or item.get("totalIncome")) is not None else None,
                        "pat_cr": round(_safe_float(item.get("netProfit") or item.get("pat")), 2) if _safe_float(item.get("netProfit") or item.get("pat")) is not None else None,
                        "ebitda_cr": round(_safe_float(item.get("operatingProfit") or item.get("ebitda")), 2) if _safe_float(item.get("operatingProfit") or item.get("ebitda")) is not None else None,
                        "eps": round(_safe_float(item.get("eps")), 2) if _safe_float(item.get("eps")) is not None else None,
                    })
        return rows[-5:] if len(rows) > 5 else rows

    rows = _parse_nse_yearly_from_annual(data)
    if rows:
        return rows[-5:]

    # Fallback: scan for any numeric arrays keyed by year-like keys
    year_pattern = re.compile(r"^(20\d{2}|fy\s*\d{2}|\d{2})$", re.I)
    for key, val in data.items():
        if year_pattern.match(str(key).strip()) and isinstance(val, dict):
            rev = _safe_float(val.get("sales") or val.get("revenue") or val.get("totalIncome"))
            pat = _safe_float(val.get("netProfit") or val.get("pat"))
            ebitda = _safe_float(val.get("operatingProfit") or val.get("ebitda"))
            eps = _safe_float(val.get("eps"))
            out_row = {
                "period_label": str(key).strip()[:20],
                "revenue_cr": round(rev, 2) if rev is not None else None,
                "pat_cr": round(pat, 2) if pat is not None else None,
                "ebitda_cr": round(ebitda, 2) if ebitda is not None else None,
                "eps": round(eps, 2) if eps is not None else None,
            }
            if any(out_row[k] is not None for k in ["revenue_cr", "pat_cr", "ebitda_cr", "eps"]):
                rows.append(out_row)
    if rows:
        rows.sort(key=lambda r: (r["period_label"],))
        return rows[-5:]
    return []


# ---------------------------------------------------------------------------
# BSE
# ---------------------------------------------------------------------------

BSE_CORPORATE_ACTION = "https://api.bseindia.com/BseIndiaAPI/api/CorporateAction/w"
BSE_SCRIPT_INFO = "https://api.bseindia.com/BseIndiaAPI/api/ListScript/w"
# Annual & Quarterly trend tables (HTML in Cr./M); requires Origin + Referer: https://www.bseindia.com
BSE_GET_REPORT_RESULT = "https://api.bseindia.com/BseIndiaAPI/api/GetReportNewFor_Result/w"

# BSE financials/results page: works for ANY equity scrip code (no company name/slug needed)
# See docs/scraper.md. Human-readable URL (company-name/shortname/scripcode) is equivalent.
BSE_FINANCIALS_RESULTS_URL = "https://www.bseindia.com/stock-share-price/equity/scripcode/{scrip_code}/financials-results/"


def bse_financials_url(scrip_code: str) -> str:
    """Return BSE financials-results page URL for the given scrip code (any BSE equity)."""
    return BSE_FINANCIALS_RESULTS_URL.format(scrip_code=str(scrip_code).strip())

# Map BSE scrip code -> NSE symbol for same company (to fetch 5Y table via NSE when BSE has no numeric API)
BSE_SCRIP_TO_NSE: dict[str, str] = {
    "500325": "RELIANCE",   # Reliance Industries
    "500180": "HDFCBANK",   # HDFC Bank
    "532540": "TCS",        # TCS
    "532215": "INFY",       # Infosys
}


def _bse_api_headers() -> dict:
    """Headers required for BSE API (Origin + Referer must be www.bseindia.com)."""
    return {
        "User-Agent": DEFAULT_HEADERS["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.bseindia.com",
        "Referer": "https://www.bseindia.com/",
    }


def fetch_bse_get_report_result(scrip_code: str) -> dict | None:
    """Fetch BSE GetReportNewFor_Result: returns QtlyinCr, AnninCr (HTML tables), QtlyinM, AnninM."""
    try:
        r = requests.get(
            BSE_GET_REPORT_RESULT,
            params={"scripcode": str(scrip_code).strip()},
            headers=_bse_api_headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("BSE GetReportNewFor_Result request failed: %s", e)
        return None


def parse_bse_html_table(html_str: str) -> dict:
    """Parse BSE table HTML (AnninCr or QtlyinCr) into headers and list of row dicts. Returns {headers, rows}."""
    if not html_str or not html_str.strip():
        return {"headers": [], "rows": []}
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("BeautifulSoup not available; install beautifulsoup4 to parse BSE table HTML")
        return {"headers": [], "rows": []}
    soup = BeautifulSoup(html_str.strip(), "lxml")
    thead = soup.find("thead")
    tbody = soup.find("tbody")
    headers = []
    if thead:
        tr = thead.find("tr")
        if tr:
            for td in tr.find_all("td"):
                headers.append((td.get_text() or "").strip())
    if headers and headers[0] in ("(in Cr.)", "(in Million)"):
        headers = headers[1:]
    rows = []
    if tbody:
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            cells = [(td.get_text() or "").strip() for td in tds]
            if not cells:
                continue
            first = cells[0]
            if not first or first in ("Standalone", "Consolidated", "--"):
                continue
            if len(cells) == 1 or (len(tds) > 1 and tds[0].get("colspan")):
                continue
            values = cells[1 : len(headers) + 1] if len(cells) > len(headers) else cells[1:]
            if values and first.lower() not in ("standalone", "consolidated"):
                rows.append({"metric": first, "cells": values})
    return {"headers": headers, "rows": rows}


def fetch_bse_annual_trend_table(scrip_code: str) -> dict:
    """Fetch BSE annual trend table for scrip code. Returns {headers, rows} (in Cr.)."""
    data = fetch_bse_get_report_result(scrip_code)
    if not data or not isinstance(data, dict):
        return {"headers": [], "rows": []}
    html = data.get("AnninCr") or data.get("AnninM") or ""
    return parse_bse_html_table(html)


def fetch_bse_corporate_actions(scrip_code: str) -> dict | None:
    """Fetch BSE Corporate Action API response (Table2 = filings list)."""
    try:
        r = requests.get(
            BSE_CORPORATE_ACTION,
            params={"scripcode": scrip_code},
            headers={**_bse_api_headers()},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("BSE Corporate Action request failed: %s", e)
        return None


def resolve_bse_scrip_code(symbol: str) -> str | None:
    """Resolve symbol to BSE scrip code. If symbol is already 5–6 digits, use as scrip code."""
    s = (symbol or "").strip()
    if re.match(r"^\d{5,6}$", s):
        return s
    # Optional: call BSE ListScript or search API to resolve name -> scrip code.
    # For now we require numeric scrip code for BSE.
    return None


def extract_bse_financial_filings(api_data: dict) -> list[dict]:
    """From Corporate Action API, extract financial result / annual report filings (Table2)."""
    filings = []
    table2 = api_data.get("Table2") or api_data.get("Table 2")
    if not isinstance(table2, list):
        return filings
    for row in table2:
        if not isinstance(row, dict):
            continue
        desc = (row.get("Purpose") or row.get("desc") or row.get("Description") or "").lower()
        if "financial result" in desc or "annual result" in desc or "profit" in desc or "xbrl" in desc:
            filings.append({
                "date": row.get("dt_dt") or row.get("date") or row.get("ExDate") or "",
                "purpose": row.get("Purpose") or row.get("desc") or row.get("Description") or "",
                "link": row.get("attachment") or row.get("link") or row.get("Attach") or "",
            })
    return filings[:20]


# ---------------------------------------------------------------------------
# Table output
# ---------------------------------------------------------------------------

def build_five_year_table(rows: list[dict]) -> dict:
    """Build 5-year table structure: headers + rows for Revenue, PAT, EBITDA, EPS."""
    rows = [r for r in rows if r.get("period_label")][-5:]
    if not rows:
        return {"headers": [], "rows": []}
    headers = [r["period_label"] for r in rows]
    metrics = [
        ("Revenue", "₹ Cr", "revenue_cr"),
        ("PAT", "₹ Cr", "pat_cr"),
        ("EBITDA", "₹ Cr", "ebitda_cr"),
        ("EPS", "₹", "eps"),
    ]
    out_rows = []
    for label, unit, key in metrics:
        cells = []
        for r in rows:
            v = r.get(key)
            if v is None:
                cells.append("N/A")
            else:
                try:
                    f = float(v)
                    cells.append(f"{f:.2f}" if abs(f) < 1e6 else f"{int(round(f))}")
                except (TypeError, ValueError):
                    cells.append("N/A")
        out_rows.append({"metric": label, "unit": unit, "cells": cells})
    return {"headers": headers, "rows": out_rows}


def print_table(table: dict) -> None:
    """Print table to stdout (human-readable)."""
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    if not headers:
        print("No data to display.")
        return
    col_width = 14
    head = "Metric".ljust(16) + "".join(h.ljust(col_width) for h in headers)
    print(head)
    print("-" * len(head))
    for r in rows:
        cells = r.get("cells") or []
        line = (r.get("metric") or "").ljust(16) + "".join(str(c).ljust(col_width) for c in cells)
        print(line)


def write_csv(table: dict, path: Path) -> None:
    """Write table to CSV file."""
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    if not headers:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Unit"] + list(headers))
        for r in rows:
            w.writerow([r.get("metric", ""), r.get("unit", "")] + list(r.get("cells") or []))
    log.info("Wrote %s", path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Build 5-year financial table from NSE or BSE")
    ap.add_argument("--symbol", required=True, help="NSE symbol (e.g. RELIANCE) or BSE scrip code (e.g. 500325)")
    ap.add_argument("--exchange", choices=["NSE", "BSE"], default="NSE", help="Exchange (default: NSE)")
    ap.add_argument("--output", choices=["table", "csv", "json"], default="table", help="Output format")
    ap.add_argument("--outfile", default="", help="Output file path (for csv/json)")
    ap.add_argument("--debug", action="store_true", help="Log raw API response")
    args = ap.parse_args()

    symbol = (args.symbol or "").strip()
    exchange = (args.exchange or "NSE").strip().upper()
    if not symbol:
        log.error("--symbol is required")
        sys.exit(1)

    yearly_rows: list[dict] = []
    bse_filings: list[dict] = []
    table: dict = {"headers": [], "rows": []}

    if exchange == "NSE":
        raw = fetch_nse_results_comparision(symbol)
        if args.debug and raw is not None:
            print(json.dumps(raw, indent=2)[:4000])
        if raw is not None:
            yearly_rows = _parse_nse_results_comparision(raw)
        if not yearly_rows:
            log.warning("NSE returned no yearly data for %s. Try --debug to inspect response.", symbol)
        table = build_five_year_table(yearly_rows)
    else:
        scrip = resolve_bse_scrip_code(symbol)
        if not scrip:
            log.error("BSE requires a 5–6 digit scrip code (e.g. 500325 for Reliance). Symbol '%s' not resolved.", symbol)
            sys.exit(1)
        # Prefer BSE GetReportNewFor_Result API (Annual / Quarterly trend tables; Origin+Referer required).
        bse_report = fetch_bse_get_report_result(scrip)
        if args.debug and bse_report:
            print(json.dumps({k: (v[:200] + "..." if isinstance(v, str) and len(v) > 200 else v) for k, v in (bse_report or {}).items()}, indent=2))
        if bse_report and (bse_report.get("AnninCr") or bse_report.get("AnninM")):
            table = fetch_bse_annual_trend_table(scrip)
            for r in table.get("rows") or []:
                r.setdefault("unit", "₹ Cr")
            if table.get("headers"):
                log.info("BSE scrip %s: Annual trend table from GetReportNewFor_Result API.", scrip)
        if not table.get("headers"):
            nse_symbol = BSE_SCRIP_TO_NSE.get(scrip)
            if nse_symbol:
                raw = fetch_nse_results_comparision(nse_symbol)
                if raw is not None:
                    yearly_rows = _parse_nse_results_comparision(raw)
                    if yearly_rows:
                        log.info("BSE scrip %s = %s on NSE. Table below uses NSE data (same company).", scrip, nse_symbol)
            if not yearly_rows:
                data = fetch_bse_corporate_actions(scrip)
                if args.debug and data is not None:
                    print(json.dumps(data, indent=2)[:4000])
                bse_filings = extract_bse_financial_filings(data or {})
                log.info("BSE: found %d corporate action entries for scrip %s.", len(bse_filings), scrip)
                if bse_filings:
                    print("\nBSE Corporate actions / filings:")
                    for f in bse_filings[:10]:
                        print("  ", f.get("date"), (f.get("purpose") or "")[:60], f.get("link") or "(no link)")
            table = build_five_year_table(yearly_rows)

    if args.output == "table":
        print_table(table)
    elif args.output == "csv":
        outfile = args.outfile or f"financial_5y_{symbol}_{exchange}.csv"
        write_csv(table, Path(outfile))
    elif args.output == "json":
        outfile = args.outfile or f"financial_5y_{symbol}_{exchange}.json"
        Path(outfile).write_text(json.dumps({"symbol": symbol, "exchange": exchange, "table": table}, indent=2), encoding="utf-8")
        log.info("Wrote %s", outfile)

    if not yearly_rows and exchange == "NSE":
        sys.exit(1)


if __name__ == "__main__":
    main()
