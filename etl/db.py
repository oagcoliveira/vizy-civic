import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])


def log_run(job_name: str, status: str, fetched: int = 0, inserted: int = 0,
            updated: int = 0, error: str | None = None, params: dict | None = None):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO jobs.etl_runs
                    (job_name, started_at, finished_at, status,
                     records_fetched, records_inserted, records_updated, error_message, params)
                VALUES
                    (:job, now(), now(), :status,
                     :fetched, :inserted, :updated, :error, :params::jsonb)
            """),
            {
                "job": job_name,
                "status": status,
                "fetched": fetched,
                "inserted": inserted,
                "updated": updated,
                "error": error,
                "params": str(params or {}),
            },
        )


def last_successful_run(job_name: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT finished_at FROM jobs.etl_runs
                WHERE job_name = :job AND status = 'success'
                ORDER BY finished_at DESC LIMIT 1
            """),
            {"job": job_name},
        ).fetchone()
    return row[0].strftime("%Y-%m-%d") if row else None
