-- ═══════════════════════════════════════════════════════════════
-- v2 Migration — Run this AFTER the original supabase_schema.sql
-- Adds: pgvector embeddings, quality columns, search function
-- Run in Supabase SQL Editor: supabase.com → project → SQL Editor
-- ═══════════════════════════════════════════════════════════════

-- 1. Enable pgvector extension (free on all Supabase plans)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add v2 columns to existing reports table
ALTER TABLE reports ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS quality_score INTEGER DEFAULT 0;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS revision_count INTEGER DEFAULT 0;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'standard';

-- 3. Create index for fast similarity search
CREATE INDEX IF NOT EXISTS reports_embedding_idx
  ON reports USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 10);

-- 4. Create the similarity search RPC function
CREATE OR REPLACE FUNCTION search_similar_reports(
  query_embedding vector(384),
  similarity_threshold float DEFAULT 0.85,
  match_count int DEFAULT 3
)
RETURNS TABLE (
  id UUID,
  topic TEXT,
  final_report TEXT,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    r.id,
    r.topic,
    r.final_report,
    1 - (r.embedding <=> query_embedding) AS similarity
  FROM reports r
  WHERE r.embedding IS NOT NULL
    AND 1 - (r.embedding <=> query_embedding) > similarity_threshold
  ORDER BY r.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- 5. Grant permissions (Supabase uses anon/authenticated roles)
GRANT EXECUTE ON FUNCTION search_similar_reports TO anon, authenticated;
