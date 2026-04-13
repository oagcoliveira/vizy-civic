-- Add unique constraints to committee tables to support upserts in the commissions ETL.
ALTER TABLE core.committees
    ADD CONSTRAINT committees_source_extid_uniq UNIQUE (source, external_id);

ALTER TABLE core.committee_memberships
    ADD CONSTRAINT committee_memberships_pol_comm_uniq UNIQUE (politician_id, committee_id);
