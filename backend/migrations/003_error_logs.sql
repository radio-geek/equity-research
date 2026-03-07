-- Error logs table: one table for all error types, queryable by node
CREATE TABLE IF NOT EXISTS error_logs (
  id          BIGSERIAL PRIMARY KEY,
  node        TEXT        NOT NULL,          -- e.g. 'report_generate', 'auth_signin', 'pdf_download', 'env_load'
  message     TEXT        NOT NULL,          -- human-readable error message
  detail      TEXT,                          -- stack trace or extra context (optional)
  symbol      TEXT,                          -- NSE/BSE symbol if applicable
  user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS error_logs_node_idx       ON error_logs (node);
CREATE INDEX IF NOT EXISTS error_logs_created_at_idx ON error_logs (created_at DESC);
