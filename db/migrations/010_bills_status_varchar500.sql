-- Migration 010: Widen core.bills.status from VARCHAR(50) to VARCHAR(500)
--
-- The Câmara API returns status strings that can exceed 50 characters
-- (e.g. "Aguardando Designação - Aguardando Devolução de Relator(a) que
-- deixou de ser Membro" = 83 chars), causing StringDataRightTruncation
-- errors in the camara_bills_daily ETL job.
--
-- Applied to production on 2026-04-22 via Manus.

ALTER TABLE core.bills ALTER COLUMN status TYPE VARCHAR(500);
