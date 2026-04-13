-- Migration 007: Add unique constraint to core.legislative_events(bill_id, sequence)
-- Needed for ETL upserts on bills_tramitacoes_daily.

ALTER TABLE core.legislative_events
    ADD CONSTRAINT legislative_events_bill_sequence_uniq
    UNIQUE (bill_id, sequence);
