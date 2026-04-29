"""
AI enrichment runner: generates ai_bio for politicians who don't have one yet.

Reads politicians without ai_bio, calls Claude, writes back to DB.
Fetches committee memberships to give the model useful context.

Usage (from backend/):
    python enrich_politicians.py            # enriches up to 50 at a time
    python enrich_politicians.py --limit 10 # smaller batch for testing
    python enrich_politicians.py --all      # no limit (runs until done)
"""

import argparse
import sys
from dotenv import load_dotenv
load_dotenv(override=True)  # must come before app.config import so .env wins over system env vars

from sqlalchemy import create_engine, text
from app.config import settings
from app.services.ai_enrichment import generate_politician_bio

engine = create_engine(settings.database_url)

JOB_NAME = "enrich_politicians"


def log_run(status: str, fetched: int = 0, updated: int = 0, error: str | None = None) -> None:
    """Record this enrichment run in jobs.etl_runs."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO jobs.etl_runs
                        (job_name, started_at, finished_at, status,
                         records_fetched, records_updated, error_message)
                    VALUES (:job, now(), now(), :status,
                            :fetched, :updated, :error)
                """),
                {
                    "job": JOB_NAME,
                    "status": status,
                    "fetched": fetched,
                    "updated": updated,
                    "error": error,
                },
            )
    except Exception as log_exc:
        print(f"[{JOB_NAME}] could not write to etl_runs — {log_exc}", file=sys.stderr)


def fetch_batch(conn, limit: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT p.id, p.name, p.state, p.current_office,
                   pa.acronym AS party
            FROM core.politicians p
            LEFT JOIN core.parties pa ON pa.id = p.party_id
            WHERE p.ai_bio IS NULL AND p.is_active = TRUE
            ORDER BY p.short_name
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def fetch_committees(conn, politician_id: int) -> list[str]:
    rows = conn.execute(
        text("""
            SELECT COALESCE(NULLIF(c.clean_name, ''), c.name) AS name
            FROM core.committee_memberships cm
            JOIN core.committees c ON c.id = cm.committee_id
            WHERE cm.politician_id = :pid
            ORDER BY COALESCE(NULLIF(c.clean_name, ''), c.name)
        """),
        {"pid": politician_id},
    ).fetchall()
    return [r[0] for r in rows]


def run(limit: int):
    with engine.connect() as conn:
        batch = fetch_batch(conn, limit)

    if not batch:
        print("No politicians without ai_bio — nothing to do.")
        log_run("success", fetched=0, updated=0)
        return

    print(f"Enriching {len(batch)} politicians...")
    ok = failed = 0

    try:
        for p in batch:
            try:
                with engine.connect() as conn:
                    committees = fetch_committees(conn, p["id"])

                bio = generate_politician_bio(
                    name=p["name"],
                    party=p["party"] or "partido não informado",
                    state=p["state"] or "?",
                    office=p["current_office"] or "deputado",
                    committees=committees,
                )

                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE core.politicians SET ai_bio = :bio, updated_at = now() WHERE id = :id"),
                        {"bio": bio, "id": p["id"]},
                    )

                print(f"  [{ok + failed + 1}/{len(batch)}] {p['name']} — ok")
                ok += 1

            except Exception as exc:
                print(f"  [{ok + failed + 1}/{len(batch)}] {p['name']} — FAILED: {exc}", file=sys.stderr)
                failed += 1

        print(f"\nDone — {ok} enriched, {failed} failed.")
        log_run("success", fetched=len(batch), updated=ok)

    except Exception as exc:
        print(f"[{JOB_NAME}] unexpected error — {exc}", file=sys.stderr)
        log_run("failed", fetched=len(batch), updated=ok, error=str(exc))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="Max politicians to process (default: 50)")
    parser.add_argument("--all", action="store_true", help="Process all politicians without ai_bio")
    args = parser.parse_args()

    limit = 10_000 if args.all else args.limit
    run(limit)
