"""\nDaily ETL: legislative events (tramitações) for Câmara bills.\n\nFetches tramitações for active bills, prioritising:\n  1. Bills that have never had tramitações fetched (no rows in core.legislative_events).\n  2. Bills updated most recently (highest updated_at), so active bills stay current.\n\nCapped at TRAMIT_LIMIT bills per run to ensure the job always finishes within\nthe scheduler timeout.  On subsequent runs it continues to chip away at the\nbacklog until all active bills are covered.\n\nUsage:\n    python -m camara.bills_tramitacoes_daily              # full run (default limit)\n    python -m camara.bills_tramitacoes_daily --limit 50   # smaller batch for testing\n    python -m camara.bills_tramitacoes_daily --all        # no limit (use with caution)\n"""

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from db import engine, log_run
from camara.client import get

JOB_NAME = "camara_bills_tramitacoes_daily"
TRAMIT_LIMIT = 500   # bills per run — keeps the job well within the 600s scheduler timeout

ARCHIVED_KEYWORDS = ("arquivada", "prejudicada", "encerrada", "retirada")


def is_archived(status: str | None) -> bool:
    if not status:
        return False
    s = status.lower()
    return any(k in s for k in ARCHIVED_KEYWORDS)


def run(limit: int = TRAMIT_LIMIT):
    try:
        _run(limit)
    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr, flush=True)
        raise


def _run(limit: int = TRAMIT_LIMIT):
    # Fetch active bills, prioritising:
    #   - Bills with no tramitações yet (never fetched) first
    #   - Then bills updated most recently (most likely to have new events)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT b.id, b.external_id, b.status
            FROM core.bills b
            WHERE b.source = 'camara'
              AND NOT (b.status IS NOT NULL AND (
                  lower(b.status) LIKE '%arquivad%' OR
                  lower(b.status) LIKE '%prejudicad%' OR
                  lower(b.status) LIKE '%encerrad%' OR
                  lower(b.status) LIKE '%retira%'
              ))
            ORDER BY
                (NOT EXISTS (
                    SELECT 1 FROM core.legislative_events le WHERE le.bill_id = b.id
                )) DESC,
                b.presented_at DESC NULLS LAST,
                b.id DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

    total = len(rows)
    if total == 0:
        print(f"[{JOB_NAME}] No active bills to process.", flush=True)
        log_run(JOB_NAME, "success", fetched=0, inserted=0)
        return

    print(
        f"[{JOB_NAME}] Fetching tramitações for {total} active bills (limit={limit})...",
        flush=True,
    )
    bills = rows

    inserted_total = 0

    for i, (bill_id, external_id, status) in enumerate(bills, 1):
        if i % 50 == 0 or i == 1:
            print(f"[{JOB_NAME}]   {i}/{total} (bill_id={bill_id})", flush=True)

        try:
            events = get(f"/proposicoes/{external_id}/tramitacoes").get("dados", [])
        except Exception as e:
            print(f"[{JOB_NAME}]   WARNING: could not fetch tramitacoes for {external_id}: {e}", flush=True)
            continue

        if not events:
            continue

        rows_to_insert = []
        for ev in events:
            raw_date = ev.get("dataHora") or ev.get("data")
            event_date = None
            if raw_date:
                try:
                    event_date = raw_date[:10]
                except Exception:
                    pass

            rows_to_insert.append({
                "bill_id": bill_id,
                "sequence": ev.get("sequencia", 0),
                "event_date": event_date,
                "stage": (ev.get("descricaoTramitacao") or "")[:255] or None,
                "description": ev.get("descricaoSituacao") or None,
                "venue": (ev.get("siglaOrgao") or "")[:100] or None,
            })

        if not rows_to_insert:
            continue

        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO core.legislative_events
                    (bill_id, sequence, event_date, stage, description, venue)
                VALUES
                    (:bill_id, :sequence, :event_date, :stage, :description, :venue)
                ON CONFLICT (bill_id, sequence) DO NOTHING
            """), rows_to_insert)
            inserted_total += result.rowcount

    log_run(JOB_NAME, "success", fetched=total, inserted=inserted_total,
            params={"limit": limit})
    print(
        f"[{JOB_NAME}] Done — {inserted_total} new tramitação events across {total} bills.",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=TRAMIT_LIMIT,
        help=f"Max bills to process per run (default: {TRAMIT_LIMIT})",
    )
    parser.add_argument("--all", action="store_true", help="Process all active bills without limit")
    args = parser.parse_args()
    run(limit=10_000 if args.all else args.limit)
