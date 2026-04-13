"""
AI enrichment runner: generates plain-language labels for legislative events.

Reads core.legislative_events without a summary, calls Claude Sonnet to
translate bureaucratic stage names into human-readable Portuguese, and
writes the result back as the 'summary' column.

Usage (from backend/):
    python enrich_legislative_events.py            # enriches up to 100 at a time
    python enrich_legislative_events.py --limit 20 # smaller batch for testing
    python enrich_legislative_events.py --all      # no limit (runs until done)
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
            SELECT id, stage, description, venue
            FROM core.legislative_events
            WHERE summary IS NULL
              AND (stage IS NOT NULL OR description IS NOT NULL)
            ORDER BY id
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def generate_plain_label(stage: str | None, description: str | None, venue: str | None) -> str | None:
    """Call Claude Sonnet to translate a bureaucratic legislative stage to plain Portuguese."""
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
        f"Você é um assistente de tecnologia cívica. Traduza esta etapa legislativa burocrática "
        f"para uma frase curta e clara em português simples (máximo 10 palavras), "
        f"como se explicasse para um cidadão leigo.\n\n"
        f"{context}\n\n"
        f'Responda APENAS com JSON no formato: {{"label": "frase em português simples"}}'
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


def run(limit: int):
    with engine.connect() as conn:
        batch = fetch_batch(conn, limit)

    if not batch:
        print("No legislative events without summary — nothing to do.")
        return

    print(f"Enriching {len(batch)} legislative events...")
    ok = failed = 0

    for item in batch:
        label = f"id={item['id']}"
        try:
            plain = generate_plain_label(
                stage=item["stage"],
                description=item["description"],
                venue=item["venue"],
            )

            if plain:
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE core.legislative_events SET summary = :s WHERE id = :id"),
                        {"s": plain, "id": item["id"]},
                    )
                print(f"  [{ok + failed + 1}/{len(batch)}] {label} — ok: {plain}")
            else:
                print(f"  [{ok + failed + 1}/{len(batch)}] {label} — skipped (no input)")

            ok += 1

        except Exception as exc:
            print(f"  [{ok + failed + 1}/{len(batch)}] {label} — FAILED: {exc}", file=sys.stderr)
            failed += 1

    print(f"\nDone — {ok} enriched, {failed} failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="Max events to process (default: 100)")
    parser.add_argument("--all", action="store_true", help="Process all events without summary")
    args = parser.parse_args()

    limit = 10_000 if args.all else args.limit
    run(limit)
