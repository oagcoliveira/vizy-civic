"""
Backfill proposicoesAfetadas for symbolic and committee votes that have no linked bills.

Fetches the votação detail from the Câmara API for each vote without bills and
upserts any linked proposições found.

Usage:
    python -m camara.backfill_vote_proposicoes              # since 2024-01-01 (default)
    python -m camara.backfill_vote_proposicoes --since 2023-01-01  # wider range
    python -m camara.backfill_vote_proposicoes --type symbolic      # only symbolic
    python -m camara.backfill_vote_proposicoes --type none          # only committee
"""

import argparse
import sys

from sqlalchemy import text

from db import engine
from camara.votes_daily import _upsert_proposicoes


def run(since: str = "2024-01-01", vote_type_filter: str | None = None):
    with engine.connect() as conn:
        type_clause = "AND v.vote_type = :vtype" if vote_type_filter else ""
        rows = conn.execute(text(f"""
            SELECT v.id, v.external_id, v.vote_type, v.session_label
            FROM core.votacoes v
            LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id
            WHERE v.vote_type IN ('symbolic', 'none')
            AND v.voted_at >= :since
            AND vb.bill_id IS NULL
            {type_clause}
            ORDER BY v.voted_at DESC
        """), {"since": since, "vtype": vote_type_filter}).fetchall()

    total = len(rows)
    print(f"[backfill_vote_proposicoes] {total} votes to backfill (since {since})", flush=True)
    found = 0

    for i, row in enumerate(rows, 1):
        if i % 50 == 0 or i == 1:
            print(f"[backfill_vote_proposicoes]   {i}/{total} (found bills for {found})", flush=True)
        try:
            with engine.begin() as conn:
                before = conn.execute(
                    text("SELECT COUNT(*) FROM core.votacao_bills WHERE votacao_id = :id"),
                    {"id": row.id},
                ).scalar()
                _upsert_proposicoes(conn, row.id, row.external_id)
                after = conn.execute(
                    text("SELECT COUNT(*) FROM core.votacao_bills WHERE votacao_id = :id"),
                    {"id": row.id},
                ).scalar()
                if after > before:
                    found += 1
        except Exception as e:
            print(f"[backfill_vote_proposicoes]   ERROR votacao {row.id} ({row.external_id}): {e}", file=sys.stderr)

    print(f"[backfill_vote_proposicoes] Done — {found}/{total} votes got bill links")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2024-01-01", help="Only backfill votes on or after this date (YYYY-MM-DD)")
    parser.add_argument("--type", dest="vote_type", choices=["symbolic", "none"], default=None, help="Limit to specific vote type")
    args = parser.parse_args()
    run(since=args.since, vote_type_filter=args.vote_type)
