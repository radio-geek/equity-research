-- =============================================================================
-- Equity Research — Full Database Setup Script
-- =============================================================================
-- Run locally:
--   psql -U postgres -d equity_research -f backend/setup_db.sql
--
-- Run on Neon / Supabase / Railway (via their SQL editor or CLI):
--   Paste this entire file and execute.
--
-- For a fresh local setup:
--   createdb equity_research
--   psql -U postgres -d equity_research -f backend/setup_db.sql
--
-- For a non-superuser (e.g. equity_app), replace the GRANT lines at the bottom
-- with your actual username.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- for gen_random_uuid() used by sessions


-- ---------------------------------------------------------------------------
-- TABLE: users
-- One row per Google-authenticated user.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id          SERIAL PRIMARY KEY,
  google_id   TEXT UNIQUE NOT NULL,
  email       TEXT UNIQUE NOT NULL,
  name        TEXT,
  picture     TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  last_login  TIMESTAMPTZ DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- TABLE: sessions
-- DB-backed sessions; each login creates a row.
-- JWT carries the session id (jti claim); logout revokes it server-side.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id        ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_revoked ON sessions (expires_at, revoked);


-- ---------------------------------------------------------------------------
-- TABLE: reports
-- Cached report payloads (JSON). One row per symbol+exchange.
-- Report is regenerated only when a new concall transcript appears.
-- ---------------------------------------------------------------------------
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
CREATE INDEX IF NOT EXISTS idx_reports_expires_at      ON reports (expires_at);


-- ---------------------------------------------------------------------------
-- TABLE: concall_transcripts
-- Cached NSE concall transcript links and extracted PDF text.
-- Avoids re-downloading PDFs on every report run.
-- text = NULL means PDF extraction failed; it will be retried on next run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS concall_transcripts (
  id              BIGSERIAL PRIMARY KEY,
  symbol          TEXT NOT NULL,
  exchange        TEXT NOT NULL DEFAULT 'NSE',
  segment         TEXT NOT NULL DEFAULT 'equities',   -- 'equities' or 'sme'
  transcript_date TEXT NOT NULL,                       -- NSE an_dt field (e.g. '15-Jan-2025 00:00:00')
  link            TEXT NOT NULL,
  description     TEXT,
  text            TEXT,                                -- NULL = extraction failed, retried on next search
  stored_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (symbol, exchange, transcript_date)           -- safe concurrent upserts (ON CONFLICT DO NOTHING)
);

CREATE INDEX IF NOT EXISTS idx_ct_symbol    ON concall_transcripts (symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_ct_stored_at ON concall_transcripts (symbol, exchange, stored_at DESC);


-- ---------------------------------------------------------------------------
-- TABLE: feedback
-- Thumbs up/down ratings on reports, with optional comment.
-- user_id is nullable (anonymous feedback allowed).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
  id         SERIAL PRIMARY KEY,
  report_id  TEXT NOT NULL,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  rating     TEXT NOT NULL CHECK (rating IN ('up', 'down')),
  comment    TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_report_id ON feedback (report_id);


-- ---------------------------------------------------------------------------
-- TABLE: section_feedback
-- Per-section star ratings (1-5) and optional suggestion text on reports.
-- section_ratings is a JSONB object: { "section_name": rating_int, ... }
-- user_id is nullable (anonymous allowed).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS section_feedback (
  id               BIGSERIAL PRIMARY KEY,
  symbol           TEXT NOT NULL,
  user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
  section_ratings  JSONB NOT NULL DEFAULT '{}',
  suggestion       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_section_feedback_symbol  ON section_feedback (symbol);
CREATE INDEX IF NOT EXISTS idx_section_feedback_user_id ON section_feedback (user_id);


-- ---------------------------------------------------------------------------
-- TABLE: pdf_downloads
-- One row per PDF download attempt — tracks requested / success / failed.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pdf_downloads (
  id            BIGSERIAL PRIMARY KEY,
  symbol        TEXT        NOT NULL,
  user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  status        TEXT        NOT NULL CHECK (status IN ('requested', 'success', 'failed')),
  error_detail  TEXT,
  duration_ms   INTEGER,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pdf_downloads_symbol     ON pdf_downloads (symbol);
CREATE INDEX IF NOT EXISTS idx_pdf_downloads_user_id    ON pdf_downloads (user_id);
CREATE INDEX IF NOT EXISTS idx_pdf_downloads_created_at ON pdf_downloads (created_at DESC);


-- ---------------------------------------------------------------------------
-- TABLE: error_logs
-- Application-level errors from all pipeline nodes.
-- node = identifier like 'report_generate', 'auth_signin', 'pdf_download'
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS error_logs (
  id          BIGSERIAL PRIMARY KEY,
  node        TEXT        NOT NULL,
  message     TEXT        NOT NULL,
  detail      TEXT,                      -- stack trace or extra context
  symbol      TEXT,                      -- NSE/BSE symbol if applicable
  user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_error_logs_node       ON error_logs (node);
CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs (created_at DESC);


-- ---------------------------------------------------------------------------
-- GRANTS (optional — only needed if using a non-superuser app account)
-- Replace 'equity_app' with your actual DB username.
-- On Neon/Supabase this is usually not required (your connection user owns the DB).
-- ---------------------------------------------------------------------------
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO equity_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO equity_app;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO equity_app;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO equity_app;


-- ---------------------------------------------------------------------------
-- Done. Tables created:
--   users, sessions, reports, concall_transcripts, feedback, section_feedback, error_logs
-- ---------------------------------------------------------------------------
