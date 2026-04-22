-- Migration 012: Digest feature
-- Creates the auth.digests table to store user-generated AI digests.

CREATE TABLE auth.digests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    label           VARCHAR(300) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'processing',  -- 'processing' | 'completed' | 'failed'
    parameters      JSONB NOT NULL,   -- { deputy_ids, bill_ids, date_range, language, enrichment, model }
    content         JSONB,            -- structured output once complete
    estimated_cost  NUMERIC(10, 6),
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX ON auth.digests (user_id, created_at DESC);
