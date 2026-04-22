-- Migration 005: Fix donations schema for correct deduplication
--
-- Problems fixed:
--   1. tse.donors had no unique constraint → ON CONFLICT DO NOTHING was a no-op,
--      causing duplicate donors on repeated loads.
--   2. Add cpf_cnpj_raw for internal deduplication (never exposed to frontend).
--   3. Add index on core.politicians.cpf for fast donor→politician matching.

BEGIN;

-- Add raw CPF/CNPJ column for deduplication (internal only, never served to API)
ALTER TABLE tse.donors ADD COLUMN IF NOT EXISTS cpf_cnpj_raw VARCHAR(20);

-- Unique on the raw identifier so ON CONFLICT works correctly
-- NULL values are excluded from uniqueness (for rows with no CPF — unusual but possible)
CREATE UNIQUE INDEX IF NOT EXISTS idx_donors_cpf_raw
    ON tse.donors (cpf_cnpj_raw)
    WHERE cpf_cnpj_raw IS NOT NULL;

-- Index for fast politician matching
CREATE INDEX IF NOT EXISTS idx_politicians_cpf
    ON core.politicians (cpf)
    WHERE cpf IS NOT NULL;

COMMIT;
