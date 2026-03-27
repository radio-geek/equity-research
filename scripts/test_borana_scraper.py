"""One-off test: fetch BORANA from Screener consolidated and company pages, inspect content.

Optional: pass --offline and set BORANA_CONSOLIDATED_HTML / BORANA_COMPANY_HTML to file paths
to test parsing without network (e.g. after saving pages with curl).
"""
from __future__ import annotations

import argparse
import sys
sys.path.insert(0, ".")

import requests
from bs4 import BeautifulSoup

from src.data.screener_scraper import (
    BASE_URL,
    USER_AGENT,
    screener_company_url,
    screener_consolidated_url,
    _page_has_quote_data,
    _find_tables_by_content,
    fetch_consolidated,
)
from src.data.yearly_financials import fetch_yearly_financials, get_ttm_statements

SYMBOL = "BORANA"


def main() -> None:
    parser = argparse.ArgumentParser(description="Test BORANA scraper")
    parser.add_argument("--offline", action="store_true", help="Use saved HTML files (env BORANA_*_HTML)")
    args = parser.parse_args()

    print("=== BORANA Scraper test ===\n")

    consolidated_url = screener_consolidated_url(SYMBOL)
    company_url = screener_company_url(SYMBOL)
    print(f"Consolidated URL: {consolidated_url}")
    print(f"Company URL:     {company_url}\n")

    if args.offline:
        import os
        cons_path = os.environ.get("BORANA_CONSOLIDATED_HTML", "/tmp/borana_cons.txt")
        company_path = os.environ.get("BORANA_COMPANY_HTML", "/tmp/borana_company.txt")
        print(f"Offline mode: cons={cons_path}, company={company_path}\n")
        try:
            with open(cons_path) as f:
                html_cons = f.read()
            with open(company_path) as f:
                html_company = f.read()
        except FileNotFoundError as e:
            print(f"Missing file: {e}. Save pages with curl first.")
            sys.exit(1)
        soup1 = BeautifulSoup(html_cons, "html.parser")
        soup2 = BeautifulSoup(html_company, "html.parser")
        text1 = soup1.get_text()
    else:
        # Fetch consolidated
        try:
            r1 = requests.get(consolidated_url, headers={"User-Agent": USER_AGENT}, timeout=30)
            print(f"Consolidated: status={r1.status_code}, len={len(r1.text)}")
            soup1 = BeautifulSoup(r1.text, "lxml")
            text1 = soup1.get_text()
        except Exception as e:
            print(f"Consolidated fetch error: {e}\n")
            soup1 = None
            text1 = ""
        soup2 = None

    if soup1 is not None:
        has_quote = _page_has_quote_data(soup1)
        print(f"  _page_has_quote_data(consolidated) = {has_quote}")
        # Show snippet that might contain price/market cap
        if "Market Cap" in text1 or "Current Price" in text1 or "₹" in text1:
            idx = min(
                text1.find("Market Cap") if text1.find("Market Cap") >= 0 else 999999,
                text1.find("Current Price") if text1.find("Current Price") >= 0 else 999999,
                text1.find("₹") if text1.find("₹") >= 0 else 999999,
            )
            idx = idx if idx != 999999 else 0
            print(f"  Snippet (quote area): {repr(text1[max(0, idx):idx + 200])}")
        else:
            print(f"  Snippet (first 500): {repr(text1[:500])}")
        tables1 = _find_tables_by_content(soup1)
        print(f"  Tables found: {list(tables1.keys())}\n")

    if not args.offline and soup2 is None:
        # Fetch company page
        try:
            r2 = requests.get(company_url, headers={"User-Agent": USER_AGENT}, timeout=30)
            print(f"Company page: status={r2.status_code}, len={len(r2.text)}")
            soup2 = BeautifulSoup(r2.text, "lxml")
        except Exception as e:
            print(f"  Error: {e}\n")
            soup2 = None

    if soup2 is not None:
        has_quote2 = _page_has_quote_data(soup2)
        print(f"  _page_has_quote_data(company) = {has_quote2}")
        tables2 = _find_tables_by_content(soup2)
        print(f"  Tables found: {list(tables2.keys())}\n")

    if args.offline:
        print("(Skipping fetch_consolidated / fetch_yearly_financials in offline mode.)")
        print("Conclusion: consolidated has_quote=False => fallback to company page would run.")
        return

    # fetch_consolidated
    print("fetch_consolidated(BORANA):")
    try:
        data = fetch_consolidated(SYMBOL)
        pl = data.get("profit_loss")
        print(f"  profit_loss: {'columns=' + str(list(pl.columns)) if pl is not None and hasattr(pl, 'columns') else pl}")
        print(f"  balance_sheet: {data.get('balance_sheet') is not None}")
        print(f"  cash_flow: {data.get('cash_flow') is not None}")
        print(f"  ratios: {data.get('ratios') is not None}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}\n")
        import traceback
        traceback.print_exc()

    # fetch_yearly_financials
    print("\nfetch_yearly_financials(BORANA, NSE):")
    try:
        metrics = fetch_yearly_financials(SYMBOL, "NSE", max_years=8)
        print(f"  rows: {len(metrics)}")
        if metrics:
            print(f"  first: {metrics[0]}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # get_ttm_statements
    print("\nget_ttm_statements(BORANA, NSE):")
    try:
        st = get_ttm_statements(SYMBOL, "NSE")
        print(f"  keys: {list(st.keys())}")
        print(f"  income len: {len(st.get('income_statement_text') or '')}")
        print(f"  balance len: {len(st.get('balance_sheet_text') or '')}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
