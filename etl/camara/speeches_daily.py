"""
Daily ETL: Câmara deputy speeches (discursos).

Fetches speeches for all active deputies since the last successful run.

Usage:
    python -m camara.speeches_daily
"""

import sys
from datetime import date

from sqlalchemy import text

from db import engine, last_successful_run, log_run
from camara.client import paginate, get

JOB_NAME = "camara_speeches_daily"


def run():
    since = last_successful_run(JOB_NAME) or date.today().strftime("%Y-%m-01")
    today = date.today().isoformat()
    print(f"[{JOB_NAME}] Fetching speeches from {since} to {today}")

    try:
        with engine.begin() as conn:
            deputies = conn.execute(
                text("SELECT id, external_id FROM core.politicians WHERE source = 'camara' AND is_active = TRUE")
            ).fetchall()

        fetched = inserted = 0

        for dep_id, dep_ext_id in deputies:
            speeches = paginate(
                f"/deputados/{dep_ext_id}/discursos",
                {"dataInicio": since, "dataFim": today, "ordenarPor": "dataHoraInicio", "ordem": "ASC"},
            )
            fetched += len(speeches)

            with engine.begin() as conn:
                for s in speeches:
                    external_id = s.get("dataHoraInicio", "") + str(dep_ext_id)
                    res = conn.execute(
                        text("""
                            INSERT INTO core.speeches
                                (source, external_id, politician_id, delivered_at, phase, full_text_url)
                            VALUES ('camara', :eid, :pid, :at, :phase, :url)
                            ON CONFLICT (source, external_id) DO NOTHING
                            RETURNING id
                        """),
                        {
                            "eid": external_id,
                            "pid": dep_id,
                            "at": s.get("dataHoraInicio"),
                            "phase": s.get("faseEvento", {}).get("titulo"),
                            "url": s.get("urlTexto"),
                        },
                    )
                    if res.fetchone():
                        inserted += 1

        log_run(JOB_NAME, "success", fetched, inserted, params={"since": since})
        print(f"[{JOB_NAME}] Done — {fetched} fetched, {inserted} inserted")

    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    run()
