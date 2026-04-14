#!/usr/bin/env python3
"""Smoke-test report PDF generation (same path as backend Playwright render).

Run from the repository root with the project venv active:

  source .venv/bin/activate   # if you use a venv
  pip install -r requirements.txt
  playwright install chromium
  PYTHONPATH=. python scripts/smoke_pdf_local.py

On Apple Silicon, if you still get “Executable doesn't exist” under
``.../chrome-headless-shell-mac-arm64/...`` after installing, run
``playwright install --force chromium`` so the correct architecture is downloaded.

Writes /tmp/equity-research-smoke.pdf on success.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _minimal_payload() -> dict:
    return {
        "meta": {
            "symbol": "SMOKE",
            "exchange": "NSE",
            "company_name": "Smoke Test Co",
        },
        "financials": {
            "yearly_metrics": [],
            "highlights": {},
            "five_year_trend": {"headers": [], "rows": []},
        },
        "company": {},
        "sectoral": {},
        "generated_at": "2026-04-14T12:00:00Z",
        "executive_summary": "Local PDF smoke test.",
        "company_overview": "## Overview\nMinimal body for PDF.",
        "management_research": "",
        "financial_risk": "",
    }


def main() -> int:
    os_cwd = Path.cwd()
    if os_cwd.resolve() != _REPO.resolve():
        print(f"Warning: cwd is {os_cwd}; repo root is {_REPO}. Run from repo root with PYTHONPATH=.", file=sys.stderr)

    from backend.pdf_render import render_payload_to_pdf

    out = Path("/tmp/equity-research-smoke.pdf")
    try:
        pdf = render_payload_to_pdf(_minimal_payload())
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        print("Install browsers: playwright install chromium", file=sys.stderr)
        return 1
    if not pdf or len(pdf) < 100 or not pdf.startswith(b"%PDF"):
        print("FAIL: output is not a PDF", file=sys.stderr)
        return 1
    out.write_bytes(pdf)
    print(f"OK: wrote {len(pdf)} bytes to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
