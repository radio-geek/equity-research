#!/usr/bin/env python3
"""Verify key metrics (Stock P/E, Market Cap, ROCE %, ROE %, D/E, PAT Margin %, EBITDA Margin %) from Screener.

Run from repo root with venv active:
  PYTHONPATH=. python scripts/verify_key_metrics.py [SYMBOL]
Default symbol: RELIANCE
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass


def main() -> None:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "RELIANCE").strip().upper()
    print(f"Fetching key metrics for {symbol} from Screener...")
    print()

    from src.data.screener_scraper import fetch_company_quote
    from src.data.yearly_financials import fetch_yearly_financials
    from src.report.financial_evaluation import build_key_metrics

    quote = fetch_company_quote(symbol)
    yearly = fetch_yearly_financials(symbol, "NSE", max_years=8)
    key_metrics = build_key_metrics(yearly)
    if quote.get("stock_pe") is not None:
        key_metrics["pe"] = str(quote["stock_pe"])
    if quote.get("market_cap"):
        key_metrics["market_cap"] = str(quote["market_cap"])

    print("Screener company quote (raw):")
    print(f"  current_price: {quote.get('current_price')}")
    print(f"  market_cap:    {quote.get('market_cap')}")
    print(f"  stock_pe:      {quote.get('stock_pe')}")
    print(f"  last_price_updated: {quote.get('last_price_updated')}")
    print()

    print("Key metrics (for report header / UI):")
    for label, key in [
        ("Stock P/E", "pe"),
        ("Market Cap", "market_cap"),
        ("ROCE %", "roce"),
        ("ROE %", "roe"),
        ("Debt/Equity", "debt_equity"),
        ("PAT Margin %", "pat_margin"),
        ("EBITDA Margin %", "ebitda_margin"),
    ]:
        val = key_metrics.get(key) or "—"
        print(f"  {label}: {val}")
    print()

    ttm = next((m for m in yearly if m.get("period_label") == "TTM"), None)
    if ttm:
        rev = ttm.get("revenue_cr")
        pat = ttm.get("pat_cr")
        ebitda = ttm.get("ebitda_cr")
        if rev and rev != 0:
            if pat is not None:
                print(f"  (TTM PAT margin computed: {100 * pat / rev:.1f}%)")
            if ebitda is not None:
                print(f"  (TTM EBITDA margin computed: {100 * ebitda / rev:.1f}%)")
    print("Done.")


if __name__ == "__main__":
    main()
