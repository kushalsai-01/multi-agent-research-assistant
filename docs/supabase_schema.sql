-- Run this in your Supabase SQL editor (supabase.com → your project → SQL Editor)

CREATE TABLE IF NOT EXISTS reports (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic        TEXT NOT NULL,
  final_report TEXT,
  raw_research TEXT,
  analysis     TEXT,
  session_id   TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- Optional: index for faster ordering by date
CREATE INDEX IF NOT EXISTS reports_created_at_idx ON reports (created_at DESC);
CREATE INDEX IF NOT EXISTS reports_session_created_at_idx ON reports (session_id, created_at DESC);
