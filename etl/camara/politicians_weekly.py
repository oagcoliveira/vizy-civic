"""
Weekly ETL: Sync all active Câmara deputies.

Upserts politicians into core.politicians and updates party/committee data.

Usage:
    python -m camara.politicians_weekly
"""

import sys

from sqlalchemy import text

from db import engine, log_run
from camara.client import paginate, get

JOB_NAME = "camara_politicians_weekly"


def run():
    print(f"[{JOB_NAME}] Fetching all active deputies")

    try:
        deputies = paginate("/deputados", {"ordem": "ASC", "ordenarPor": "nome"})
        fetched = len(deputies)
        inserted = updated = 0

        with engine.begin() as conn:
            for dep in deputies:
                detail = get(f"/deputados/{dep['id']}").get("dados", {})
                party_acronym = dep.get("siglaPartido", "")

                # Upsert party
                if party_acronym:
                    conn.execute(
                        text("""
                            INSERT INTO core.parties (acronym, name)
                            VALUES (:acronym, :name)
                            ON CONFLICT (acronym) DO NOTHING
                        """),
                        {"acronym": party_acronym, "name": party_acronym},
                    )
                    party_row = conn.execute(
                        text("SELECT id FROM core.parties WHERE acronym = :a"),
                        {"a": party_acronym},
                    ).fetchone()
                    party_id = party_row[0] if party_row else None
                else:
                    party_id = None

                res = conn.execute(
                    text("""
                        INSERT INTO core.politicians
                            (source, external_id, name, short_name, photo_url,
                             gender, email, cpf, party_id, state, current_office, is_active)
                        VALUES
                            ('camara', :eid, :name, :short_name, :photo,
                             :gender, :email, :cpf, :party_id, :state, 'deputado', TRUE)
                        ON CONFLICT (source, external_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            short_name = EXCLUDED.short_name,
                            cpf = COALESCE(EXCLUDED.cpf, core.politicians.cpf),
                            party_id = EXCLUDED.party_id,
                            state = EXCLUDED.state,
                            photo_url = EXCLUDED.photo_url,
                            updated_at = now()
                        RETURNING (xmax = 0) AS was_inserted
                    """),
                    {
                        "eid": dep["id"],
                        "name": detail.get("nomeCivil", dep.get("nome", "")),
                        "short_name": dep.get("nome"),
                        "photo": dep.get("urlFoto"),
                        "gender": detail.get("sexo"),
                        "email": detail.get("ultimoStatus", {}).get("email"),
                        "cpf": detail.get("cpf"),
                        "party_id": party_id,
                        "state": dep.get("siglaUf"),
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
