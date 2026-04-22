"""
One-time backfill: fetch all proposições presented since a given date,
upsert into core.bills, then enrich with detail + AI and load tramitações.

Usage:
    python -m camara.bills_backfill                        # since 2023-01-01 (default)
    python -m camara.bills_backfill --since 2024-01-01     # narrower window
    python -m camara.bills_backfill --fetch-only           # skip enrichment + tramitações
"""

import argparse
import sys
from datetime import date, timedelta

from sqlalchemy import text

from db import engine
from camara.client import paginate
from camara.bills_daily import run as enrich_bills
from camara.bills_tramitacoes_daily import run as load_tramitacoes

CHUNK_DAYS = 30

# Only fetch substantive legislative proposals — exclude internal documents
# (requerimentos, emendas, pareceres, substitutivos, etc.)
BILL_TYPES = ["PL", "PLP", "PEC", "MPV", "PDL", "PRC", "MSC", "TVR", "PLN", "PDC"]


def _date_chunks(since: str):
    start = date.fromisoformat(since)
    end = date.today()
    while start <= end:
        chunk_end = min(start + timedelta(days=CHUNK_DAYS - 1), end)
        yield start.isoformat(), chunk_end.isoformat()
        start = chunk_end + timedelta(days=1)


def fetch_and_upsert(since: str):
    inserted = updated = 0

    for chunk_start, chunk_end in _date_chunks(since):
        print(f"[bills_backfill] Fetching {chunk_start} -> {chunk_end}", flush=True)
        try:
            bills = paginate("/proposicoes", {
                "dataApresentacaoInicio": chunk_start,
                "dataApresentacaoFim": chunk_end,
                "ordem": "ASC",
            })
        except Exception as e:
            print(f"[bills_backfill]   ERROR fetching chunk: {e}", file=sys.stderr)
            continue

        if not bills:
            continue

        with engine.begin() as conn:
            for b in bills:
                ext_id = b.get("id")
                if not ext_id:
                    continue
                tipo = b.get("siglaTipo") or None
                numero = b.get("numero")
                ano = b.get("ano")
                ementa = b.get("ementa") or None
                title = f"{tipo} {numero}/{ano}" if tipo and numero and ano else None
                raw_date = b.get("dataApresentacao")
                presented_at = raw_date[:10] if raw_date else None  # keep only date part

                res = conn.execute(text("""
                    INSERT INTO core.bills
                        (source, external_id, type, number, year, title, ementa, presented_at)
                    VALUES ('camara', :eid, :type, :number, :year, :title, :ementa, :presented_at)
                    ON CONFLICT (source, external_id) DO UPDATE
                        SET ementa = COALESCE(EXCLUDED.ementa, core.bills.ementa),
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

        print(f"[bills_backfill]   chunk done — {inserted} inserted, {updated} updated so far", flush=True)

    print(f"[bills_backfill] Fetch complete: {inserted} new bills, {updated} already existed", flush=True)
    return inserted + updated


def run(since: str = "2023-01-01", fetch_only: bool = False):
    print(f"[bills_backfill] === Step 1/3: Fetching proposições since {since} ===", flush=True)
    total = fetch_and_upsert(since)

    if fetch_only:
        print(f"[bills_backfill] --fetch-only set, stopping after fetch.", flush=True)
        return

    print(f"\n[bills_backfill] === Step 2/3: Enriching bills (detail + AI) ===", flush=True)
    enrich_bills()

    print(f"\n[bills_backfill] === Step 3/3: Loading tramitações ===", flush=True)
    load_tramitacoes()

    print(f"\n[bills_backfill] === All done ===", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2023-01-01")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch bills, skip enrichment and tramitações")
    args = parser.parse_args()
    run(since=args.since, fetch_only=args.fetch_only)
