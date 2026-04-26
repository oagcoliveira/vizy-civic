"""
AI enrichment runner: generates summary and keywords for speeches.

Priority for content to summarise:
  1. transcricao  — verbatim transcript stored from the Câmara API (best)
  2. summary      — the API's own short summary (sumario field), used as context
  3. phase        — bureaucratic session label (last resort, least useful)

Reads speeches without an AI-generated summary (where summary IS NULL), calls
Claude Haiku, and writes back summary + keywords.

Note: speeches where the API already provided a sumario have summary pre-filled
by the ETL. This script only processes rows where summary is still NULL, which
typically means the API returned no sumario and we need to derive one from the
transcript.

Usage (from backend/):
    python enrich_speeches.py            # enriches up to 50 at a time
    python enrich_speeches.py --limit 10 # smaller batch for testing
    python enrich_speeches.py --all      # no limit (runs until done)
"""

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv(override=True)

from anthropic import Anthropic
from sqlalchemy import create_engine, text

from app.config import settings

engine = create_engine(settings.database_url)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

JOB_NAME = "enrich_speeches"


def log_run(status: str, fetched: int = 0, updated: int = 0, error: str | None = None) -> None:
    """Record this enrichment run in jobs.etl_runs."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO jobs.etl_runs
                        (job_name, started_at, finished_at, status,
                         records_fetched, records_updated, error_message)
                    VALUES (:job, now(), now(), :status,
                            :fetched, :updated, :error)
                """),
                {
                    "job": JOB_NAME,
                    "status": status,
                    "fetched": fetched,
                    "updated": updated,
                    "error": error,
                },
            )
    except Exception as log_exc:
        print(f"[{JOB_NAME}] could not write to etl_runs — {log_exc}", file=sys.stderr)


def fetch_batch(conn, limit: int) -> list[dict]:
    rows = conn.execute(
        text("""
            SELECT s.id, s.phase, s.transcricao, s.full_text_url, s.delivered_at,
                   p.short_name AS politician_name
            FROM core.speeches s
            LEFT JOIN core.politicians p ON p.id = s.politician_id
            WHERE s.summary IS NULL
              AND (s.transcricao IS NOT NULL OR s.phase IS NOT NULL)
            ORDER BY s.id
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def generate_speech_enrichment(
    transcricao: str | None,
    phase: str | None,
    politician_name: str | None,
) -> dict:
    """Call Claude Haiku to generate summary and keywords for a speech.

    Uses transcricao (verbatim transcript) when available; falls back to phase.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    speaker = politician_name or "Deputado(a)"

    if transcricao and len(transcricao.strip()) > 20:
        # We have a real transcript — summarise it properly
        content_label = "Transcrição do discurso"
        content_text = transcricao[:4000]
        instruction = (
            "Resuma o discurso em 3 frases em português simples, descrevendo o que foi dito e a posição do parlamentar."
        )
    else:
        # Only the bureaucratic phase label — produce a minimal summary
        content_label = "Fase/contexto do discurso"
        content_text = phase or "(sem texto disponível)"
        instruction = (
            "Com base apenas no contexto disponível, escreva uma frase curta em português simples "
            "descrevendo o tipo de participação do parlamentar."
        )

    prompt = (
        f"Você é um assistente de tecnologia cívica. Analise este discurso parlamentar brasileiro.\n\n"
        f"Parlamentar: {speaker}\n"
        f"{content_label}: {content_text}\n\n"
        f"{instruction}\n"
        f"Extraia também 3-7 palavras-chave relevantes.\n\n"
        f"Responda APENAS com JSON no formato:\n"
        f'{{"summary": "resumo aqui", "keywords": ["palavra1", "palavra2", "palavra3"]}}'
    )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if not raw:
        raise ValueError("Anthropic returned an empty response — possible rate limit or content filter")
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
        log_run("success", fetched=0, updated=0)
        return

    has_transcript = sum(1 for r in batch if r.get("transcricao"))
    print(f"Enriching {len(batch)} speeches ({has_transcript} with full transcript, "
          f"{len(batch) - has_transcript} phase-only)...")
    ok = failed = 0

    try:
        for item in batch:
            label = f"id={item['id']} ({item['politician_name'] or 'unknown'})"
            try:
                enrichment = generate_speech_enrichment(
                    transcricao=item.get("transcricao"),
                    phase=item.get("phase"),
                    politician_name=item.get("politician_name"),
                )

                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE core.speeches
                            SET summary = :summary,
                                keywords = :keywords
                            WHERE id = :id
                        """),
                        {
                            "id": item["id"],
                            "summary": enrichment.get("summary"),
                            "keywords": enrichment.get("keywords"),
                        },
                    )

                src = "transcript" if item.get("transcricao") else "phase"
                print(f"  [{ok + failed + 1}/{len(batch)}] {label} [{src}] — ok")
                ok += 1

            except Exception as exc:
                print(f"  [{ok + failed + 1}/{len(batch)}] {label} — FAILED: {exc}", file=sys.stderr)
                failed += 1

            finally:
                # Respect Anthropic rate limits: small delay between every call
                time.sleep(0.5)

        print(f"\nDone — {ok} enriched, {failed} failed.")
        log_run("success", fetched=len(batch), updated=ok)

    except Exception as exc:
        print(f"[{JOB_NAME}] unexpected error — {exc}", file=sys.stderr)
        log_run("failed", fetched=len(batch), updated=ok, error=str(exc))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="Max speeches to process (default: 50)")
    parser.add_argument("--all", action="store_true", help="Process all speeches without summary")
    args = parser.parse_args()

    limit = 10_000 if args.all else args.limit
    run(limit)
