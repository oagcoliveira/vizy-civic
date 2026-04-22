"""
Bills ETL: Enriches core.bills rows with full detail from the Câmara API.

For each bill in core.bills where status IS NULL (not yet fetched from the detail
endpoint), calls GET /proposicoes/{external_id} and updates:
  - status (descricaoSituacao)
  - keywords
  - full_text_url (urlInteiroTeor)
  - author_label (from /proposicoes/{id}/autores)

Then runs AI enrichment (Claude Sonnet) to generate short_title and summary for
bills that have ementa but no short_title yet.

Usage:
    # Test run — 20 bills only
    python -m camara.bills_daily --limit 20

    # Full run
    python -m camara.bills_daily
"""

import sys
import os
import argparse

from dotenv import load_dotenv
load_dotenv(override=True)  # must come before reading env vars so .env wins over system env

from sqlalchemy import text
from anthropic import Anthropic

from db import engine
from camara.client import get

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def fetch_bill_detail(external_id: int) -> dict:
    """Fetch full detail for one bill from the Câmara API."""
    try:
        data = get(f"/proposicoes/{external_id}").get("dados", {})
    except Exception as e:
        print(f"    WARNING: could not fetch /proposicoes/{external_id}: {e}", flush=True)
        return {}

    status_info = data.get("statusProposicao") or {}
    status = status_info.get("descricaoSituacao")
    full_text_url = data.get("urlInteiroTeor")
    keywords_raw = data.get("keywords", "") or ""
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else None

    # Fetch author(s)
    author_label = None
    author_external_id = None  # Câmara deputy ID, if single-deputy author
    try:
        autores = get(f"/proposicoes/{external_id}/autores").get("dados", [])
        if autores:
            names = [a.get("nome", "") for a in autores[:3] if a.get("nome")]
            author_label = "; ".join(names) if names else None
            # If exactly one author with a deputy URI, extract their external ID
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
        "keywords": keywords,
        "author_label": author_label,
        "author_external_id": author_external_id,
    }


POLICY_AREAS = [
    "Saúde", "Educação", "Economia e Finanças", "Meio Ambiente", "Segurança Pública",
    "Agricultura e Agropecuária", "Infraestrutura e Transportes", "Direitos Humanos",
    "Administração Pública", "Ciência e Tecnologia", "Cultura e Esporte",
    "Trabalho e Emprego", "Previdência Social", "Relações Exteriores e Defesa",
    "Tributos e Fiscalidade", "Habitação e Urbanismo", "Justiça e Legislação",
    "Comunicação e Mídia", "Energia", "Assistência Social",
]


def generate_ai_enrichment(ementa: str, title: str | None, bill_type: str | None,
                            number: int | None, year: int | None) -> dict:
    """Use Claude Sonnet to generate short_title, summary, and policy_area from the ementa."""
    if not ANTHROPIC_API_KEY:
        return {}

    import json as _json

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

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Extract JSON even if wrapped in markdown code block
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        result = _json.loads(raw)
        policy_area = result.get("policy_area")
        # Only accept known areas
        if policy_area not in POLICY_AREAS:
            policy_area = None
        return {
            "short_title": result.get("short_title"),
            "summary": result.get("summary"),
            "policy_area": policy_area,
        }
    except Exception as e:
        print(f"    WARNING: AI enrichment failed: {e}", flush=True)
        return {}


def backfill_author_ids():
    """
    One-time backfill: match author_label (single author, no semicolons) against
    core.politicians.short_name to populate author_politician_id for existing bills.
    """
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE core.bills b
            SET author_politician_id = p.id, updated_at = now()
            FROM core.politicians p
            WHERE b.author_politician_id IS NULL
              AND b.author_label NOT LIKE '%;%'
              AND lower(p.short_name) = lower(b.author_label)
        """))
        count = result.rowcount
    if count:
        print(f"  Backfilled author_politician_id for {count} bills via short_name match.", flush=True)


def run(limit: int | None = None):
    # Backfill author IDs for existing bills (idempotent — only updates NULL rows)
    backfill_author_ids()

    # Only enrich substantive bill types — other types (REQ, EMC, PAR, etc.) are stored
    # but not enriched unless explicitly requested later.
    ENRICH_TYPES = ("PL", "PLP", "PEC", "MPV", "PDL", "PRC", "MSC", "TVR", "PLN", "PDC")

    with engine.connect() as conn:
        query = f"""
            SELECT id, external_id, type, number, year, title, ementa FROM core.bills
            WHERE source = 'camara'
              AND type IN {ENRICH_TYPES}
              AND (status IS NULL OR short_title IS NULL OR policy_area IS NULL)
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        rows = conn.execute(text(query)).fetchall()

    total = len(rows)
    print(f"Enriching {total} bills from Câmara API{'  (test run)' if limit else ''}...", flush=True)

    for i, row in enumerate(rows, 1):
        bill_id, ext_id, bill_type, number, year, title, ementa = row
        if i % 20 == 0 or i == 1:
            print(f"  {i}/{total} (id={bill_id}, ext={ext_id})", flush=True)

        detail = fetch_bill_detail(ext_id)

        # Resolve author_politician_id from the deputy URI returned by the autores API
        author_politician_id = None
        if detail.get("author_external_id"):
            with engine.connect() as conn:
                row_pol = conn.execute(text("""
                    SELECT id FROM core.politicians
                    WHERE source = 'camara' AND external_id = :eid
                """), {"eid": detail["author_external_id"]}).fetchone()
                if row_pol:
                    author_politician_id = row_pol[0]

        # AI enrichment if ementa exists and no short_title yet
        ai = {}
        if ementa and not detail.get("short_title"):
            ai = generate_ai_enrichment(ementa, title, bill_type, number, year)

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE core.bills SET
                    status = COALESCE(:status, status),
                    full_text_url = COALESCE(:full_text_url, full_text_url),
                    author_label = COALESCE(:author_label, author_label),
                    author_politician_id = COALESCE(:author_politician_id, author_politician_id),
                    short_title = COALESCE(:short_title, short_title),
                    summary = COALESCE(:summary, summary),
                    policy_area = COALESCE(:policy_area, policy_area),
                    updated_at = now()
                WHERE id = :id
            """), {
                "id": bill_id,
                "status": detail.get("status"),
                "full_text_url": detail.get("full_text_url"),
                "author_label": detail.get("author_label"),
                "author_politician_id": author_politician_id,
                "short_title": ai.get("short_title"),
                "summary": ai.get("summary"),
                "policy_area": ai.get("policy_area"),
            })

    print(f"Done! Enriched {total} bills.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process this many bills (for testing)")
    args = parser.parse_args()
    run(limit=args.limit)
