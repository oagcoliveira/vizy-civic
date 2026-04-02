"""
Daily ETL: Senado plenary votes.

Fetches today's plenary vote list, then individual senator votes.

Usage:
    python -m senado.votes_daily
"""

import sys
from datetime import date

from sqlalchemy import text

from db import engine, last_successful_run, log_run
from senado.client import get, to_date_str

JOB_NAME = "senado_votes_daily"


def run():
    since = last_successful_run(JOB_NAME) or date.today().strftime("%Y-%m-01")
    today = date.today()
    print(f"[{JOB_NAME}] Fetching votes for {today.isoformat()}")

    try:
        date_str = to_date_str(today.isoformat())
        data = get(f"/plenario/lista/votacoes/{date_str}")
        votacoes = (
            data.get("ListaVotacoes", {})
                .get("Votacoes", {})
                .get("Votacao", [])
        )
        if isinstance(votacoes, dict):
            votacoes = [votacoes]

        fetched = len(votacoes)
        inserted = updated = 0

        with engine.begin() as conn:
            for v in votacoes:
                external_id = v.get("CodigoSessaoVotacao", "")
                res = conn.execute(
                    text("""
                        INSERT INTO core.votacoes (source, external_id, description, voted_at, result)
                        VALUES ('senado', :eid, :desc, :at, :result)
                        ON CONFLICT (source, external_id) DO UPDATE SET result = EXCLUDED.result
                        RETURNING (xmax = 0) AS was_inserted
                    """),
                    {
                        "eid": external_id,
                        "desc": v.get("DescricaoVotacao"),
                        "at": v.get("DataSessao"),
                        "result": v.get("Resultado"),
                    },
                )
                if res.fetchone()[0]:
                    inserted += 1
                else:
                    updated += 1

        log_run(JOB_NAME, "success", fetched, inserted, updated)
        print(f"[{JOB_NAME}] Done — {fetched} fetched, {inserted} inserted, {updated} updated")

    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    run()
