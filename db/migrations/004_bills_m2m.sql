-- Migration 004: Consolidate core.proposicoes into core.bills + M:M junction
-- Prerequisite: proposicoes_backfill.py must have completed.
--
-- Steps:
--   1. Relax NOT NULL constraints on core.bills (proposicoes data has nullable fields)
--   2. Add ementa column to core.bills
--   3. Migrate core.proposicoes rows into core.bills
--   4. Create core.votacao_bills (M:M junction, replaces core.votacao_proposicoes)
--   5. Migrate linkage data
--   6. Drop retired tables (core.votacao_proposicoes, core.proposicoes)
--   7. Drop the now-unused singular bill_id FK from core.votacoes

BEGIN;

-- 1. Relax NOT NULL constraints
ALTER TABLE core.bills ALTER COLUMN type DROP NOT NULL;
ALTER TABLE core.bills ALTER COLUMN number DROP NOT NULL;
ALTER TABLE core.bills ALTER COLUMN year DROP NOT NULL;
ALTER TABLE core.bills ALTER COLUMN title DROP NOT NULL;

-- 2. Add ementa column (raw text from API before AI summary is generated)
ALTER TABLE core.bills ADD COLUMN IF NOT EXISTS ementa TEXT;

-- 3. Migrate proposicoes → bills
INSERT INTO core.bills (source, external_id, type, number, year, title, ementa, full_text_url)
SELECT
    source,
    external_id,
    type,
    number,
    year,
    COALESCE(title, ementa, 'Sem título'),
    ementa,
    uri
FROM core.proposicoes
ON CONFLICT (source, external_id) DO NOTHING;

-- 4. Create M:M junction table
CREATE TABLE core.votacao_bills (
    id          SERIAL PRIMARY KEY,
    votacao_id  INTEGER NOT NULL REFERENCES core.votacoes(id) ON DELETE CASCADE,
    bill_id     INTEGER NOT NULL REFERENCES core.bills(id) ON DELETE CASCADE,
    is_primary  BOOLEAN DEFAULT FALSE,
    UNIQUE (votacao_id, bill_id)
);

CREATE INDEX ON core.votacao_bills (votacao_id);
CREATE INDEX ON core.votacao_bills (bill_id);

-- 5. Migrate linkage data
INSERT INTO core.votacao_bills (votacao_id, bill_id, is_primary)
SELECT vp.votacao_id, b.id, vp.is_primary
FROM core.votacao_proposicoes vp
JOIN core.proposicoes p ON p.id = vp.proposicao_id
JOIN core.bills b ON b.source = p.source AND b.external_id = p.external_id;

-- 6. Drop retired tables
DROP TABLE core.votacao_proposicoes;
DROP TABLE core.proposicoes;

-- 7. Drop the old singular FK (never populated, replaced by M:M)
ALTER TABLE core.votacoes DROP COLUMN IF EXISTS bill_id;

COMMIT;
