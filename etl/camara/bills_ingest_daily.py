"""
Daily ETL: fetch newly presented proposições from the Câmara API.

Fetches all bills presented since the last successful run of this job
(or since 2023-01-01 on first run), upserts them into core.bills with
their presented_at date, then hands off to bills_daily for enrichment.

This is the *ingestion* counterpart to bills_daily.py (which only enriches
existing rows). Both must run to keep the bills table current.

Schedule: 03:05 BRT daily (immediately after camara_votes_daily).

Usage:
    python -m camara.bills_ingest_daily          # full run
    python -m camara.bills_ingest_daily --dry-run  # print counts, no DB writes
"""

import argparse
import sys
from datetime import date, timedelta

from sqlalchemy import text

from db import engine, last_successful_run, log_run
from camara.client import paginate

JOB_NAME = "camara_bills_ingest_daily"
CHUNK_DAYS = 7   # small chunks to avoid API pagination limits


def _date_chunks(since: str, until: str):
    start = date.fromisoformat(since)
    end = date.fromisoformat(until)
    while start <= end:
        chunk_end = min(start + timedelta(days=CHUNK_DAYS - 1), end)
        yield start.isoformat(), chunk_end.isoformat()
        start = chunk_end + timedelta(days=1)


def run(dry_run: bool = False):
    today = date.today().isoformat()
    # Use last successful run date; fall back to 2023-01-01 (start of 57th legislature)
    since = last_successful_run(JOB_NAME) or "2023-01-01"
    print(f"[{JOB_NAME}] Fetching new bills from {since} to {today}", flush=True)

    inserted = 0
    updated = 0

    try:
        for chunk_start, chunk_end in _date_chunks(since, today):
            print(f"[{JOB_NAME}]   chunk {chunk_start} -> {chunk_end}", flush=True)
            try:
                bills = paginate("/proposicoes", {
                    "dataApresentacaoInicio": chunk_start,
                    "dataApresentacaoFim": chunk_end,
                    "ordem": "ASC",
                })
            except Exception as e:
                print(f"[{JOB_NAME}]   WARNING: could not fetch chunk: {e}", file=sys.stderr, flush=True)
                continue

            if not bills:
                continue

            if dry_run:
                print(f"[{JOB_NAME}]   [DRY RUN] would upsert {len(bills)} bills", flush=True)
                inserted += len(bills)
                continue

            with engine.begin() as conn:
                for b in bills:
                    ext_id = b.get("id")
                    if not ext_id:
                        continue
                    tipo = b.get("siglaTipo") or None
                    numero = b.get("numero")
                    ano = b.get("ano")
                    ementa = (b.get("ementa") or "").strip() or None
                    title = f"{tipo} {numero}/{ano}" if tipo and numero and ano else None
                    raw_date = b.get("dataApresentacao")
                    presented_at = raw_date[:10] if raw_date else None

                    res = conn.execute(text("""
                        INSERT INTO core.bills
                            (source, external_id, type, number, year, title, ementa, presented_at)
                        VALUES ('camara', :eid, :type, :number, :year, :title, :ementa, :presented_at)
                        ON CONFLICT (source, external_id) DO UPDATE
                            SET type         = COALESCE(EXCLUDED.type,         core.bills.type),
                                number       = COALESCE(EXCLUDED.number,       core.bills.number),
                                year         = COALESCE(EXCLUDED.year,         core.bills.year),
                                title        = COALESCE(EXCLUDED.title,        core.bills.title),
                                ementa       = COALESCE(EXCLUDED.ementa,       core.bills.ementa),
                                presented_at = COALESCE(EXCLUDED.presented_at, core.bills.presented_at)
                        RETURNING (xmax = 0) AS was_inserted
                    """), {
                        "eid": str(ext_id),
                        "type": tipo,
                        "number": numero,
                        "year": ano,
                        "title": title,
                        "ementa": ementa,
                        "presented_at": presented_at,
                    })
                    was_inserted = res.fetchone()[0]
                    if was_inserted:
                        inserted += 1
                    else:
                        updated += 1

        fetched = inserted + updated
        print(f"[{JOB_NAME}] Done — {inserted} new bills inserted, {updated} existing updated", flush=True)
        if not dry_run:
            log_run(JOB_NAME, "success", fetched=fetched, inserted=inserted, updated=updated,
                    params={"since": since, "until": today})

    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
