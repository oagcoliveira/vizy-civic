"""
Bills tramitações ETL: fetches and upserts legislative events for active bills.

For each bill in core.bills where source='camara' and status is not archived,
calls GET /proposicoes/{external_id}/tramitacoes and upserts new events into
core.legislative_events.

Usage:
    # Test run — process only 20 bills
    python -m camara.bills_tramitacoes_daily --limit 20

    # Full run
    python -m camara.bills_tramitacoes_daily
"""

import argparse
from datetime import datetime, timezone

import sys
from sqlalchemy import text

from db import engine, log_run
from camara.client import get

JOB_NAME = "camara_bills_tramitacoes_daily"

ARCHIVED_KEYWORDS = ("arquivada", "prejudicada", "encerrada", "retirada")


def is_archived(status: str | None) -> bool:
    if not status:
        return False
    s = status.lower()
    return any(k in s for k in ARCHIVED_KEYWORDS)


def run(limit: int | None = None):
    try:
        _run(limit)
    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr, flush=True)
        raise


def _run(limit: int | None = None):
    started_at = datetime.now(timezone.utc)

    with engine.connect() as conn:
        query = """
            SELECT id, external_id, status
            FROM core.bills
            WHERE source = 'camara'
              AND NOT (status IS NOT NULL AND (
                  lower(status) LIKE '%arquivad%' OR
                  lower(status) LIKE '%prejudicad%' OR
                  lower(status) LIKE '%encerrad%' OR
                  lower(status) LIKE '%retira%'
              ))
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        bills = conn.execute(text(query)).fetchall()

    total = len(bills)
    print(f"Fetching tramitações for {total} active bills{'  (test run)' if limit else ''}...", flush=True)

    inserted_total = 0

    for i, (bill_id, external_id, status) in enumerate(bills, 1):
        if i % 50 == 0 or i == 1:
            print(f"  {i}/{total} (bill_id={bill_id})", flush=True)

        try:
            events = get(f"/proposicoes/{external_id}/tramitacoes").get("dados", [])
        except Exception as e:
            print(f"    WARNING: could not fetch tramitacoes for {external_id}: {e}", flush=True)
            continue

        if not events:
            continue

        rows = []
        for ev in events:
            raw_date = ev.get("dataHora") or ev.get("data")
            event_date = None
            if raw_date:
                try:
                    event_date = raw_date[:10]  # ISO date part
                except Exception:
                    pass

            rows.append({
                "bill_id": bill_id,
                "sequence": ev.get("sequencia", 0),
                "event_date": event_date,
                "stage": (ev.get("descricaoTramitacao") or "")[:255] or None,
                "description": ev.get("descricaoSituacao") or None,
                "venue": (ev.get("siglaOrgao") or "")[:100] or None,
            })

        if not rows:
            continue

        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO core.legislative_events
                    (bill_id, sequence, event_date, stage, description, venue)
                VALUES
                    (:bill_id, :sequence, :event_date, :stage, :description, :venue)
                ON CONFLICT (bill_id, sequence) DO NOTHING
            """), rows)
            inserted_total += result.rowcount

    log_run(JOB_NAME, "success", fetched=total, inserted=inserted_total,
            params={"limit": limit})
    print(f"Done! Inserted {inserted_total} new tramitação events across {total} bills.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(limit=args.limit)
