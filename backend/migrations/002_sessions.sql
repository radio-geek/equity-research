-- DB-backed sessions: each login creates a session row.
-- JWT carries the session id (jti claim); logout revokes it server-side.
-- Run: psql -U postgres -d equity_research -f backend/migrations/002_sessions.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

CREATE TABLE IF NOT EXISTS sessions (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_revoked ON sessions (expires_at, revoked);
