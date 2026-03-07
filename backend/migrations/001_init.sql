-- Equity Research DB schema
-- Run: psql -U postgres -d equity_research -f backend/migrations/001_init.sql

CREATE TABLE IF NOT EXISTS users (
  id          SERIAL PRIMARY KEY,
  google_id   TEXT UNIQUE NOT NULL,
  email       TEXT UNIQUE NOT NULL,
  name        TEXT,
  picture     TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  last_login  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reports (
  id           SERIAL PRIMARY KEY,
  symbol       TEXT NOT NULL,
  exchange     TEXT NOT NULL DEFAULT 'NSE',
  payload      JSONB NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  expires_at   TIMESTAMPTZ NOT NULL,
  UNIQUE (symbol, exchange)
);

CREATE INDEX IF NOT EXISTS idx_reports_symbol_exchange ON reports (symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_reports_expires_at ON reports (expires_at);

CREATE TABLE IF NOT EXISTS feedback (
  id         SERIAL PRIMARY KEY,
  report_id  TEXT NOT NULL,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  rating     TEXT NOT NULL CHECK (rating IN ('up', 'down')),
  comment    TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_report_id ON feedback (report_id);
