# Vizy

Vizy is a data-aggregation, AI-enrichment, and publishing platform that makes Brazilian legislative and electoral data accessible to citizens.

It collects raw data from government sources (Câmara dos Deputados, Senado Federal, TSE), enriches it with AI-generated summaries and topic tags via the Claude API, and surfaces it through a web application and weekly email digests.

---

## Architecture

```
External Sources (Câmara API, Senado API, Base dos Dados / TSE)
        ↓
ETL Layer  — Python cron workers + Manus (bulk/historical loads)
        ↓
PostgreSQL — Core data store (core, tse, auth, jobs schemas)
        ↓
   ┌─────────────────────────────────┐
   │ Processing Layer                │     Application Layer
   │ AI enrichment (Claude Sonnet)   │  →  FastAPI (REST API)
   │ Topic tagging, summaries        │  →  Next.js 14 (frontend)
   └─────────────────────────────────┘     Redis (cache)
        ↓
Delivery Layer — Weekly email digests via Resend
```

## Tech Stack

| Layer         | Technology                          |
|---------------|-------------------------------------|
| Database      | PostgreSQL 16                       |
| Backend API   | FastAPI (Python 3.11)               |
| Frontend      | Next.js 14 (React, TypeScript)      |
| ETL           | Python 3.11 (`httpx`, `pandas`)     |
| AI enrichment | Claude API (Sonnet)                 |
| Cache         | Redis via Upstash                   |
| Email         | Resend                              |
| Hosting       | Railway                             |
| Bulk ETL      | Manus (historical loads, TSE CSVs)  |

---

## Repository Structure

```
vizy-civic/
├── backend/        FastAPI REST API
├── frontend/       Next.js 14 web app
├── etl/            Python ETL workers (incremental cron jobs)
├── db/             PostgreSQL migrations
└── docs/           Architecture & data source notes
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- Redis

### Environment variables

Copy `.env.example` to `.env` in each sub-project and fill in values.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### ETL

```bash
cd etl
pip install -r requirements.txt
python -m camara.votes_daily
```

### Database migrations

```bash
psql $DATABASE_URL -f db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f db/migrations/002_indexes.sql
```

---

## Data Sources

- **Câmara dos Deputados** — `https://dadosabertos.camara.leg.br/api/v2/` (no auth)
- **Senado Federal** — `https://legis.senado.leg.br/dadosabertos/` (no auth)
- **TSE / Base dos Dados** — `br_tse_eleicoes` dataset on Google BigQuery

---

## MVP Scope

- [ ] Database schema deployed
- [ ] Manus initial load: TSE donations 2018 + 2022, historical Câmara votes 2019–2025
- [ ] Daily ETL: Câmara votes + speeches
- [ ] Daily ETL: Senado votes + speeches
- [ ] AI enrichment: bill summaries, speech summaries, policy tagging
- [ ] Politician profile page
- [ ] Authenticated feed
- [ ] Bill detail page
- [ ] Weekly email digest
- [ ] Voting database explorer
- [ ] Donation table per politician
- [ ] Search
- [ ] User auth (email + password)

---

## License

Private — all rights reserved.
