"""
One-off (then weekly): sync all parties from Câmara API into core.parties.

Populates full name, website URL. Fixes encoding issues from auto-created rows.

Usage:
    cd etl
    python -m camara.parties_sync
"""

import sys
from sqlalchemy import text
from db import engine, log_run
from camara.client import paginate, get

JOB_NAME = "camara_parties_sync"


def run():
    print(f"[{JOB_NAME}] Fetching parties from Câmara API...")

    try:
        parties = paginate("/partidos", {"ordem": "ASC", "ordenarPor": "sigla"})
        print(f"[{JOB_NAME}] Got {len(parties)} parties")

        upserted = 0
        with engine.begin() as conn:
            for p in parties:
                acronym = p.get("sigla", "").strip()
                if not acronym:
                    continue

                # Fetch detail for full name and website
                detail = get(f"/partidos/{p['id']}").get("dados", {})
                full_name = detail.get("nome") or p.get("nome") or acronym
                website = detail.get("urlWebSite") or detail.get("urlFacebook") or None

                conn.execute(
                    text("""
                        INSERT INTO core.parties (acronym, name, website_url)
                        VALUES (:acronym, :name, :website)
                        ON CONFLICT (acronym) DO UPDATE SET
                            name        = EXCLUDED.name,
                            website_url = COALESCE(EXCLUDED.website_url, core.parties.website_url)
                    """),
                    {"acronym": acronym, "name": full_name, "website": website},
                )
                upserted += 1
                print(f"  {acronym:15s} → {full_name}", flush=True)

        log_run(JOB_NAME, "success", len(parties), upserted, 0)
        print(f"[{JOB_NAME}] Done — {upserted} parties upserted")

    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    run()
