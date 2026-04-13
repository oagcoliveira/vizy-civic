"""
AI enrichment runner: generates summary and keywords for speeches.

Reads speeches without summary, calls Claude Sonnet, writes back to DB.
Uses 'phase' (the speech text/phase field) as the content to summarize.

Usage (from backend/):
    python enrich_speeches.py            # enriches up to 50 at a time
    python enrich_speeches.py --limit 10 # smaller batch for testing
    python enrich_speeches.py --all      # no limit (runs until done)
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv(override=True)

from anthropic import Anthropic
from sqlalchemy import create_engine, text

from app.config import settings

engine = create_engine(settings.database_url)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def fetch_batch(conn, limit: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT s.id, s.phase, s.full_text_url, s.delivered_at,
                   p.short_name AS politician_name
            FROM core.speeches s
            LEFT JOIN core.politicians p ON p.id = s.politician_id
            WHERE s.summary IS NULL AND s.phase IS NOT NULL
            ORDER BY s.id
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def generate_speech_enrichment(phase: str, politician_name: str | None) -> dict:
    """Call Claude Sonnet to generate summary and keywords for a speech."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    speaker = politician_name or "Deputado(a)"
    prompt = (
        f"Você é um assistente de tecnologia cívica. Analise este resumo de discurso parlamentar brasileiro.\n\n"
        f"Parlamentar: {speaker}\n"
        f"Texto/fase do discurso: {phase[:2000]}\n\n"
        f"Responda APENAS com JSON no formato:\n"
        f'{{"summary": "resumo em 3 frases em português simples descrevendo o que foi dito", '
        f'"keywords": ["palavra1", "palavra2", "palavra3", "palavra4", "palavra5"]}}'
    )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    result = json.loads(raw)

    keywords = result.get("keywords", [])
    if isinstance(keywords, list):
        keywords = [str(k) for k in keywords[:7]]
    else:
        keywords = []

    return {
        "summary": result.get("summary"),
        "keywords": keywords or None,
    }


def run(limit: int):
    with engine.connect() as conn:
        batch = fetch_batch(conn, limit)

    if not batch:
        print("No speeches without summary — nothing to do.")
        return

    print(f"Enriching {len(batch)} speeches...")
    ok = failed = 0

    for item in batch:
        label = f"id={item['id']} ({item['politician_name'] or 'unknown'})"
        try:
            enrichment = generate_speech_enrichment(
                phase=item["phase"],
                politician_name=item["politician_name"],
            )

            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE core.speeches
                        SET summary = :summary,
                            keywords = :keywords,
                            updated_at = now()
                        WHERE id = :id
                    """),
                    {
                        "id": item["id"],
                        "summary": enrichment.get("summary"),
                        "keywords": enrichment.get("keywords"),
                    },
                )

            print(f"  [{ok + failed + 1}/{len(batch)}] {label} — ok")
            ok += 1

        except Exception as exc:
            print(f"  [{ok + failed + 1}/{len(batch)}] {label} — FAILED: {exc}", file=sys.stderr)
            failed += 1

    print(f"\nDone — {ok} enriched, {failed} failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="Max speeches to process (default: 50)")
    parser.add_argument("--all", action="store_true", help="Process all speeches without summary")
    args = parser.parse_args()

    limit = 10_000 if args.all else args.limit
    run(limit)
