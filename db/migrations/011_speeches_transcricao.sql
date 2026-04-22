-- Migration 011: Add transcricao column to core.speeches
--
-- The Câmara API returns a 'transcricao' field in the /deputados/{id}/discursos
-- endpoint containing the verbatim speech transcript. This column stores it so
-- that AI enrichment can summarise the actual speech content rather than the
-- bureaucratic 'phase' label.
--
-- Applied to production on 2026-04-22 via Manus.

ALTER TABLE core.speeches ADD COLUMN IF NOT EXISTS transcricao TEXT;
