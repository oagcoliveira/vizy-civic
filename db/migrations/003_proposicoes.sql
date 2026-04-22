-- Migration 003: Proposicoes table and votacao linkage
-- Stores the propositions (bills, requisitions, etc.) affected by each votação.
-- A single votação can affect multiple proposições (e.g. the main PL + an urgency REQ).

CREATE TABLE core.proposicoes (
    id              SERIAL PRIMARY KEY,
    source          VARCHAR(10) NOT NULL,   -- 'camara'
    external_id     INTEGER NOT NULL,
    type            VARCHAR(20),            -- PL, PEC, MPV, REQ, PDL, etc.
    number          INTEGER,
    year            INTEGER,
    title           VARCHAR(200),           -- e.g. "PL 1604/2022"
    ementa          TEXT,
    uri             TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE core.votacao_proposicoes (
    id              SERIAL PRIMARY KEY,
    votacao_id      INTEGER NOT NULL REFERENCES core.votacoes(id) ON DELETE CASCADE,
    proposicao_id   INTEGER NOT NULL REFERENCES core.proposicoes(id) ON DELETE CASCADE,
    is_primary      BOOLEAN DEFAULT FALSE,  -- true for the main bill, false for related ones
    UNIQUE (votacao_id, proposicao_id)
);

CREATE INDEX ON core.votacao_proposicoes (votacao_id);
CREATE INDEX ON core.votacao_proposicoes (proposicao_id);
