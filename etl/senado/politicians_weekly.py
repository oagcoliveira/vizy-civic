"""
Weekly ETL: Sync all active Senators.

Usage:
    python -m senado.politicians_weekly
"""

import sys

from sqlalchemy import text

from db import engine, log_run
from senado.client import get

JOB_NAME = "senado_politicians_weekly"


def run():
    print(f"[{JOB_NAME}] Fetching current senators")

    try:
        data = get("/senador/lista/atual")
        senators = (
            data.get("ListaParlamentarEmExercicio", {})
                .get("Parlamentares", {})
                .get("Parlamentar", [])
        )
        fetched = len(senators)
        inserted = updated = 0

        with engine.begin() as conn:
            for s in senators:
                ident = s.get("IdentificacaoParlamentar", {})
                ext_id = ident.get("CodigoParlamentar")
                party_acronym = ident.get("SiglaPartidoParlamentar", "")

                if party_acronym:
                    conn.execute(
                        text("INSERT INTO core.parties (acronym, name) VALUES (:a, :n) ON CONFLICT (acronym) DO NOTHING"),
                        {"a": party_acronym, "n": party_acronym},
                    )
                    party_row = conn.execute(
                        text("SELECT id FROM core.parties WHERE acronym = :a"), {"a": party_acronym}
                    ).fetchone()
                    party_id = party_row[0] if party_row else None
                else:
                    party_id = None

                res = conn.execute(
                    text("""
                        INSERT INTO core.politicians
                            (source, external_id, name, short_name, photo_url,
                             party_id, state, current_office, is_active)
                        VALUES
                            ('senado', :eid, :name, :short_name, :photo,
                             :party_id, :state, 'senador', TRUE)
                        ON CONFLICT (source, external_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            party_id = EXCLUDED.party_id,
                            state = EXCLUDED.state,
                            updated_at = now()
                        RETURNING (xmax = 0) AS was_inserted
                    """),
                    {
                        "eid": ext_id,
                        "name": ident.get("NomeParlamentar", ""),
                        "short_name": ident.get("NomeParlamentar"),
                        "photo": ident.get("UrlFotoParlamentar"),
                        "party_id": party_id,
                        "state": ident.get("UfParlamentar"),
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
