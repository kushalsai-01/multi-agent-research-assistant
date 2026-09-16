ALTER TABLE reports ADD COLUMN IF NOT EXISTS session_id TEXT;

UPDATE reports
SET session_id = 'legacy'
WHERE session_id IS NULL;

ALTER TABLE reports ALTER COLUMN session_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS reports_session_created_at_idx
ON reports (session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_sessions (
  session_id TEXT PRIMARY KEY,
  queries JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
