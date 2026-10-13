-- Trade journal: personal buy/sell entries with thesis per user
CREATE TABLE IF NOT EXISTS trade_journal (
  id         BIGSERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  symbol     TEXT NOT NULL,
  action     TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
  trade_date DATE NOT NULL,
  thesis     TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_user_id     ON trade_journal (user_id);
CREATE INDEX IF NOT EXISTS idx_trade_journal_user_symbol ON trade_journal (user_id, symbol);
