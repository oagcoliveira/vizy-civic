"""
Daily ETL: Câmara nominal votes.

Fetches new votações since last successful run, then fetches individual votes
for each nominal votação and upserts into core.votacoes and core.individual_votes.

Usage:
    python -m camara.votes_daily
"""

import json
import sys
from datetime import date

from sqlalchemy import text

from db import engine, last_successful_run, log_run
from camara.client import paginate, get

JOB_NAME = "camara_votes_daily"


def run():
    since = last_successful_run(JOB_NAME) or "2019-01-01"
    today = date.today().isoformat()
    print(f"[{JOB_NAME}] Fetching votações from {since} to {today}")

    try:
        votacoes = paginate("/votacoes", {"dataInicio": since, "dataFim": today, "ordem": "ASC"})
        fetched = len(votacoes)
        inserted = updated = 0

        with engine.begin() as conn:
            for v in votacoes:
                row = {
                    "source": "camara",
                    "external_id": str(v["id"]),
                    "description": v.get("descricao"),
                    "voted_at": v.get("dataHoraInicio"),
                    "vote_type": "nominal" if v.get("tipoVotacao") == "Nominal" else v.get("tipoVotacao"),
                    "result": v.get("aprovacao"),
                    "session_label": v.get("siglaOrgao"),
                }
                res = conn.execute(
                    text("""
                        INSERT INTO core.votacoes (source, external_id, description, voted_at, vote_type, result, session_label)
                        VALUES (:source, :external_id, :description, :voted_at, :vote_type, :result, :session_label)
                        ON CONFLICT (source, external_id) DO UPDATE
                            SET description = EXCLUDED.description,
                                result = EXCLUDED.result
                        RETURNING (xmax = 0) AS was_inserted
                    """),
                    row,
                )
                was_inserted = res.fetchone()[0]
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1

                # Fetch individual votes for nominal votações
                if v.get("tipoVotacao") == "Nominal":
                    _upsert_individual_votes(conn, v["id"])

        log_run(JOB_NAME, "success", fetched, inserted, updated, params={"since": since})
        print(f"[{JOB_NAME}] Done — {fetched} fetched, {inserted} inserted, {updated} updated")

    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr)
        raise


def _upsert_individual_votes(conn, votacao_external_id: str):
    votos = get(f"/votacoes/{votacao_external_id}/votos").get("dados", [])
    orientacoes = {
        o["siglaPartidoLider"]: o["orientacao"]
        for o in get(f"/votacoes/{votacao_external_id}/orientacoes").get("dados", [])
    }

    votacao_id_row = conn.execute(
        text("SELECT id FROM core.votacoes WHERE source = 'camara' AND external_id = :eid"),
        {"eid": str(votacao_external_id)},
    ).fetchone()
    if not votacao_id_row:
        return
    votacao_id = votacao_id_row[0]

    for voto in votos:
        dep_external_id = voto.get("deputado_", {}).get("id")
        if not dep_external_id:
            continue
        politician = conn.execute(
            text("SELECT id FROM core.politicians WHERE source = 'camara' AND external_id = :eid"),
            {"eid": dep_external_id},
        ).fetchone()
        if not politician:
            continue

        party = voto.get("deputado_", {}).get("siglaPartido", "")
        orientation = orientacoes.get(party)
        vote_value = voto.get("voto", "")
        followed = (vote_value == orientation) if orientation else None

        conn.execute(
            text("""
                INSERT INTO core.individual_votes
                    (votacao_id, politician_id, vote, party_at_time, party_orientation, followed_orientation)
                VALUES (:vid, :pid, :vote, :party, :orientation, :followed)
                ON CONFLICT (votacao_id, politician_id) DO NOTHING
            """),
            {
                "vid": votacao_id,
                "pid": politician[0],
                "vote": vote_value,
                "party": party,
                "orientation": orientation,
                "followed": followed,
            },
        )


if __name__ == "__main__":
    run()
