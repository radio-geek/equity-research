-- Add optional session metadata columns expected by backend/auth.py create_session().
-- Run if you already applied 002_sessions.sql before these columns existed:
--   psql -U postgres -d equity_research -f backend/migrations/003_sessions_ip_user_agent.sql

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'sessions' AND column_name = 'ip_address'
  ) THEN
    ALTER TABLE sessions ADD COLUMN ip_address TEXT;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'sessions' AND column_name = 'user_agent'
  ) THEN
    ALTER TABLE sessions ADD COLUMN user_agent TEXT;
  END IF;
END $$;
