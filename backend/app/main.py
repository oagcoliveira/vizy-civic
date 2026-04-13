import os
import subprocess
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine
from app.routers import auth, politicians, bills, votes, donations, feed, search, parties

# Read .env files directly so subprocesses get the right values
# (pydantic-settings loads into settings object, not os.environ)
_BACKEND_ENV = dotenv_values(Path(__file__).parent.parent / ".env")
_ETL_ENV = dotenv_values(Path(__file__).parent.parent.parent / "etl" / ".env")

# Path to the etl/ directory (two levels up from backend/app/)
ETL_DIR = Path(__file__).parent.parent.parent / "etl"

# Map of ETL job names → Python module paths (run as `python -m <module>` in ETL_DIR)
ETL_JOBS = {
    "camara_votes_daily": "camara.votes_daily",
    "camara_bills_daily": "camara.bills_daily",
    "camara_bills_tramitacoes_daily": "camara.bills_tramitacoes_daily",
    "camara_speeches_daily": "camara.speeches_daily",
    "camara_commissions_sync": "camara.commissions_sync",
}


def _hours_since_last_run(job_name: str) -> float | None:
    """Returns hours elapsed since last successful ETL run, or None if never run."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT finished_at FROM jobs.etl_runs
            WHERE job_name = :job AND status = 'success'
            ORDER BY finished_at DESC LIMIT 1
        """), {"job": job_name}).fetchone()
    if not row:
        return None
    elapsed = datetime.now(timezone.utc) - row[0].replace(tzinfo=timezone.utc)
    return elapsed.total_seconds() / 3600


def _build_etl_env() -> dict:
    """Build environment for ETL subprocesses, merging .env files explicitly."""
    env = {**os.environ, **_ETL_ENV, **_BACKEND_ENV}
    return env


def _run_stale_etl_jobs():
    """Check each ETL job; run any that haven't succeeded in >24h."""
    env = _build_etl_env()
    if not env.get("DATABASE_URL") or not ETL_DIR.exists():
        print("[ETL auto-refresh] Skipped — DATABASE_URL not set or ETL dir not found")
        return
    for job_name, module in ETL_JOBS.items():
        hours = _hours_since_last_run(job_name)
        if hours is None or hours > 24:
            age = f"{hours:.1f}h ago" if hours is not None else "never"
            print(f"[ETL auto-refresh] Running {job_name} (last success: {age})")
            try:
                subprocess.run(
                    ["python", "-m", module],
                    cwd=str(ETL_DIR),
                    env=env,
                    timeout=600,  # 10-minute timeout per job
                )
                print(f"[ETL auto-refresh] {job_name} complete")
            except subprocess.TimeoutExpired:
                print(f"[ETL auto-refresh] {job_name} timed out after 10 minutes")
            except Exception as e:
                print(f"[ETL auto-refresh] {job_name} failed: {e}")
        else:
            print(f"[ETL auto-refresh] {job_name} is fresh ({hours:.1f}h ago), skipping")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run stale ETL jobs in a background thread so startup is not blocked
    thread = threading.Thread(target=_run_stale_etl_jobs, daemon=True)
    thread.start()
    yield


app = FastAPI(
    title="Vizy API",
    description="REST API for the Vizy civic data platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(politicians.router, prefix="/politicians", tags=["politicians"])
app.include_router(bills.router, prefix="/bills", tags=["bills"])
app.include_router(votes.router, prefix="/votes", tags=["votes"])
app.include_router(donations.router, prefix="/donations", tags=["donations"])
app.include_router(feed.router, prefix="/feed", tags=["feed"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(parties.router, prefix="/parties", tags=["parties"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/admin/refresh", tags=["admin"])
def manual_refresh(background_tasks: BackgroundTasks):
    """Trigger ETL jobs immediately, regardless of last run time.
    Runs in the background — returns instantly."""
    background_tasks.add_task(_force_run_all_etl)
    return {"status": "refresh started", "jobs": list(ETL_JOBS.keys())}


def _force_run_all_etl():
    """Run all ETL jobs unconditionally (used by manual refresh)."""
    env = _build_etl_env()
    if not env.get("DATABASE_URL") or not ETL_DIR.exists():
        print("[ETL manual refresh] Skipped — DATABASE_URL not set or ETL dir not found")
        return
    for job_name, module in ETL_JOBS.items():
        print(f"[ETL manual refresh] Running {job_name}")
        try:
            subprocess.run(
                ["python", "-m", module],
                cwd=str(ETL_DIR),
                env=env,
                timeout=600,
            )
            print(f"[ETL manual refresh] {job_name} complete")
        except subprocess.TimeoutExpired:
            print(f"[ETL manual refresh] {job_name} timed out")
        except Exception as e:
            print(f"[ETL manual refresh] {job_name} failed: {e}")
