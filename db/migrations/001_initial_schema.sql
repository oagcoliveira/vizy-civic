-- Vizy — Initial Schema
-- Run order: 001 → 002
-- PostgreSQL 16

-- Schemas
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS tse;
CREATE SCHEMA IF NOT EXISTS jobs;

-- ─────────────────────────────────────────
-- core.legislatures
-- ─────────────────────────────────────────
CREATE TABLE core.legislatures (
    id          SERIAL PRIMARY KEY,
    number      INTEGER NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE,
    chamber     VARCHAR(10) NOT NULL,  -- 'camara' | 'senado'
    UNIQUE (number, chamber)
);

-- ─────────────────────────────────────────
-- core.parties
-- ─────────────────────────────────────────
CREATE TABLE core.parties (
    id          SERIAL PRIMARY KEY,
    acronym     VARCHAR(20) UNIQUE NOT NULL,
    name        VARCHAR(200) NOT NULL,
    ideology    VARCHAR(50),
    website_url TEXT,
    logo_url    TEXT,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────
-- core.politicians
-- ─────────────────────────────────────────
CREATE TABLE core.politicians (
    id                      SERIAL PRIMARY KEY,
    source                  VARCHAR(10) NOT NULL,   -- 'camara' | 'senado'
    external_id             INTEGER NOT NULL,
    name                    VARCHAR(200) NOT NULL,
    short_name              VARCHAR(100),
    cpf                     VARCHAR(14),
    photo_url               TEXT,
    gender                  CHAR(1),
    birth_date              DATE,
    education               VARCHAR(100),
    email                   VARCHAR(200),
    website_url             TEXT,
    party_id                INTEGER REFERENCES core.parties(id),
    state                   CHAR(2),
    current_office          VARCHAR(20),            -- 'deputado' | 'senador'
    current_legislature_id  INTEGER REFERENCES core.legislatures(id),
    is_active               BOOLEAN DEFAULT TRUE,
    ai_bio                  TEXT,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, external_id)
);

-- ─────────────────────────────────────────
-- core.bills
-- ─────────────────────────────────────────
CREATE TABLE core.bills (
    id                      SERIAL PRIMARY KEY,
    source                  VARCHAR(10) NOT NULL,
    external_id             INTEGER NOT NULL,
    type                    VARCHAR(10) NOT NULL,   -- PL, PEC, MPV, PDL …
    number                  INTEGER NOT NULL,
    year                    INTEGER NOT NULL,
    title                   TEXT NOT NULL,
    short_title             VARCHAR(300),
    summary                 TEXT,
    full_text_url           TEXT,
    author_politician_id    INTEGER REFERENCES core.politicians(id),
    author_label            VARCHAR(200),
    status                  VARCHAR(50),
    policy_area             VARCHAR(100),
    policy_tags             TEXT[],
    is_controversial        BOOLEAN,
    legislature_id          INTEGER REFERENCES core.legislatures(id),
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, external_id)
);

-- ─────────────────────────────────────────
-- core.legislative_events (tramitação)
-- ─────────────────────────────────────────
CREATE TABLE core.legislative_events (
    id          SERIAL PRIMARY KEY,
    bill_id     INTEGER NOT NULL REFERENCES core.bills(id),
    sequence    INTEGER NOT NULL,
    event_date  DATE,
    stage       VARCHAR(200),
    description TEXT,
    summary     TEXT,
    venue       VARCHAR(200),
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────
-- core.votacoes
-- ─────────────────────────────────────────
CREATE TABLE core.votacoes (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(10) NOT NULL,
    external_id         VARCHAR(100) NOT NULL,
    bill_id             INTEGER REFERENCES core.bills(id),
    description         TEXT,
    voted_at            TIMESTAMPTZ,
    vote_type           VARCHAR(20),    -- 'nominal' | 'simbolica' | 'secreta'
    result              VARCHAR(50),
    yes_count           INTEGER,
    no_count            INTEGER,
    abstention_count    INTEGER,
    session_label       VARCHAR(200),
    legislature_id      INTEGER REFERENCES core.legislatures(id),
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, external_id)
);

-- ─────────────────────────────────────────
-- core.individual_votes
-- ─────────────────────────────────────────
CREATE TABLE core.individual_votes (
    id                  SERIAL PRIMARY KEY,
    votacao_id          INTEGER NOT NULL REFERENCES core.votacoes(id),
    politician_id       INTEGER NOT NULL REFERENCES core.politicians(id),
    vote                VARCHAR(20) NOT NULL,   -- Sim | Não | Abstenção | Obstrução | Artigo 17
    party_at_time       VARCHAR(20),
    party_orientation   VARCHAR(20),
    followed_orientation BOOLEAN,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (votacao_id, politician_id)
);

-- ─────────────────────────────────────────
-- core.speeches
-- ─────────────────────────────────────────
CREATE TABLE core.speeches (
    id              SERIAL PRIMARY KEY,
    source          VARCHAR(10) NOT NULL,
    external_id     VARCHAR(100) NOT NULL,
    politician_id   INTEGER NOT NULL REFERENCES core.politicians(id),
    delivered_at    TIMESTAMPTZ,
    phase           VARCHAR(100),
    summary         TEXT,
    full_text_url   TEXT,
    keywords        TEXT[],
    policy_tags     TEXT[],
    sentiment       VARCHAR(20),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, external_id)
);

-- ─────────────────────────────────────────
-- core.committees
-- ─────────────────────────────────────────
CREATE TABLE core.committees (
    id          SERIAL PRIMARY KEY,
    source      VARCHAR(10) NOT NULL,
    external_id VARCHAR(50),
    acronym     VARCHAR(20),
    name        VARCHAR(300) NOT NULL,
    type        VARCHAR(30),    -- 'permanente' | 'especial' | 'CPI'
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE
);

-- ─────────────────────────────────────────
-- core.committee_memberships
-- ─────────────────────────────────────────
CREATE TABLE core.committee_memberships (
    id              SERIAL PRIMARY KEY,
    politician_id   INTEGER NOT NULL REFERENCES core.politicians(id),
    committee_id    INTEGER NOT NULL REFERENCES core.committees(id),
    role            VARCHAR(50),    -- 'Titular' | 'Suplente' | 'Presidente' | 'Relator'
    started_at      DATE,
    ended_at        DATE
);

-- ─────────────────────────────────────────
-- tse.donors
-- ─────────────────────────────────────────
CREATE TABLE tse.donors (
    id              SERIAL PRIMARY KEY,
    cpf_cnpj_masked VARCHAR(18) NOT NULL,
    name            VARCHAR(300) NOT NULL,
    donor_type      VARCHAR(20) NOT NULL,   -- 'individual' | 'company'
    state           CHAR(2),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────
-- tse.donations
-- ─────────────────────────────────────────
CREATE TABLE tse.donations (
    id              SERIAL PRIMARY KEY,
    donor_id        INTEGER NOT NULL REFERENCES tse.donors(id),
    politician_id   INTEGER NOT NULL REFERENCES core.politicians(id),
    election_year   INTEGER NOT NULL,
    amount_brl      NUMERIC(12,2) NOT NULL,
    receipt_date    DATE,
    source_type     VARCHAR(100),
    office_sought   VARCHAR(50),
    state           CHAR(2),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────
-- auth.users
-- ─────────────────────────────────────────
CREATE TABLE auth.users (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR(300) UNIQUE NOT NULL,
    name                VARCHAR(200) NOT NULL,
    password_hash       TEXT NOT NULL,
    is_verified         BOOLEAN DEFAULT FALSE,
    digest_frequency    VARCHAR(20) DEFAULT 'weekly',
    digest_day          VARCHAR(10) DEFAULT 'friday',
    created_at          TIMESTAMPTZ DEFAULT now(),
    last_login_at       TIMESTAMPTZ
);

-- ─────────────────────────────────────────
-- auth.politician_follows
-- ─────────────────────────────────────────
CREATE TABLE auth.politician_follows (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    politician_id   INTEGER NOT NULL REFERENCES core.politicians(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, politician_id)
);

-- ─────────────────────────────────────────
-- auth.bill_tracks
-- ─────────────────────────────────────────
CREATE TABLE auth.bill_tracks (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    bill_id     INTEGER NOT NULL REFERENCES core.bills(id),
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, bill_id)
);

-- ─────────────────────────────────────────
-- auth.tag_follows
-- ─────────────────────────────────────────
CREATE TABLE auth.tag_follows (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tag         VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, tag)
);

-- ─────────────────────────────────────────
-- jobs.etl_runs
-- ─────────────────────────────────────────
CREATE TABLE jobs.etl_runs (
    id                  SERIAL PRIMARY KEY,
    job_name            VARCHAR(100) NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    status              VARCHAR(20) NOT NULL,   -- 'success' | 'partial' | 'failed'
    records_fetched     INTEGER DEFAULT 0,
    records_inserted    INTEGER DEFAULT 0,
    records_updated     INTEGER DEFAULT 0,
    error_message       TEXT,
    params              JSONB
);

-- Seed current legislature
INSERT INTO core.legislatures (number, start_date, end_date, chamber)
VALUES
    (57, '2023-02-01', '2027-01-31', 'camara'),
    (57, '2023-02-01', '2027-01-31', 'senado');
