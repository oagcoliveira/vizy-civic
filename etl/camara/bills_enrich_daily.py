"""
Daily ETL: AI enrichment for Câmara bills.

Generates short_title, summary, and policy_area for bills that have an ementa
but are missing AI enrichment.  Processes up to ENRICH_LIMIT bills per run so
the job always finishes within the scheduler timeout.  On subsequent runs it
continues from where it left off (newest bills first).

This job is intentionally separate from bills_ingest_daily so that:
  - Ingestion (fast, no AI) and enrichment (slow, AI) can be tuned independently.
  - A timeout in enrichment never blocks new bills from being ingested.

Usage:
    python -m camara.bills_enrich_daily               # full run (default limit)
    python -m camara.bills_enrich_daily --limit 50    # smaller batch for testing
    python -m camara.bills_enrich_daily --all         # no limit (use with caution)
"""

import argparse
import json
import os
import sys

from anthropic import Anthropic
from sqlalchemy import text

from db import engine, log_run

JOB_NAME = "camara_bills_enrich_daily"
ENRICH_LIMIT = 200   # bills per run — keeps the job well within the 900s scheduler timeout

# Bill types worth enriching — procedural/minor types are excluded
ENRICH_TYPES = ("PL", "PLP", "PEC", "MPV", "PDL", "PRC", "MSC", "TVR", "PLN", "PDC")

POLICY_AREAS = [
    "Saúde", "Educação", "Economia e Finanças", "Meio Ambiente", "Segurança Pública",
    "Agricultura e Agropecuária", "Infraestrutura e Transportes", "Direitos Humanos",
    "Administração Pública", "Ciência e Tecnologia", "Cultura e Esporte",
    "Trabalho e Emprego", "Previdência Social", "Relações Exteriores e Defesa",
    "Tributos e Fiscalidade", "Habitação e Urbanismo", "Justiça e Legislação",
    "Comunicação e Mídia", "Energia", "Assistência Social",
]

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# AI enrichment
# ---------------------------------------------------------------------------

def generate_ai_enrichment(
    ementa: str,
    title: str | None,
    bill_type: str | None,
    number: int | None,
    year: int | None,
) -> dict:
    """Call Claude Haiku to generate short_title, summary, and policy_area."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    bill_ref = f"{bill_type} {number}/{year}" if bill_type and number and year else title or "Sem título"
    areas_list = ", ".join(f'"{a}"' for a in POLICY_AREAS)

    prompt = (
        f"Você é um assistente de tecnologia cívica. Analise esta proposição legislativa brasileira.\n\n"
        f"Referência: {bill_ref}\n"
        f"Ementa: {ementa}\n\n"
        f"Áreas de política disponíveis: {areas_list}\n\n"
        f"Responda APENAS com JSON no formato:\n"
        f'{{"short_title": "título curto em até 12 palavras", '
        f'"summary": "resumo em 2 frases em português simples, sem jargão jurídico", '
        f'"policy_area": "uma das áreas listadas acima"}}'
    )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    result = json.loads(raw)

    policy_area = result.get("policy_area")
    if policy_area not in POLICY_AREAS:
        policy_area = None

    return {
        "short_title": result.get("short_title"),
        "summary": result.get("summary"),
        "policy_area": policy_area,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(limit: int = ENRICH_LIMIT):
    try:
        _run(limit)
    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr, flush=True)
        raise


def _run(limit: int):
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT id, external_id, type, number, year, title, ementa
            FROM core.bills
            WHERE source = 'camara'
              AND type IN {ENRICH_TYPES}
              AND ementa IS NOT NULL
              AND (short_title IS NULL OR policy_area IS NULL)
            ORDER BY presented_at DESC NULLS LAST, id DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

    total = len(rows)
    if total == 0:
        print(f"[{JOB_NAME}] Nothing to enrich — all qualifying bills already have short_title and policy_area.", flush=True)
        log_run(JOB_NAME, "success", fetched=0, updated=0)
        return

    print(f"[{JOB_NAME}] Enriching {total} bills (limit={limit})...", flush=True)
    ok = failed = 0

    for i, row in enumerate(rows, 1):
        bill_id, ext_id, bill_type, number, year, title, ementa = row
        if i % 20 == 0 or i == 1:
            print(f"[{JOB_NAME}]   {i}/{total} (id={bill_id})", flush=True)

        try:
            ai = generate_ai_enrichment(ementa, title, bill_type, number, year)
        except Exception as e:
            print(f"[{JOB_NAME}]   WARNING: AI failed for id={bill_id}: {e}", file=sys.stderr, flush=True)
            failed += 1
            continue

        if not any(ai.values()):
            failed += 1
            continue

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
        ok += 1

    log_run(JOB_NAME, "success", fetched=total, updated=ok,
            params={"limit": limit})
    print(f"[{JOB_NAME}] Done — {ok} enriched, {failed} failed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=ENRICH_LIMIT,
        help=f"Max bills to enrich per run (default: {ENRICH_LIMIT})",
    )
    parser.add_argument("--all", action="store_true", help="Process all bills without limit")
    args = parser.parse_args()
    run(limit=10_000 if args.all else args.limit)
