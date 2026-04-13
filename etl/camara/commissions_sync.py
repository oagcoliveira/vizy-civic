"""
Commissions sync ETL: fetches committee memberships for all active deputies.

For each active politician in core.politicians (source = 'camara'):
  1. Calls GET /deputados/{external_id}/orgaos
  2. Upserts committees into core.committees
  3. Upserts memberships into core.committee_memberships

Usage:
    python -m camara.commissions_sync              # full sync
    python -m camara.commissions_sync --limit 20   # test run
"""

import argparse
from datetime import datetime, timezone

from sqlalchemy import text

from db import engine, log_run
from camara.client import get

JOB_NAME = "camara_commissions_sync"


def run(limit: int | None = None):
    started_at = datetime.now(timezone.utc)

    # Fetch all active deputies
    with engine.connect() as conn:
        query = "SELECT id, external_id FROM core.politicians WHERE source = 'camara' AND is_active = TRUE ORDER BY id"
        if limit:
            query += f" LIMIT {limit}"
        politicians = conn.execute(text(query)).fetchall()

    total = len(politicians)
    print(f"Syncing commissions for {total} active deputies{'  (test run)' if limit else ''}...", flush=True)

    committees_upserted = 0
    memberships_upserted = 0

    for i, (politician_id, external_id) in enumerate(politicians, 1):
        if i % 50 == 0 or i == 1:
            print(f"  {i}/{total} (politician_id={politician_id})", flush=True)

        try:
            orgaos = get(f"/deputados/{external_id}/orgaos", {"itens": 100}).get("dados", [])
        except Exception as e:
            print(f"    WARNING: could not fetch orgaos for {external_id}: {e}", flush=True)
            continue

        for orgao in orgaos:
            committee_external_id = str(orgao.get("idOrgao", ""))
            if not committee_external_id:
                continue

            acronym = (orgao.get("siglaOrgao") or "")[:50] or None
            name = (orgao.get("nomePublicacao") or orgao.get("nomeOrgao") or "")[:500] or None
            role = (orgao.get("titulo") or "")[:100] or None

            # Parse dates
            started_at_str = orgao.get("dataInicio")
            ended_at_str = orgao.get("dataFim")
            started_at_val = started_at_str[:10] if started_at_str else None
            ended_at_val = ended_at_str[:10] if ended_at_str else None

            with engine.begin() as conn:
                # Upsert committee
                committee_row = conn.execute(text("""
                    INSERT INTO core.committees (source, external_id, acronym, name, is_active)
                    VALUES ('camara', :eid, :acronym, :name, TRUE)
                    ON CONFLICT (source, external_id) DO UPDATE
                        SET acronym = EXCLUDED.acronym,
                            name = EXCLUDED.name
                    RETURNING id
                """), {
                    "eid": committee_external_id,
                    "acronym": acronym,
                    "name": name,
                }).fetchone()

                if not committee_row:
                    continue

                committee_id = committee_row[0]
                committees_upserted += 1

                # Upsert membership
                conn.execute(text("""
                    INSERT INTO core.committee_memberships
                        (politician_id, committee_id, role, started_at, ended_at)
                    VALUES (:pid, :cid, :role, :started, :ended)
                    ON CONFLICT (politician_id, committee_id) DO UPDATE
                        SET role = EXCLUDED.role,
                            started_at = EXCLUDED.started_at,
                            ended_at = EXCLUDED.ended_at
                """), {
                    "pid": politician_id,
                    "cid": committee_id,
                    "role": role,
                    "started": started_at_val,
                    "ended": ended_at_val,
                })
                memberships_upserted += 1

    finished_at = datetime.now(timezone.utc)
    log_run(JOB_NAME, "success", committees_upserted, memberships_upserted, 0,
            params={"limit": limit})

    print(f"Done! {committees_upserted} committee rows, {memberships_upserted} memberships.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process this many deputies")
    args = parser.parse_args()
    run(limit=args.limit)
