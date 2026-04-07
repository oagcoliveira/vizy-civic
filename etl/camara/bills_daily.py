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
    try:
        autores = get(f"/proposicoes/{external_id}/autores").get("dados", [])
        if autores:
            names = [a.get("nome", "") for a in autores[:3] if a.get("nome")]
            author_label = "; ".join(names) if names else None
    except Exception:
        pass

    return {
        "status": status,
        "full_text_url": full_text_url,
        "keywords": keywords,
        "author_label": author_label,
    }


def generate_ai_enrichment(ementa: str, title: str | None, bill_type: str | None,
                            number: int | None, year: int | None) -> dict:
    """Use Claude Sonnet to generate short_title and summary from the ementa."""
    if not ANTHROPIC_API_KEY:
        return {}

    bill_ref = f"{bill_type} {number}/{year}" if bill_type and number and year else title or "Sem título"
    prompt = (
        f"Você é um assistente de tecnologia cívica. Analise esta proposição legislativa brasileira.\n\n"
        f"Referência: {bill_ref}\n"
        f"Ementa: {ementa}\n\n"
        f"Responda APENAS com JSON no formato:\n"
        f'{{"short_title": "título curto em até 12 palavras", "summary": "resumo em 2 frases em português simples, sem jargão jurídico"}}'
    )

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        text = message.content[0].text.strip()
        # Extract JSON even if wrapped in markdown code block
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        result = json.loads(text)
        return {
            "short_title": result.get("short_title"),
            "summary": result.get("summary"),
        }
    except Exception as e:
        print(f"    WARNING: AI enrichment failed: {e}", flush=True)
        return {}


def run(limit: int | None = None):
    # Fetch bills that haven't been enriched yet (status IS NULL = not fetched from detail API)
    with engine.connect() as conn:
        query = "SELECT id, external_id, type, number, year, title, ementa FROM core.bills WHERE source = 'camara' AND status IS NULL ORDER BY id"
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
                    short_title = COALESCE(:short_title, short_title),
                    summary = COALESCE(:summary, summary),
                    updated_at = now()
                WHERE id = :id
            """), {
                "id": bill_id,
                "status": detail.get("status"),
                "full_text_url": detail.get("full_text_url"),
                "author_label": detail.get("author_label"),
                "short_title": ai.get("short_title"),
                "summary": ai.get("summary"),
            })

    print(f"Done! Enriched {total} bills.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process this many bills (for testing)")
    args = parser.parse_args()
    run(limit=args.limit)
