"""Store NSE board-meeting intimations and the derived earnings-date calendar.

Two tables (see backend/migrations/008_earnings_dates.sql):
  board_meeting_intimations - raw source log, so attribution can be re-run without re-fetching
  earnings_dates            - derived projection, one row per (symbol, exchange, period_end)

Read paths swallow exceptions and log, following transcript_store, so a DB hiccup cannot take
the calendar page down. Write paths let exceptions propagate to the refresh script, which needs
a non-zero exit.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from backend.db import execute_many, fetchall

logger = logging.getLogger(__name__)

# A QoQ peer further back than this is a gap in history, not a previous quarter.
_MAX_QOQ_GAP_DAYS = 200


def upsert_intimations(records: list[dict[str, Any]]) -> None:
    """Batch-insert raw board-meeting intimations (the reparse source log)."""
    execute_many(
        """
        INSERT INTO board_meeting_intimations
          (symbol, exchange, segment, company_name, isin, bm_date, purpose,
           description, announced_at, attachment)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, exchange, bm_date, purpose, announced_at)
        DO UPDATE SET description = EXCLUDED.description,
                      attachment  = EXCLUDED.attachment
        """,
        [
            (
                rec["symbol"], rec.get("exchange", "NSE"), rec.get("segment", "equities"),
                rec.get("company_name"), rec.get("isin"), rec["bm_date"],
                rec.get("purpose") or "", rec.get("description"),
                rec.get("announced_at"), rec.get("attachment"),
            )
            for rec in records
        ],
    )


def upsert_earnings_dates(records: list[dict[str, Any]]) -> None:
    """Batch-upsert the derived projection rows.

    source_intimation_id is resolved by a scalar subquery on the log's natural key rather than
    round-tripping a RETURNING id per row, which is what makes a multi-month backfill viable.

    Two independent guards, because recency and attribution quality are different concerns:
      - the intimated date is a fact, so a newer filing always wins (that is how a postponement
        propagates, and it sets date_status='revised' plus revision_count);
      - period_type and friends are inferences, so only a better-attributed record may
        overwrite them, regardless of which filing arrived later. Without this, a company that
        files a generic intimation alongside a 'Financial Results' row gets its period_type
        decided by filing order, which mislabels roughly one half-yearly filer in seven.

    The outer WHERE skips no-op updates so stored_at stays a true first-seen marker.
    """
    execute_many(
        """
        INSERT INTO earnings_dates
          (symbol, exchange, segment, company_name, isin, period_end, period_type,
           covers_full_year, intimated_date, first_intimated_date, revision_count,
           is_earnings, purpose, description, attachment, period_source, period_confidence,
           attribution_note, announced_at, source_intimation_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
          (SELECT b.id FROM board_meeting_intimations b
            WHERE b.symbol = %s AND b.exchange = %s AND b.bm_date = %s
              AND b.purpose = %s AND b.announced_at IS NOT DISTINCT FROM %s
            LIMIT 1))
        ON CONFLICT (symbol, exchange, period_end) WHERE period_end IS NOT NULL
        DO UPDATE SET
          intimated_date = CASE
            WHEN EXCLUDED.announced_at IS NOT NULL
             AND (earnings_dates.announced_at IS NULL
                  OR EXCLUDED.announced_at > earnings_dates.announced_at)
            THEN EXCLUDED.intimated_date ELSE earnings_dates.intimated_date END,
          date_status = CASE
            WHEN EXCLUDED.announced_at IS NOT NULL
             AND (earnings_dates.announced_at IS NULL
                  OR EXCLUDED.announced_at > earnings_dates.announced_at)
             AND EXCLUDED.intimated_date <> earnings_dates.intimated_date
            THEN 'revised' ELSE earnings_dates.date_status END,
          revision_count = earnings_dates.revision_count + CASE
            WHEN EXCLUDED.announced_at IS NOT NULL
             AND (earnings_dates.announced_at IS NULL
                  OR EXCLUDED.announced_at > earnings_dates.announced_at)
             AND EXCLUDED.intimated_date <> earnings_dates.intimated_date
            THEN 1 ELSE 0 END,
          period_type = CASE
            WHEN COALESCE(EXCLUDED.period_confidence, 0)
               > COALESCE(earnings_dates.period_confidence, 0)
            THEN EXCLUDED.period_type ELSE earnings_dates.period_type END,
          covers_full_year = CASE
            WHEN COALESCE(EXCLUDED.period_confidence, 0)
               > COALESCE(earnings_dates.period_confidence, 0)
            THEN EXCLUDED.covers_full_year ELSE earnings_dates.covers_full_year END,
          period_source = CASE
            WHEN COALESCE(EXCLUDED.period_confidence, 0)
               > COALESCE(earnings_dates.period_confidence, 0)
            THEN EXCLUDED.period_source ELSE earnings_dates.period_source END,
          attribution_note = CASE
            WHEN COALESCE(EXCLUDED.period_confidence, 0)
               > COALESCE(earnings_dates.period_confidence, 0)
            THEN EXCLUDED.attribution_note ELSE earnings_dates.attribution_note END,
          period_confidence = GREATEST(
            COALESCE(earnings_dates.period_confidence, 0),
            COALESCE(EXCLUDED.period_confidence, 0)),
          company_name = COALESCE(EXCLUDED.company_name, earnings_dates.company_name),
          isin         = COALESCE(EXCLUDED.isin, earnings_dates.isin),
          purpose      = EXCLUDED.purpose,
          description  = EXCLUDED.description,
          attachment   = COALESCE(EXCLUDED.attachment, earnings_dates.attachment),
          source_intimation_id = COALESCE(EXCLUDED.source_intimation_id,
                                          earnings_dates.source_intimation_id),
          announced_at = GREATEST(earnings_dates.announced_at, EXCLUDED.announced_at),
          updated_at   = now()
        WHERE (EXCLUDED.announced_at IS NOT NULL
               AND (earnings_dates.announced_at IS NULL
                    OR EXCLUDED.announced_at > earnings_dates.announced_at))
           OR COALESCE(EXCLUDED.period_confidence, 0)
            > COALESCE(earnings_dates.period_confidence, 0)
        """,
        [
            (
                rec["symbol"], rec.get("exchange", "NSE"), rec.get("segment", "equities"),
                rec.get("company_name"), rec.get("isin"), rec.get("period_end"),
                rec.get("period_type"), rec.get("covers_full_year", False),
                rec.get("intimated_date") or rec["bm_date"],
                rec.get("first_intimated_date") or rec["bm_date"],
                rec.get("revision_count", 0),
                rec.get("is_earnings", True),
                rec.get("purpose"), rec.get("description"), rec.get("attachment"),
                rec.get("period_source"), rec.get("period_confidence"),
                rec.get("attribution_note"), rec.get("announced_at"),
                # source_intimation_id subquery params (the log's natural key)
                rec["symbol"], rec.get("exchange", "NSE"), rec["bm_date"],
                rec.get("purpose") or "", rec.get("announced_at"),
            )
            for rec in records
        ],
    )


def get_filer_cadence(symbol: str, exchange: str = "NSE") -> set[int]:
    """Return the period-end months this filer has used historically, e.g. {3, 6, 9, 12}.

    Feeds period_type inference for filings whose text states no period noun. Only
    confidently-attributed rows are used, so a weak guess cannot reinforce itself.
    """
    try:
        rows = fetchall(
            """
            SELECT DISTINCT date_part('month', period_end)::int AS m
            FROM earnings_dates
            WHERE symbol = %s AND exchange = %s
              AND period_end IS NOT NULL AND is_earnings
              AND COALESCE(period_confidence, 0) >= 75
            ORDER BY m
            """,
            (symbol.upper(), exchange.upper()),
        )
        return {r["m"] for r in rows}
    except Exception as e:  # noqa: BLE001
        logger.warning("get_filer_cadence failed for %s: %s", symbol, e)
        return set()


def get_intimations(from_date: date, to_date: date) -> list[dict[str, Any]]:
    """Read raw log rows for a meeting-date window, for re-attribution without re-fetching."""
    try:
        return fetchall(
            """
            SELECT symbol, exchange, segment, company_name, isin, bm_date, purpose,
                   description, announced_at, attachment
            FROM board_meeting_intimations
            WHERE bm_date >= %s AND bm_date <= %s
            ORDER BY symbol, bm_date, announced_at
            """,
            (from_date, to_date),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("get_intimations failed: %s", e)
        return []


def delete_projection_window(from_date: date, to_date: date) -> None:
    """Drop projection rows in a results-date window so they can be rebuilt from the log.

    Used only by the --reattribute path. The confidence guard in upsert_earnings_dates
    deliberately refuses equal-confidence overwrites, so a parser *correction* (same
    confidence, different period_type) cannot be applied by upsert alone -- the projection has
    to be rebuilt. Safe because board_meeting_intimations retains the full source truth.
    """
    execute_many(
        "DELETE FROM earnings_dates WHERE results_date >= %s AND results_date <= %s",
        [(from_date, to_date)],
    )


def get_filer_cadences(
    symbols: list[str], exchange: str = "NSE"
) -> dict[str, set[int]]:
    """Bulk form of get_filer_cadence: {symbol: {period-end months}} in one query."""
    if not symbols:
        return {}
    try:
        rows = fetchall(
            """
            SELECT symbol, date_part('month', period_end)::int AS m
            FROM earnings_dates
            WHERE symbol = ANY(%s) AND exchange = %s
              AND period_end IS NOT NULL AND is_earnings
              AND COALESCE(period_confidence, 0) >= 75
            GROUP BY symbol, m
            """,
            ([s.upper() for s in symbols], exchange.upper()),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("get_filer_cadences failed: %s", e)
        return {}
    out: dict[str, set[int]] = {}
    for r in rows:
        out.setdefault(r["symbol"], set()).add(r["m"])
    return out


def get_calendar(
    from_date: date,
    to_date: date,
    period_type: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return calendar rows for a results-date window, each with YoY/QoQ peers and history.

    Comparisons come back as objects carrying an explicit reason, never a bare null: a NULL
    delta rendered by a naive `delta < 0 ? 'earlier' : 'later'` check displays as "later",
    because `null < 0` is false in JS. A company with no prior-year data would otherwise be
    shown as having reported later than last year.

    Rows whose period could not be attributed are still returned -- they are real upcoming
    results -- with both comparisons reasoned as 'period_unattributed'.
    """
    try:
        return fetchall(
            f"""
            WITH cal AS (
              SELECT id, symbol, exchange, segment, company_name, period_end, period_type,
                     covers_full_year, fiscal_year, fiscal_quarter, results_date,
                     intimated_date, first_intimated_date, actual_results_date, date_status,
                     revision_count, lag_days, period_source, period_confidence,
                     attribution_note, announced_at, attachment,
                     (actual_results_date IS NULL) AS lag_is_provisional
              FROM earnings_dates
              WHERE is_earnings
                AND results_date >= %(from_date)s
                AND results_date <= %(to_date)s
                AND (%(period_type)s IS NULL OR period_type = %(period_type)s)
              ORDER BY results_date, symbol
              LIMIT %(limit)s
            ),
            hist AS (
              SELECT c.id AS cal_id, e.period_end, e.period_type, e.results_date,
                     e.lag_days, e.date_status,
                     ROW_NUMBER() OVER (PARTITION BY c.id ORDER BY e.period_end DESC) AS rn
              FROM cal c
              JOIN earnings_dates e
                ON e.symbol = c.symbol AND e.exchange = c.exchange
               AND e.is_earnings AND e.period_end IS NOT NULL
               AND e.period_end < c.period_end
              WHERE c.period_end IS NOT NULL
            )
            SELECT
              c.*,
              COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                         'period_end',   h.period_end,
                         'period_type',  h.period_type,
                         'results_date', h.results_date,
                         'lag_days',     h.lag_days,
                         'date_status',  h.date_status)
                       ORDER BY h.period_end DESC)
                FROM hist h WHERE h.cal_id = c.id AND h.rn <= 4
              ), '[]'::jsonb) AS prior_periods,

              jsonb_build_object(
                'value', CASE WHEN yoy.lag_days IS NOT NULL AND c.lag_days IS NOT NULL
                              THEN c.lag_days - yoy.lag_days END,
                'peer_period_end',  yoy.period_end,
                'peer_period_type', yoy.period_type,
                'peer_results_date', yoy.results_date,
                'reason', CASE
                  WHEN c.period_end IS NULL   THEN 'period_unattributed'
                  WHEN yoy.period_end IS NULL THEN 'no_peer'
                  WHEN yoy.period_type <> c.period_type THEN 'cadence_change'
                  ELSE 'ok' END
              ) AS yoy,

              jsonb_build_object(
                'value', CASE
                  WHEN qoq.lag_days IS NOT NULL AND c.lag_days IS NOT NULL
                   AND NOT c.covers_full_year AND NOT qoq.covers_full_year
                   AND qoq.period_type = c.period_type
                   AND c.period_type <> 'H'
                   AND (c.period_end - qoq.period_end) <= {_MAX_QOQ_GAP_DAYS}
                  THEN c.lag_days - qoq.lag_days END,
                'peer_period_end',  qoq.period_end,
                'peer_period_type', qoq.period_type,
                'peer_results_date', qoq.results_date,
                'reason', CASE
                  WHEN c.period_end IS NULL   THEN 'period_unattributed'
                  WHEN qoq.period_end IS NULL THEN 'no_peer'
                  -- Q4/annual is audited (~45-60d lag vs ~15-20d), never comparable to a quarter
                  WHEN c.covers_full_year OR qoq.covers_full_year
                                              THEN 'not_comparable_audit_cycle'
                  WHEN c.period_type = 'H'    THEN 'half_yearly_no_sequential_peer'
                  WHEN qoq.period_type <> c.period_type THEN 'cadence_change'
                  WHEN (c.period_end - qoq.period_end) > {_MAX_QOQ_GAP_DAYS}
                                              THEN 'gap_in_history'
                  ELSE 'ok' END
              ) AS qoq
            FROM cal c
            LEFT JOIN LATERAL (
              -- Exact date arithmetic, not (fiscal_year-1, fiscal_quarter) and not LAG(4): the
              -- row offset varies by cadence and breaks on gaps. The ::date cast keeps the
              -- unique index usable.
              SELECT e.period_end, e.period_type, e.lag_days, e.results_date
              FROM earnings_dates e
              WHERE e.symbol = c.symbol AND e.exchange = c.exchange
                AND e.period_end = (c.period_end - INTERVAL '1 year')::date
                AND e.is_earnings
            ) yoy ON TRUE
            LEFT JOIN LATERAL (
              SELECT e.period_end, e.period_type, e.lag_days, e.results_date,
                     e.covers_full_year
              FROM earnings_dates e
              WHERE e.symbol = c.symbol AND e.exchange = c.exchange
                AND e.is_earnings AND e.period_end IS NOT NULL
                AND e.period_end < c.period_end
              ORDER BY e.period_end DESC
              LIMIT 1
            ) qoq ON TRUE
            ORDER BY c.results_date, c.symbol
            """,
            {
                "from_date": from_date,
                "to_date": to_date,
                "period_type": period_type,
                "limit": limit,
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("get_calendar failed: %s", e)
        return []


def get_attribution_stats(from_date: date, to_date: date) -> list[dict[str, Any]]:
    """period_source/confidence breakdown over a window -- the attribution quality gate."""
    try:
        return fetchall(
            """
            SELECT period_source, period_type, COUNT(*) AS n,
                   MIN(period_confidence) AS min_conf,
                   ROUND(AVG(period_confidence)) AS avg_conf
            FROM earnings_dates
            WHERE is_earnings AND results_date BETWEEN %s AND %s
            GROUP BY period_source, period_type
            ORDER BY n DESC
            """,
            (from_date, to_date),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("get_attribution_stats failed: %s", e)
        return []
