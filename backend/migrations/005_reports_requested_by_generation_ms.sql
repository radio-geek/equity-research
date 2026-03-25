-- Optional cache metadata for reports (user who triggered generation, timing).
-- Run after 001_init.sql (and other migrations as you already apply):
--   psql -U postgres -d equity_research -f backend/migrations/005_reports_requested_by_generation_ms.sql

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'reports' AND column_name = 'requested_by'
  ) THEN
    ALTER TABLE reports
      ADD COLUMN requested_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'reports' AND column_name = 'generation_ms'
  ) THEN
    ALTER TABLE reports ADD COLUMN generation_ms INTEGER;
  END IF;
END $$;

COMMENT ON COLUMN reports.requested_by IS 'User id who last requested this cached report; NULL for anonymous/CLI.';
COMMENT ON COLUMN reports.generation_ms IS 'Wall-clock time to generate the report payload in milliseconds.';
