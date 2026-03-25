#!/usr/bin/env python3
"""Run governance/auditor extraction from latest Screener-linked annual report (any symbol).

Example:
  PYTHONPATH=. python scripts/run_governance_from_ar.py SIMPLEXCAS
  PYTHONPATH=. python scripts/run_governance_from_ar.py SIMPLEXCAS --extract-only

`symbol` is the Screener.in slug (same as https://www.screener.in/company/{SYMBOL}/).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "symbol",
        help="Screener company slug, e.g. SIMPLEXCAS, RELIANCE",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Scrape AR URL, download, build excerpt only (no OpenAI call)",
    )
    args = parser.parse_args()
    sym = args.symbol.strip().upper()
    if not sym:
        print("symbol required", file=sys.stderr)
        sys.exit(1)

    from src.data.screener_annual_report import (
        fetch_governance_excerpt_from_latest_screener_ar,
        fetch_latest_annual_report_from_screener,
    )

    if args.extract_only:
        meta = fetch_latest_annual_report_from_screener(sym)
        print("=== Latest annual report on Screener ===")
        print(json.dumps(meta, indent=2))
        bundle = fetch_governance_excerpt_from_latest_screener_ar(sym)
        print("\n=== Governance excerpt ===")
        if bundle:
            preview = {
                "fy_label": bundle["fy_label"],
                "year": bundle["year"],
                "url": bundle["url"],
                "raw_text_length": bundle["raw_text_length"],
                "excerpt_length": bundle["excerpt_length"],
                "excerpt_preview": (bundle["excerpt"][:800] + "…")
                if len(bundle["excerpt"]) > 800
                else bundle["excerpt"],
            }
            print(json.dumps(preview, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "error": "No excerpt (missing link, download failure, or text too short / empty)",
                    },
                    indent=2,
                )
            )
        return

    bundle = fetch_governance_excerpt_from_latest_screener_ar(sym)
    if not bundle:
        print(
            "Failed to build governance excerpt. Use --extract-only to debug.",
            file=sys.stderr,
        )
        sys.exit(1)

    from src.nodes.prompts import (
        auditor_flags_from_annual_report_prompt,
        invoke_llm_structured,
    )
    from src.nodes.schemas import AuditorFlagsStructured

    company = sym
    system, user = auditor_flags_from_annual_report_prompt(
        company,
        sym,
        "NSE",
        bundle["fy_label"],
        bundle["url"],
        bundle["excerpt"],
    )
    parsed = invoke_llm_structured(
        system, user, AuditorFlagsStructured, use_web_search=False
    )
    out = parsed.model_dump() if parsed else None
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
