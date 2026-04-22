"""
Daily ETL: Câmara deputy speeches (discursos).

Fetches speeches for all active deputies since the last successful run.

Usage:
    python -m camara.speeches_daily
"""

import sys
import argparse
from datetime import date

from sqlalchemy import text

from db import engine, last_successful_run, log_run
from camara.client import paginate, get

JOB_NAME = "camara_speeches_daily"


def run(since_override: str | None = None):
    since = since_override or last_successful_run(JOB_NAME) or date.today().strftime("%Y-%m-01")
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
                    # Parse keywords from comma-separated string
                    kw_raw = s.get("keywords") or ""
                    keywords = [k.strip() for k in kw_raw.split(",") if k.strip()] or None
                    res = conn.execute(
                        text("""
                            INSERT INTO core.speeches
                                (source, external_id, politician_id, delivered_at, phase, summary, keywords, full_text_url)
                            VALUES ('camara', :eid, :pid, :at, :phase, :summary, :keywords, :url)
                            ON CONFLICT (source, external_id) DO UPDATE SET
                                summary = COALESCE(EXCLUDED.summary, core.speeches.summary),
                                keywords = COALESCE(EXCLUDED.keywords, core.speeches.keywords),
                                full_text_url = COALESCE(EXCLUDED.full_text_url, core.speeches.full_text_url)
                            RETURNING id
                        """),
                        {
                            "eid": external_id,
                            "pid": dep_id,
                            "at": s.get("dataHoraInicio"),
                            "phase": s.get("faseEvento", {}).get("titulo"),
                            "summary": s.get("sumario") or None,
                            "keywords": keywords,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=str, default=None, help="Fetch speeches from this date (YYYY-MM-DD). Overrides last successful run date.")
    args = parser.parse_args()
    run(since_override=args.since)
