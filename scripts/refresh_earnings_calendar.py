#!/usr/bin/env python3
"""Fetch NSE board-meeting intimations for a date window into the earnings-date calendar.

Idempotent: safe to re-run over overlapping windows. Intended for a Render Cron Job daily
during results season, and for seeding history:

    python scripts/refresh_earnings_calendar.py --from 2025-10-01 --to 2025-10-31
    python scripts/refresh_earnings_calendar.py --days 7          # rolling window
    python scripts/refresh_earnings_calendar.py --backfill-months 14

NSE ignores the date range unless both ends are supplied, and the feed is queried in chunks
because long windows are slow and more likely to time out.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from backend.earnings_date_store import (  # noqa: E402
    delete_projection_window,
    get_attribution_stats,
    get_filer_cadences,
    get_intimations,
    upsert_earnings_dates,
    upsert_intimations,
)
from src.data.nse_board_meetings import (  # noqa: E402
    dedupe_records,
    fetch_board_meetings,
    normalize_row,
)

logger = logging.getLogger("refresh_earnings_calendar")

_CHUNK_DAYS = 30


def _chunks(from_date: date, to_date: date, size: int = _CHUNK_DAYS):
    start = from_date
    while start <= to_date:
        end = min(start + timedelta(days=size - 1), to_date)
        yield start, end
        start = end + timedelta(days=1)


def refresh_window(from_date: date, to_date: date) -> dict[str, int]:
    """Fetch, attribute and store one window. Returns counts for logging."""
    raw = fetch_board_meetings(from_date, to_date)
    if not raw:
        return {"raw": 0, "earnings": 0, "stored": 0, "unattributed": 0}

    # Cadence from already-stored history sharpens period_type for filings whose text states
    # no period noun. Fetched in bulk, and empty on a cold database -- a second pass over the
    # same window after the first backfill will attribute those rows better.
    symbols = sorted({(r.get("bm_symbol") or "").strip().upper() for r in raw if r.get("bm_symbol")})
    cadences = get_filer_cadences(symbols)
    records, attributed, unattributed = _attribute_all(raw, cadences)
    earnings = [r for r in records if r["is_earnings"]]

    # Every raw row goes to the log, including non-earnings ones: it is the reparse source.
    # The log must land first, so the projection's provenance subquery can resolve.
    upsert_intimations(records)
    projection = attributed + unattributed
    upsert_earnings_dates(projection)

    return {
        "raw": len(raw),
        "earnings": len(earnings),
        "stored": len(projection),
        "unattributed": len(unattributed),
    }


def _attribute_all(
    raw: list[dict], cadences: dict[str, set[int]]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Normalize raw rows, then split into (all records, attributed+deduped, unattributed)."""
    records = []
    for row in raw:
        symbol = (row.get("bm_symbol") or "").strip().upper()
        rec = normalize_row(row, cadences.get(symbol))
        if rec:
            records.append(rec)
    earnings = [r for r in records if r["is_earnings"]]
    attributed = dedupe_records([r for r in earnings if r["period_end"] is not None])
    unattributed = [r for r in earnings if r["period_end"] is None]
    return records, attributed, unattributed


def reattribute_window(from_date: date, to_date: date) -> dict[str, int]:
    """Recompute the projection from the stored log, without touching NSE.

    This is what the raw log buys: a parser fix rolls out over all history in seconds.
    first_intimated_date and revision_count are recovered from the log rather than lost, by
    grouping every intimation that resolves to the same (symbol, period_end).
    """
    log_rows = get_intimations(from_date, to_date)
    if not log_rows:
        return {"raw": 0, "earnings": 0, "stored": 0, "unattributed": 0}

    # Re-shape log rows back into the NSE field names normalize_row expects.
    raw = [
        {
            "bm_symbol": r["symbol"], "bm_date": r["bm_date"].strftime("%d-%b-%Y"),
            "bm_purpose": r["purpose"], "bm_desc": r["description"],
            "bm_timestamp": r["announced_at"].strftime("%d-%b-%Y %H:%M:%S")
            if r["announced_at"] else None,
            "sm_name": r["company_name"], "sm_isin": r["isin"],
            "attachment": r["attachment"], "segment": r["segment"],
        }
        for r in log_rows
    ]

    symbols = sorted({r["symbol"] for r in log_rows})
    cadences = get_filer_cadences(symbols)
    records, attributed, unattributed = _attribute_all(raw, cadences)

    # Recover first_intimated_date / revision_count from every intimation for the same period.
    dates_by_key: dict[tuple, set] = {}
    for rec in records:
        if rec["period_end"] is None:
            continue
        dates_by_key.setdefault((rec["symbol"], rec["period_end"]), set()).add(rec["bm_date"])
    for rec in attributed:
        seen = dates_by_key.get((rec["symbol"], rec["period_end"]), {rec["bm_date"]})
        # The winning record won on attribution quality, which is a separate concern from
        # which filing is most recent. Take the date from the latest intimation and the period
        # from the best-attributed one, or a row can end up flagged as revised while its first
        # and current dates are identical.
        rec["intimated_date"] = max(seen)
        rec["first_intimated_date"] = min(seen)
        rec["revision_count"] = max(0, len(seen) - 1)

    projection = attributed + unattributed
    delete_projection_window(from_date, to_date)
    upsert_earnings_dates(projection)
    return {
        "raw": len(raw),
        "earnings": len([r for r in records if r["is_earnings"]]),
        "stored": len(projection),
        "unattributed": len(unattributed),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="from_date", help="start date YYYY-MM-DD")
    ap.add_argument("--to", dest="to_date", help="end date YYYY-MM-DD")
    ap.add_argument("--days", type=int,
                    help="rolling window: this many days back through 30 days ahead")
    ap.add_argument("--backfill-months", type=int,
                    help="seed history this many months back from today")
    ap.add_argument("--reattribute", action="store_true",
                    help="rebuild the projection from the stored log without re-fetching NSE "
                         "(use after a parser change)")
    ap.add_argument("--stats", action="store_true",
                    help="print the attribution quality breakdown afterwards")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1

    today = date.today()
    if args.backfill_months:
        from_date = today - timedelta(days=31 * args.backfill_months)
        to_date = today + timedelta(days=30)
    elif args.days:
        from_date = today - timedelta(days=args.days)
        to_date = today + timedelta(days=30)
    elif args.from_date and args.to_date:
        from_date = date.fromisoformat(args.from_date)
        to_date = date.fromisoformat(args.to_date)
    else:
        # Default cron behaviour: recent filings plus everything already announced ahead.
        from_date = today - timedelta(days=7)
        to_date = today + timedelta(days=30)

    if from_date > to_date:
        print("--from must not be after --to", file=sys.stderr)
        return 1

    totals = {"raw": 0, "earnings": 0, "stored": 0, "unattributed": 0}
    mode = "reattributing" if args.reattribute else "refreshing"
    logger.info("%s %s..%s", mode, from_date, to_date)
    for chunk_from, chunk_to in _chunks(from_date, to_date):
        try:
            counts = (
                reattribute_window(chunk_from, chunk_to)
                if args.reattribute
                else refresh_window(chunk_from, chunk_to)
            )
        except Exception as e:  # noqa: BLE001
            # One bad chunk must not lose the rest of a long backfill.
            logger.error("chunk %s..%s failed: %s", chunk_from, chunk_to, e)
            continue
        for k, v in counts.items():
            totals[k] += v
        logger.info("  %s..%s  %s", chunk_from, chunk_to, counts)

    logger.info(
        "done: %d raw rows, %d earnings, %d stored, %d unattributed",
        totals["raw"], totals["earnings"], totals["stored"], totals["unattributed"],
    )

    if args.stats:
        print("\nAttribution quality:")
        for row in get_attribution_stats(from_date, to_date):
            print(f"  {str(row['period_source']):14s} {str(row['period_type']):3s} "
                  f"n={row['n']:5d} min_conf={row['min_conf']} avg_conf={row['avg_conf']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
