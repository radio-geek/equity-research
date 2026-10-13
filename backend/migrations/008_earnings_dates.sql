-- 008_earnings_dates: NSE board-meeting intimations -> earnings date calendar.
--
-- Two tables by design:
--   board_meeting_intimations = raw append-mostly source log, keyed on the NSE natural key.
--                               Lets attribution be re-run over all history without re-fetching.
--   earnings_dates            = derived projection, one row per (symbol, period_end).
--
-- NOTE: run_migrations.py re-executes every .sql file on each invocation inside a single
-- implicit transaction, so every object here must be IF NOT EXISTS and CONCURRENTLY is illegal.

CREATE TABLE IF NOT EXISTS board_meeting_intimations (
  id            BIGSERIAL PRIMARY KEY,
  symbol        TEXT NOT NULL,
  exchange      TEXT NOT NULL DEFAULT 'NSE',
  segment       TEXT NOT NULL DEFAULT 'equities',   -- 'equities' or 'sme'; predicts filing cadence
  company_name  TEXT,
  isin          TEXT,
  bm_date       DATE NOT NULL,                      -- intimated meeting (= results) date
  purpose       TEXT NOT NULL DEFAULT '',           -- bm_purpose; '' not NULL so it can key
  description   TEXT,                               -- bm_desc verbatim; the reparse source
  -- NSE sends '01-Oct-2026 12:37:30' with no timezone. Stored as wall clock (IST).
  -- Deliberately TIMESTAMP, not TIMESTAMPTZ: the latter lands 5h30m off on a UTC server.
  announced_at  TIMESTAMP,
  attachment    TEXT,
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (symbol, exchange, bm_date, purpose, announced_at)
);

CREATE INDEX IF NOT EXISTS idx_bmi_symbol_announced
  ON board_meeting_intimations (symbol, exchange, announced_at DESC);

CREATE TABLE IF NOT EXISTS earnings_dates (
  id            BIGSERIAL PRIMARY KEY,
  symbol        TEXT NOT NULL,
  exchange      TEXT NOT NULL DEFAULT 'NSE',
  segment       TEXT NOT NULL DEFAULT 'equities',
  company_name  TEXT,
  isin          TEXT,

  -- Period attribution. All nullable: NULL = an earnings event we could not attribute.
  -- period_type must NOT default to 'Q' -- never force a low-confidence guess into identity.
  period_end       DATE,
  period_type      TEXT CHECK (period_type IN ('Q', 'H', '9M', 'FY')),
  covers_full_year BOOLEAN NOT NULL DEFAULT false,  -- 'quarter and year ended Mar 31' = ONE row

  CONSTRAINT ed_period_end_is_quarter_end CHECK (
    period_end IS NULL OR (
      date_part('month', period_end) IN (3, 6, 9, 12)
      AND period_end = (date_trunc('month', period_end)
                        + INTERVAL '1 month' - INTERVAL '1 day')::date
    )
  ),
  CONSTRAINT ed_period_type_requires_end CHECK (
    (period_end IS NULL) = (period_type IS NULL)
  ),

  -- Year-ending, 4-digit, matching src/data/indian_quarters.py (FY26 = Apr 2025-Mar 2026 -> 2026).
  -- Generated so they can never drift from period_end. Render as FY{fiscal_year % 100} at the API.
  fiscal_year    SMALLINT GENERATED ALWAYS AS (
    (date_part('year', period_end)
     + CASE WHEN date_part('month', period_end) > 3 THEN 1 ELSE 0 END)::smallint
  ) STORED,
  fiscal_quarter SMALLINT GENERATED ALWAYS AS (
    (CASE date_part('month', period_end)
       WHEN 6 THEN 1 WHEN 9 THEN 2 WHEN 12 THEN 3 WHEN 3 THEN 4 END)::smallint
  ) STORED,

  -- Three distinct date concepts: the original promise, the current promise, the confirmed fact.
  intimated_date       DATE NOT NULL,
  first_intimated_date DATE NOT NULL,   -- set on insert, never updated: a moved date is a signal
  actual_results_date  DATE,            -- NULL until a second source confirms publication
  results_date         DATE GENERATED ALWAYS AS (
    COALESCE(actual_results_date, intimated_date)
  ) STORED,
  date_status    TEXT NOT NULL DEFAULT 'intimated'
    CHECK (date_status IN ('intimated', 'confirmed', 'revised', 'deferred', 'cancelled')),
  revision_count SMALLINT NOT NULL DEFAULT 0,

  lag_days      INTEGER GENERATED ALWAYS AS (
    COALESCE(actual_results_date, intimated_date) - period_end
  ) STORED,

  CONSTRAINT ed_results_after_period CHECK (
    period_end IS NULL
    OR COALESCE(actual_results_date, intimated_date) > period_end
  ),
  -- SEBI Reg 33 allows 45 days quarterly / 60 days annual; these bounds are those plus slack.
  -- A loose bound is dangerous: it admits a period attributed a full year wrong, which would
  -- silently make the YoY peer the current period.
  CONSTRAINT ed_lag_sane CHECK (
    period_end IS NULL
    OR (COALESCE(actual_results_date, intimated_date) - period_end)
       <= CASE WHEN covers_full_year THEN 210 ELSE 180 END
  ),

  -- Fund Raising / Other business matters are not earnings events and must not claim a
  -- period slot, or they block the real financial-results intimation for that quarter.
  is_earnings   BOOLEAN NOT NULL DEFAULT true,
  purpose       TEXT,
  description   TEXT,
  attachment    TEXT,

  period_source     TEXT CHECK (period_source IN
                      ('text_explicit', 'text_partial', 'proximity', 'manual')),
  period_confidence SMALLINT CHECK (period_confidence BETWEEN 0 AND 100),
  attribution_note  TEXT,   -- e.g. 'text/prox disagree prox=2025-09-30'

  source_intimation_id BIGINT REFERENCES board_meeting_intimations(id) ON DELETE SET NULL,
  announced_at  TIMESTAMP,
  stored_at     TIMESTAMPTZ NOT NULL DEFAULT now(),   -- first-seen; never touched on update
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Natural key: a company reports a given period-end once. Collapses the Q4+FY dual filing into
-- one row, and makes a half-yearly -> quarterly cadence switch an attribute update rather than
-- a duplicate row. Serves the YoY equality lookup, the QoQ backward range scan, and the
-- last-N-periods scan, so no separate period_end DESC index is needed.
CREATE UNIQUE INDEX IF NOT EXISTS uq_earnings_dates_period
  ON earnings_dates (symbol, exchange, period_end)
  WHERE period_end IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_earnings_dates_unattributed
  ON earnings_dates (symbol, exchange, intimated_date, source_intimation_id)
  WHERE period_end IS NULL;

CREATE INDEX IF NOT EXISTS idx_earnings_dates_calendar
  ON earnings_dates (results_date, symbol)
  WHERE is_earnings;
