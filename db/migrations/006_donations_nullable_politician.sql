-- Migration 006: Allow donations without a matched politician
--
-- Problem: tse.donations.politician_id was NOT NULL, so any donation
-- where cpf_candidato didn't match core.politicians was silently dropped.
-- We want ALL historical donations, matching to politicians where possible.
--
-- Changes:
--   1. Make politician_id nullable
--   2. Add cpf_candidato column (raw CPF from TSE) for future matching
--   3. Add nome_candidato for display when no politician record exists

BEGIN;

ALTER TABLE tse.donations
    ALTER COLUMN politician_id DROP NOT NULL;

ALTER TABLE tse.donations
    ADD COLUMN IF NOT EXISTS cpf_candidato VARCHAR(14),
    ADD COLUMN IF NOT EXISTS nome_candidato VARCHAR(300);

CREATE INDEX IF NOT EXISTS idx_donations_cpf_candidato
    ON tse.donations (cpf_candidato)
    WHERE cpf_candidato IS NOT NULL;

COMMIT;
