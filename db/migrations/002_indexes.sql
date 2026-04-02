-- Vizy — Performance Indexes
-- Run after 001_initial_schema.sql

-- Politicians
CREATE INDEX idx_politicians_source_ext ON core.politicians (source, external_id);
CREATE INDEX idx_politicians_state ON core.politicians (state);
CREATE INDEX idx_politicians_party ON core.politicians (party_id);
CREATE INDEX idx_politicians_active ON core.politicians (is_active) WHERE is_active = TRUE;

-- Bills
CREATE INDEX idx_bills_source_ext ON core.bills (source, external_id);
CREATE INDEX idx_bills_policy_area ON core.bills (policy_area);
CREATE INDEX idx_bills_status ON core.bills (status);
CREATE INDEX idx_bills_year ON core.bills (year DESC);
CREATE INDEX idx_bills_author ON core.bills (author_politician_id);
CREATE INDEX idx_bills_updated ON core.bills (updated_at DESC);

-- Individual votes (high-traffic queries)
CREATE INDEX idx_individual_votes_politician ON core.individual_votes (politician_id);
CREATE INDEX idx_individual_votes_votacao ON core.individual_votes (votacao_id);
CREATE INDEX idx_individual_votes_politician_time
    ON core.individual_votes (politician_id, votacao_id DESC);

-- Votacoes
CREATE INDEX idx_votacoes_voted_at ON core.votacoes (voted_at DESC);
CREATE INDEX idx_votacoes_bill ON core.votacoes (bill_id);

-- Speeches
CREATE INDEX idx_speeches_politician ON core.speeches (politician_id);
CREATE INDEX idx_speeches_politician_time ON core.speeches (politician_id, delivered_at DESC);
CREATE INDEX idx_speeches_delivered_at ON core.speeches (delivered_at DESC);

-- Legislative events
CREATE INDEX idx_leg_events_bill ON core.legislative_events (bill_id, event_date DESC);

-- Donations
CREATE INDEX idx_donations_politician_year ON tse.donations (politician_id, election_year);
CREATE INDEX idx_donations_donor ON tse.donations (donor_id);

-- Auth / feed construction
CREATE INDEX idx_politician_follows_user ON auth.politician_follows (user_id);
CREATE INDEX idx_bill_tracks_user ON auth.bill_tracks (user_id);

-- Full-text search
ALTER TABLE core.politicians
    ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (to_tsvector('portuguese', coalesce(name, '') || ' ' || coalesce(short_name, ''))) STORED;
CREATE INDEX idx_politicians_fts ON core.politicians USING GIN (fts);

ALTER TABLE core.bills
    ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (to_tsvector('portuguese', coalesce(short_title, '') || ' ' || coalesce(title, ''))) STORED;
CREATE INDEX idx_bills_fts ON core.bills USING GIN (fts);

ALTER TABLE core.speeches
    ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (to_tsvector('portuguese', coalesce(summary, ''))) STORED;
CREATE INDEX idx_speeches_fts ON core.speeches USING GIN (fts);
