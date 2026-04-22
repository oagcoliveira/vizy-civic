"""
Vizy API — FastAPI application entry point.

Scheduling strategy
-------------------
ETL and AI enrichment jobs are scheduled via APScheduler (BackgroundScheduler)
to run daily at 03:00 BRT (UTC-3 = 06:00 UTC). This replaces the old
startup-triggered approach that ran stale jobs every time the server restarted —
unsuitable now that the backend is always on in Railway.

Schedule overview (all times BRT / America/Sao_Paulo):
  03:00  camara_votes_daily
  03:05  camara_bills_daily          (includes inline AI enrichment)
  03:20  camara_bills_tramitacoes_daily
  03:35  camara_speeches_daily
  03:45  camara_commissions_sync
  04:00  enrich_speeches             (AI — Claude Haiku, batch 100)
  04:10  enrich_legislative_events   (AI — Claude Haiku, batch 200)
  04:20  enrich_politicians          (AI — Claude Sonnet, batch 50)
  Monday 04:30  camara_politicians_weekly
  Monday 04:35  senado_politicians_weekly

The /admin/refresh endpoint still allows a manual unconditional run of all
data-ingestion ETL jobs (requires X-Admin-Key header).
"""

import os
import subprocess
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import dotenv_values
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import auth, politicians, bills, votes, donations, feed, search, parties, speeches

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

_BACKEND_ENV = dotenv_values(Path(__file__).parent.parent / ".env")
_ETL_ENV = dotenv_values(Path(__file__).parent.parent.parent / "etl" / ".env")

ETL_DIR = Path(os.environ.get("ETL_DIR", str(Path(__file__).parent.parent / "etl")))
BACKEND_DIR = Path(__file__).parent.parent  # /app in container, backend/ locally

# ---------------------------------------------------------------------------
# Job registry
# ---------------------------------------------------------------------------

# Data-ingestion ETL jobs (run as `python -m <module>` inside ETL_DIR)
ETL_JOBS: dict[str, str] = {
    "camara_votes_daily":             "camara.votes_daily",
    "camara_bills_daily":             "camara.bills_daily",
    "camara_bills_tramitacoes_daily": "camara.bills_tramitacoes_daily",
    "camara_speeches_daily":          "camara.speeches_daily",
    "camara_commissions_sync":        "camara.commissions_sync",
}

# Weekly data-ingestion jobs (run as `python -m <module>` inside ETL_DIR)
WEEKLY_ETL_JOBS: dict[str, str] = {
    "camara_politicians_weekly": "camara.politicians_weekly",
    "senado_politicians_weekly": "senado.politicians_weekly",
}

# AI enrichment scripts (run as `python <script>` inside BACKEND_DIR)
ENRICH_JOBS: dict[str, tuple[str, list[str]]] = {
    # job_name: (script_filename, extra_args)
    "enrich_speeches":           ("enrich_speeches.py",           ["--limit", "100"]),
    "enrich_legislative_events": ("enrich_legislative_events.py", ["--limit", "200"]),
    "enrich_politicians":        ("enrich_politicians.py",         ["--limit", "50"]),
}

# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _build_etl_env() -> dict:
    return {**os.environ, **_ETL_ENV, **_BACKEND_ENV}


def _run_etl_module(job_name: str, module: str, cwd: Path, timeout: int = 600):
    env = _build_etl_env()
    if not env.get("DATABASE_URL") or not cwd.exists():
        print(f"[scheduler] {job_name}: skipped — DATABASE_URL not set or dir not found")
        return
    print(f"[scheduler] {job_name}: starting at {datetime.now(timezone.utc).isoformat()}")
    try:
        subprocess.run(
            ["python", "-m", module],
            cwd=str(cwd),
            env=env,
            timeout=timeout,
            check=False,
        )
        print(f"[scheduler] {job_name}: finished")
    except subprocess.TimeoutExpired:
        print(f"[scheduler] {job_name}: timed out after {timeout}s")
    except Exception as exc:
        print(f"[scheduler] {job_name}: error — {exc}")


def _run_enrich_script(job_name: str, script: str, extra_args: list[str], timeout: int = 900):
    env = _build_etl_env()
    script_path = BACKEND_DIR / script
    if not env.get("DATABASE_URL") or not script_path.exists():
        print(f"[scheduler] {job_name}: skipped — DATABASE_URL not set or script not found")
        return
    print(f"[scheduler] {job_name}: starting at {datetime.now(timezone.utc).isoformat()}")
    try:
        subprocess.run(
            ["python", str(script_path)] + extra_args,
            cwd=str(BACKEND_DIR),
            env=env,
            timeout=timeout,
            check=False,
        )
        print(f"[scheduler] {job_name}: finished")
    except subprocess.TimeoutExpired:
        print(f"[scheduler] {job_name}: timed out after {timeout}s")
    except Exception as exc:
        print(f"[scheduler] {job_name}: error — {exc}")


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

def _build_scheduler() -> BackgroundScheduler:
    """
    Build and configure the APScheduler instance.

    All cron times are in America/Sao_Paulo (BRT, UTC-3).
    Jobs are staggered by 5–15 minutes to avoid DB contention.
    """
    tz = "America/Sao_Paulo"
    scheduler = BackgroundScheduler(timezone=tz)

    # ── Daily data-ingestion jobs (03:00–03:45 BRT) ──────────────────────

    scheduler.add_job(
        lambda: _run_etl_module("camara_votes_daily", ETL_JOBS["camara_votes_daily"], ETL_DIR),
        CronTrigger(hour=3, minute=0, timezone=tz),
        id="camara_votes_daily", name="Câmara votes (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_etl_module("camara_bills_daily", ETL_JOBS["camara_bills_daily"], ETL_DIR, timeout=1200),
        CronTrigger(hour=3, minute=5, timezone=tz),
        id="camara_bills_daily", name="Câmara bills + AI enrichment (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_etl_module("camara_bills_tramitacoes_daily", ETL_JOBS["camara_bills_tramitacoes_daily"], ETL_DIR),
        CronTrigger(hour=3, minute=20, timezone=tz),
        id="camara_bills_tramitacoes_daily", name="Câmara tramitações (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_etl_module("camara_speeches_daily", ETL_JOBS["camara_speeches_daily"], ETL_DIR),
        CronTrigger(hour=3, minute=35, timezone=tz),
        id="camara_speeches_daily", name="Câmara speeches (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_etl_module("camara_commissions_sync", ETL_JOBS["camara_commissions_sync"], ETL_DIR),
        CronTrigger(hour=3, minute=45, timezone=tz),
        id="camara_commissions_sync", name="Câmara commissions sync (daily)", replace_existing=True,
    )

    # ── Daily AI enrichment jobs (04:00–04:20 BRT) ───────────────────────

    scheduler.add_job(
        lambda: _run_enrich_script("enrich_speeches", *ENRICH_JOBS["enrich_speeches"]),
        CronTrigger(hour=4, minute=0, timezone=tz),
        id="enrich_speeches", name="AI enrich speeches (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_enrich_script("enrich_legislative_events", *ENRICH_JOBS["enrich_legislative_events"]),
        CronTrigger(hour=4, minute=10, timezone=tz),
        id="enrich_legislative_events", name="AI enrich legislative events (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_enrich_script("enrich_politicians", *ENRICH_JOBS["enrich_politicians"]),
        CronTrigger(hour=4, minute=20, timezone=tz),
        id="enrich_politicians", name="AI enrich politicians (daily)", replace_existing=True,
    )

    # ── Weekly politician sync (Monday 04:30–04:35 BRT) ──────────────────

    scheduler.add_job(
        lambda: _run_etl_module("camara_politicians_weekly", WEEKLY_ETL_JOBS["camara_politicians_weekly"], ETL_DIR),
        CronTrigger(day_of_week="mon", hour=4, minute=30, timezone=tz),
        id="camara_politicians_weekly", name="Câmara politicians sync (weekly)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_etl_module("senado_politicians_weekly", WEEKLY_ETL_JOBS["senado_politicians_weekly"], ETL_DIR),
        CronTrigger(day_of_week="mon", hour=4, minute=35, timezone=tz),
        id="senado_politicians_weekly", name="Senado politicians sync (weekly)", replace_existing=True,
    )

    return scheduler


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = _build_scheduler()
    scheduler.start()
    print("[scheduler] APScheduler started — ETL jobs scheduled daily at 03:00 BRT")
    yield
    scheduler.shutdown(wait=False)
    print("[scheduler] APScheduler stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Vizy API",
    description="REST API for the Vizy civic data platform",
    version="0.1.0",
    lifespan=lifespan,
)

_allowed_origins = [
    o.strip() for o in
    os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:3002").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/auth",       tags=["auth"])
app.include_router(politicians.router, prefix="/politicians", tags=["politicians"])
app.include_router(bills.router,       prefix="/bills",       tags=["bills"])
app.include_router(votes.router,       prefix="/votes",       tags=["votes"])
app.include_router(donations.router,   prefix="/donations",   tags=["donations"])
app.include_router(feed.router,        prefix="/feed",        tags=["feed"])
app.include_router(search.router,      prefix="/search",      tags=["search"])
app.include_router(parties.router,     prefix="/parties",     tags=["parties"])
app.include_router(speeches.router,    prefix="/speeches",    tags=["speeches"])


# ---------------------------------------------------------------------------
# Health + admin endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/admin/schedule", tags=["admin"])
def list_schedule(x_admin_key: str | None = Header(None)):
    """Return the next scheduled run time for every job."""
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    from apscheduler.schedulers.background import BackgroundScheduler
    # Retrieve the running scheduler via the lifespan-attached reference
    # (APScheduler stores jobs in its own registry; we re-read them here)
    jobs = []
    for job in app.state.scheduler.get_jobs() if hasattr(app.state, "scheduler") else []:
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    return {"jobs": jobs}


@app.post("/admin/refresh", tags=["admin"])
def manual_refresh(background_tasks: BackgroundTasks, x_admin_key: str | None = Header(None)):
    """Trigger all data-ingestion ETL jobs immediately (ignores last-run time).
    AI enrichment jobs are NOT triggered here — run them manually if needed.
    Requires X-Admin-Key header matching ADMIN_API_KEY env var."""
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(_force_run_all_etl)
    return {"status": "refresh started", "jobs": list(ETL_JOBS.keys())}


def _force_run_all_etl():
    """Run all data-ingestion ETL jobs unconditionally in a background thread."""
    for job_name, module in ETL_JOBS.items():
        _run_etl_module(job_name, module, ETL_DIR)
