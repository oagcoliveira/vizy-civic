"""
Single-bill enrichment pipeline.

Runs the full enrichment sequence for one Câmara bill identified by its
internal DB id and Câmara external_id:

  Step 1 — Detail ingest (Câmara API)
    Calls GET /proposicoes/{external_id} and GET /proposicoes/{external_id}/autores
    to fill: status, full_text_url, author_label, author_politician_id.

  Step 2 — Tramitações ingest (Câmara API)
    Calls GET /proposicoes/{external_id}/tramitacoes and upserts
    core.legislative_events rows for this bill.

  Step 3 — AI bill enrichment (Claude Haiku)
    Generates short_title, summary, and policy_area if still missing.

  Step 4 — AI legislative-event enrichment (Claude Haiku)
    Generates plain-language summary for any core.legislative_events rows
    belonging to this bill that still have summary IS NULL.

Each step is idempotent: it only fills NULL / missing fields and skips work
that has already been done.

Usage (from etl/):
    python -m camara.bill_enrich_single --bill-id 42
    python -m camara.bill_enrich_single --bill-id 42 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from anthropic import Anthropic
from sqlalchemy import text

from db import engine
from camara.client import get
from camara.bills_ingest_daily import _fetch_bill_detail, _resolve_author_politician_id
from camara.bills_enrich_daily import generate_ai_enrichment, ENRICH_TYPES

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# Step 1 — Detail ingest
# ---------------------------------------------------------------------------

def step_detail(bill_id: int, external_id: int, dry_run: bool = False) -> dict:
    """
    Fetch status, author, and full_text_url from the Câmara API.
    Returns a dict with the fields that were updated (empty dict if nothing changed).
    """
    print(f"  [step 1/detail] Fetching detail for external_id={external_id}...", flush=True)
    detail = _fetch_bill_detail(external_id)
    if not detail:
        print("  [step 1/detail] No data returned from API — skipping.", flush=True)
        return {}

    author_politician_id = _resolve_author_politician_id(detail.get("author_external_id"))

    if dry_run:
        print(f"  [step 1/detail] [DRY RUN] would update: {detail}", flush=True)
        return detail

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

    print(f"  [step 1/detail] Done — status={detail.get('status')!r}", flush=True)
    return detail


# ---------------------------------------------------------------------------
# Step 2 — Tramitações ingest
# ---------------------------------------------------------------------------

def step_tramitacoes(bill_id: int, external_id: int, dry_run: bool = False) -> int:
    """
    Fetch and upsert legislative events (tramitações) for this bill.
    Returns the number of new rows inserted.
    """
    print(f"  [step 2/tramitacoes] Fetching tramitações for external_id={external_id}...", flush=True)
    try:
        events = get(f"/proposicoes/{external_id}/tramitacoes").get("dados", [])
    except Exception as e:
        print(f"  [step 2/tramitacoes] WARNING: API error — {e}", flush=True)
        return 0

    if not events:
        print("  [step 2/tramitacoes] No events returned.", flush=True)
        return 0

    rows_to_insert = []
    for ev in events:
        raw_date = ev.get("dataHora") or ev.get("data")
        event_date = raw_date[:10] if raw_date else None
        rows_to_insert.append({
            "bill_id": bill_id,
            "sequence": ev.get("sequencia", 0),
            "event_date": event_date,
            "stage": (ev.get("descricaoTramitacao") or "")[:255] or None,
            "description": ev.get("descricaoSituacao") or None,
            "venue": (ev.get("siglaOrgao") or "")[:100] or None,
        })

    if dry_run:
        print(f"  [step 2/tramitacoes] [DRY RUN] would upsert {len(rows_to_insert)} events.", flush=True)
        return len(rows_to_insert)

    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO core.legislative_events
                (bill_id, sequence, event_date, stage, description, venue)
            VALUES
                (:bill_id, :sequence, :event_date, :stage, :description, :venue)
            ON CONFLICT (bill_id, sequence) DO NOTHING
        """), rows_to_insert)
        inserted = result.rowcount

    print(f"  [step 2/tramitacoes] Done — {inserted} new events inserted (of {len(rows_to_insert)} total).", flush=True)
    return inserted


# ---------------------------------------------------------------------------
# Step 3 — AI bill enrichment
# ---------------------------------------------------------------------------

def step_ai_bill(bill_id: int, dry_run: bool = False) -> bool:
    """
    Generate short_title, summary, and policy_area for this bill if still missing.
    Returns True if enrichment was performed.
    """
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, external_id, type, number, year, title, ementa,
                   short_title, policy_area
            FROM core.bills
            WHERE id = :id
        """), {"id": bill_id}).fetchone()

    if not row:
        print(f"  [step 3/ai-bill] Bill id={bill_id} not found — skipping.", flush=True)
        return False

    bill_type = row.type
    ementa = row.ementa

    # Skip if already fully enriched
    if row.short_title and row.policy_area:
        print("  [step 3/ai-bill] Already enriched (short_title + policy_area present) — skipping.", flush=True)
        return False

    # Skip if not a substantive bill type or missing ementa
    if bill_type not in ENRICH_TYPES:
        print(f"  [step 3/ai-bill] Bill type {bill_type!r} not in ENRICH_TYPES — skipping AI enrichment.", flush=True)
        return False

    if not ementa:
        print("  [step 3/ai-bill] No ementa available — cannot enrich yet.", flush=True)
        return False

    print(f"  [step 3/ai-bill] Generating AI enrichment for bill id={bill_id}...", flush=True)

    if dry_run:
        print("  [step 3/ai-bill] [DRY RUN] would call Claude Haiku.", flush=True)
        return True

    try:
        ai = generate_ai_enrichment(
            ementa=ementa,
            title=row.title,
            bill_type=bill_type,
            number=row.number,
            year=row.year,
        )
    except Exception as e:
        print(f"  [step 3/ai-bill] AI call failed: {e}", file=sys.stderr, flush=True)
        return False

    if not any(ai.values()):
        print("  [step 3/ai-bill] AI returned empty result — skipping update.", flush=True)
        return False

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE core.bills SET
                short_title = COALESCE(:short_title, short_title),
                summary     = COALESCE(:summary,     summary),
                policy_area = COALESCE(:policy_area, policy_area),
                updated_at  = now()
            WHERE id = :id
        """), {
            "id": bill_id,
            "short_title": ai.get("short_title"),
            "summary": ai.get("summary"),
            "policy_area": ai.get("policy_area"),
        })

    print(f"  [step 3/ai-bill] Done — short_title={ai.get('short_title')!r}", flush=True)
    return True


# ---------------------------------------------------------------------------
# Step 4 — AI legislative-event enrichment
# ---------------------------------------------------------------------------

def _generate_event_label(stage: str | None, description: str | None, venue: str | None) -> str | None:
    """Call Claude Haiku to translate a bureaucratic legislative stage to plain Portuguese."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    parts = []
    if stage:
        parts.append(f"Fase: {stage}")
    if description:
        parts.append(f"Situação: {description}")
    if venue:
        parts.append(f"Órgão: {venue}")

    if not parts:
        return None

    context = "\n".join(parts)
    prompt = (
        "Você é um assistente de tecnologia cívica. Traduza esta etapa legislativa burocrática "
        "para uma frase curta e clara em português simples (máximo 10 palavras), "
        "como se explicasse para um cidadão leigo.\n\n"
        f"{context}\n\n"
        'Responda APENAS com JSON no formato: {"label": "frase em português simples"}'
    )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    result = json.loads(raw)
    return result.get("label")


def step_ai_events(bill_id: int, dry_run: bool = False) -> int:
    """
    Generate plain-language summaries for legislative events of this bill
    that still have summary IS NULL.
    Returns the number of events enriched.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, stage, description, venue
            FROM core.legislative_events
            WHERE bill_id = :bill_id
              AND summary IS NULL
              AND (stage IS NOT NULL OR description IS NOT NULL)
            ORDER BY sequence ASC
        """), {"bill_id": bill_id}).fetchall()

    events = [dict(r._mapping) for r in rows]

    if not events:
        print("  [step 4/ai-events] All events already have summaries — skipping.", flush=True)
        return 0

    print(f"  [step 4/ai-events] Enriching {len(events)} legislative events...", flush=True)

    if dry_run:
        print(f"  [step 4/ai-events] [DRY RUN] would enrich {len(events)} events.", flush=True)
        return len(events)

    ok = 0
    for item in events:
        try:
            label = _generate_event_label(
                stage=item["stage"],
                description=item["description"],
                venue=item["venue"],
            )
            if label:
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE core.legislative_events SET summary = :s WHERE id = :id"),
                        {"s": label, "id": item["id"]},
                    )
                ok += 1
        except Exception as exc:
            print(f"  [step 4/ai-events] WARNING: failed for event id={item['id']}: {exc}", file=sys.stderr, flush=True)
        finally:
            time.sleep(0.3)  # respect Anthropic rate limits

    print(f"  [step 4/ai-events] Done — {ok}/{len(events)} events enriched.", flush=True)
    return ok


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run(bill_id: int, dry_run: bool = False) -> dict:
    """
    Run the full enrichment pipeline for a single bill.
    Returns a summary dict with counts/flags for each step.
    """
    # Resolve external_id from DB
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, external_id, source, status, short_title, policy_area,
                   ementa, type
            FROM core.bills
            WHERE id = :id
        """), {"id": bill_id}).fetchone()

    if not row:
        raise ValueError(f"Bill id={bill_id} not found in core.bills")

    if row.source != "camara":
        raise ValueError(f"Bill id={bill_id} has source={row.source!r}; only 'camara' bills are supported for now")

    external_id = row.external_id
    print(f"[bill_enrich_single] Starting enrichment for bill id={bill_id} (external_id={external_id})", flush=True)

    result: dict = {}

    # Step 1: Detail ingest
    result["detail"] = step_detail(bill_id, external_id, dry_run=dry_run)

    # Step 2: Tramitações ingest
    result["tramitacoes_inserted"] = step_tramitacoes(bill_id, external_id, dry_run=dry_run)

    # Step 3: AI bill enrichment
    result["ai_bill_enriched"] = step_ai_bill(bill_id, dry_run=dry_run)

    # Step 4: AI legislative-event enrichment
    result["ai_events_enriched"] = step_ai_events(bill_id, dry_run=dry_run)

    print(f"[bill_enrich_single] All steps complete for bill id={bill_id}.", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich a single Câmara bill end-to-end")
    parser.add_argument("--bill-id", type=int, required=True, help="Internal DB id from core.bills")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing to DB")
    args = parser.parse_args()
    run(bill_id=args.bill_id, dry_run=args.dry_run)
