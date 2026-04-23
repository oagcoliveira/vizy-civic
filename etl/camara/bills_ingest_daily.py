"""
Daily ETL: discover and detail-fetch Câmara bills.

Phase 1 — Discovery (list API):
  Fetches all bills presented since the last successful run (or since
  MAX(presented_at) in the DB, or 2023-01-01 as absolute fallback).
  Upserts bare-bones rows: external_id, type, number, year, ementa, presented_at.

Phase 2 — Detail backfill (detail API):
  Fetches full detail (status, author, full_text_url) for up to DETAIL_LIMIT
  bills per run that still have status IS NULL.  This naturally covers both
  newly-inserted bills from Phase 1 and any historical rows that were never
  enriched.  Capped so the job always finishes within the scheduler timeout.

AI enrichment (short_title, summary, policy_area) is handled by the separate
camara_bills_enrich_daily job.

Usage:
    python -m camara.bills_ingest_daily           # full run
    python -m camara.bills_ingest_daily --dry-run  # print counts, no DB writes
    python -m camara.bills_ingest_daily --detail-limit 100  # smaller detail batch
"""

import argparse
import sys
from datetime import date, timedelta

from sqlalchemy import text

from db import engine, last_successful_run, log_run
from camara.client import paginate, get

JOB_NAME = "camara_bills_ingest_daily"
CHUNK_DAYS = 7        # small chunks to avoid API pagination limits
DETAIL_LIMIT = 300    # max bills to detail-fetch per run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_chunks(since: str, until: str):
    start = date.fromisoformat(since)
    end = date.fromisoformat(until)
    while start <= end:
        chunk_end = min(start + timedelta(days=CHUNK_DAYS - 1), end)
        yield start.isoformat(), chunk_end.isoformat()
        start = chunk_end + timedelta(days=1)


def _newest_bill_date() -> str | None:
    """Return MAX(presented_at) from core.bills as a YYYY-MM-DD string, or None."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(presented_at)::date FROM core.bills WHERE source = 'camara'")
        ).fetchone()
    if row and row[0]:
        return str(row[0])
    return None


def _fetch_bill_detail(external_id: int) -> dict:
    """Fetch status, author, and full_text_url for one bill from the Câmara API."""
    try:
        data = get(f"/proposicoes/{external_id}").get("dados", {})
    except Exception as e:
        print(f"    WARNING: could not fetch /proposicoes/{external_id}: {e}", flush=True)
        return {}

    status_info = data.get("statusProposicao") or {}
    status = status_info.get("descricaoSituacao")
    full_text_url = data.get("urlInteiroTeor")

    # Fetch author(s)
    author_label = None
    author_external_id = None
    try:
        autores = get(f"/proposicoes/{external_id}/autores").get("dados", [])
        if autores:
            names = [a.get("nome", "") for a in autores[:3] if a.get("nome")]
            author_label = "; ".join(names) if names else None
            if len(autores) == 1:
                uri = autores[0].get("uri", "")
                if "/deputados/" in uri:
                    try:
                        author_external_id = int(uri.rstrip("/").split("/")[-1])
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass

    return {
        "status": status,
        "full_text_url": full_text_url,
        "author_label": author_label,
        "author_external_id": author_external_id,
    }


def _resolve_author_politician_id(author_external_id: int | None) -> int | None:
    if not author_external_id:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM core.politicians WHERE source = 'camara' AND external_id = :eid"),
            {"eid": author_external_id},
        ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Phase 1: Discovery
# ---------------------------------------------------------------------------

def run_discovery(today: str, dry_run: bool = False) -> tuple[int, int]:
    """
    Fetch bills from the list API since the last successful run.
    Returns (inserted, updated).
    """
    # Determine start date: last successful run → newest bill in DB → absolute fallback
    since = last_successful_run(JOB_NAME) or _newest_bill_date() or "2023-01-01"
    print(f"[{JOB_NAME}] Phase 1 — Discovery: fetching bills from {since} to {today}", flush=True)

    inserted = updated = 0

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

    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED during discovery: {exc}", file=sys.stderr, flush=True)
        raise

    print(
        f"[{JOB_NAME}] Phase 1 done — {inserted} new bills inserted, {updated} existing updated",
        flush=True,
    )
    return inserted, updated


# ---------------------------------------------------------------------------
# Phase 2: Detail backfill
# ---------------------------------------------------------------------------

def run_detail_backfill(limit: int, dry_run: bool = False) -> int:
    """
    Fetch full detail (status, author) for up to `limit` bills that still
    have status IS NULL.  Returns the number of bills processed.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, external_id
            FROM core.bills
            WHERE source = 'camara'
              AND status IS NULL
            ORDER BY id
            LIMIT :limit
        """), {"limit": limit}).fetchall()

    total = len(rows)
    if total == 0:
        print(f"[{JOB_NAME}] Phase 2 — Detail backfill: nothing to do (all bills have status)", flush=True)
        return 0

    print(f"[{JOB_NAME}] Phase 2 — Detail backfill: fetching detail for {total} bills (limit={limit})", flush=True)

    processed = 0
    for i, (bill_id, ext_id) in enumerate(rows, 1):
        if i % 50 == 0 or i == 1:
            print(f"[{JOB_NAME}]   {i}/{total} (id={bill_id}, ext={ext_id})", flush=True)

        if dry_run:
            processed += 1
            continue

        detail = _fetch_bill_detail(ext_id)
        if not detail:
            # API error — leave status NULL so it will be retried next run
            continue

        author_politician_id = _resolve_author_politician_id(detail.get("author_external_id"))

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE core.bills SET
                    status               = COALESCE(:status,               status),
                    full_text_url        = COALESCE(:full_text_url,        full_text_url),
                    author_label         = COALESCE(:author_label,         author_label),
                    author_politician_id = COALESCE(:author_politician_id, author_politician_id),
                    updated_at           = now()
                WHERE id = :id
            """), {
                "id": bill_id,
                "status": detail.get("status"),
                "full_text_url": detail.get("full_text_url"),
                "author_label": detail.get("author_label"),
                "author_politician_id": author_politician_id,
            })
        processed += 1

    print(f"[{JOB_NAME}] Phase 2 done — {processed} bills detail-fetched", flush=True)
    return processed


# ---------------------------------------------------------------------------
# Backfill author IDs from short_name match (idempotent)
# ---------------------------------------------------------------------------

def backfill_author_ids():
    """Match author_label against core.politicians.short_name to fill author_politician_id."""
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE core.bills b
            SET author_politician_id = p.id, updated_at = now()
            FROM core.politicians p
            WHERE b.author_politician_id IS NULL
              AND b.author_label IS NOT NULL
              AND b.author_label NOT LIKE '%;%'
              AND lower(p.short_name) = lower(b.author_label)
        """))
        count = result.rowcount
    if count:
        print(f"[{JOB_NAME}] Backfilled author_politician_id for {count} bills via short_name match.", flush=True)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, detail_limit: int = DETAIL_LIMIT):
    today = date.today().isoformat()

    # Phase 1: discover new bills
    inserted, updated = run_discovery(today, dry_run=dry_run)

    # Phase 2: detail-fetch bills missing status (new + historical backlog)
    detail_processed = run_detail_backfill(detail_limit, dry_run=dry_run)

    # Backfill author IDs via name match (fast, idempotent)
    if not dry_run:
        backfill_author_ids()

    fetched = inserted + updated
    if not dry_run:
        log_run(
            JOB_NAME, "success",
            fetched=fetched, inserted=inserted, updated=updated,
            params={"today": today, "detail_processed": detail_processed},
        )
    print(
        f"[{JOB_NAME}] All done — {inserted} new, {updated} updated, {detail_processed} detail-fetched",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing to DB")
    parser.add_argument(
        "--detail-limit", type=int, default=DETAIL_LIMIT,
        help=f"Max bills to detail-fetch per run (default: {DETAIL_LIMIT})",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, detail_limit=args.detail_limit)
