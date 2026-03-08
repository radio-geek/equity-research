-- 004_concall_transcripts: cache NSE concall transcript links and extracted text
-- Avoids re-downloading PDFs on every report run.
-- Reports are invalidated based on stored_at vs report generated_at (not just 24h TTL).

CREATE TABLE IF NOT EXISTS concall_transcripts (
  id              BIGSERIAL PRIMARY KEY,
  symbol          TEXT NOT NULL,
  exchange        TEXT NOT NULL DEFAULT 'NSE',
  segment         TEXT NOT NULL DEFAULT 'equities',   -- 'equities' or 'sme'
  transcript_date TEXT NOT NULL,                       -- NSE an_dt field (e.g. '15-Jan-2025')
  link            TEXT NOT NULL,
  description     TEXT,
  text            TEXT,                                -- NULL = PDF extraction failed; retried on next search
  stored_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (symbol, exchange, transcript_date)           -- safe concurrent upserts
);

CREATE INDEX IF NOT EXISTS idx_ct_symbol ON concall_transcripts (symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_ct_stored_at ON concall_transcripts (symbol, exchange, stored_at DESC);
