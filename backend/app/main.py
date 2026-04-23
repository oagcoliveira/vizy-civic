"""
Vizy API — FastAPI application entry point.

Scheduling strategy
-------------------
ETL and AI enrichment jobs are scheduled via APScheduler (BackgroundScheduler)
to run daily at 03:00 BRT (UTC-3 = 06:00 UTC).

Schedule overview (all times BRT / America/Sao_Paulo):
  03:00  camara_votes_daily
  03:05  camara_bills_ingest_daily      (discovery + detail backfill, capped at 300/run)
  03:20  camara_bills_tramitacoes_daily (capped at 500/run)
  03:35  camara_speeches_daily
  03:45  camara_commissions_sync
  04:00  camara_bills_enrich_daily      (AI — Claude Haiku, capped at 200/run)
  04:15  enrich_speeches                (AI — Claude Haiku, batch 300)
  04:30  enrich_legislative_events      (AI — Claude Haiku, batch 200)
  04:45  enrich_politicians             (AI — Claude Sonnet, batch 50)
  Monday 05:00  camara_politicians_weekly
  Monday 05:05  senado_politicians_weekly

Admin endpoints:
  POST /admin/refresh  — triggers data-ingestion ETL jobs only (no AI enrichment)
  POST /admin/enrich   — triggers AI enrichment jobs only
"""

import os
import subprocess
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
from app.routers import auth, politicians, bills, votes, donations, feed, search, parties, speeches, digests

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
# These jobs do NOT perform AI enrichment — they only fetch and store raw data.
ETL_JOBS: dict[str, str] = {
    "camara_votes_daily":             "camara.votes_daily",
    "camara_bills_ingest_daily":      "camara.bills_ingest_daily",
    "camara_bills_tramitacoes_daily": "camara.bills_tramitacoes_daily",
    "camara_speeches_daily":          "camara.speeches_daily",
    "camara_commissions_sync":        "camara.commissions_sync",
}

# Weekly data-ingestion jobs (run as `python -m <module>` inside ETL_DIR)
WEEKLY_ETL_JOBS: dict[str, str] = {
    "camara_politicians_weekly": "camara.politicians_weekly",
    "senado_politicians_weekly": "senado.politicians_weekly",
}

# AI enrichment ETL jobs (run as `python -m <module>` inside ETL_DIR)
# Kept separate from ETL_JOBS so /admin/refresh never triggers AI enrichment.
AI_ETL_JOBS: dict[str, str] = {
    "camara_bills_enrich_daily": "camara.bills_enrich_daily",
}

# AI enrichment scripts (run as `python <script>` inside BACKEND_DIR)
ENRICH_JOBS: dict[str, tuple[str, list[str]]] = {
    # job_name: (script_filename, extra_args)
    "enrich_speeches":           ("enrich_speeches.py",           ["--limit", "300"]),
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
    Ingestion jobs run 03:00–03:45; AI enrichment jobs run 04:00–04:45.
    This ensures all ingestion is complete before any AI enrichment starts,
    preventing overlap and DB contention.
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
        # timeout=900: discovery + up to 300 detail fetches; should finish in ~10 min normally
        lambda: _run_etl_module("camara_bills_ingest_daily", ETL_JOBS["camara_bills_ingest_daily"], ETL_DIR, timeout=900),
        CronTrigger(hour=3, minute=5, timezone=tz),
        id="camara_bills_ingest_daily", name="Câmara bills ingestion + detail (daily)", replace_existing=True,
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

    # ── Daily AI enrichment jobs (04:00–04:45 BRT) ───────────────────────
    # All AI jobs fire after 04:00 to ensure ingestion jobs have completed.

    scheduler.add_job(
        # Bills AI enrichment: short_title, summary, policy_area (capped at 200/run)
        lambda: _run_etl_module("camara_bills_enrich_daily", AI_ETL_JOBS["camara_bills_enrich_daily"], ETL_DIR, timeout=900),
        CronTrigger(hour=4, minute=0, timezone=tz),
        id="camara_bills_enrich_daily", name="Câmara bills AI enrichment (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_enrich_script("enrich_speeches", *ENRICH_JOBS["enrich_speeches"]),
        CronTrigger(hour=4, minute=15, timezone=tz),
        id="enrich_speeches", name="AI enrich speeches (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_enrich_script("enrich_legislative_events", *ENRICH_JOBS["enrich_legislative_events"]),
        CronTrigger(hour=4, minute=30, timezone=tz),
        id="enrich_legislative_events", name="AI enrich legislative events (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_enrich_script("enrich_politicians", *ENRICH_JOBS["enrich_politicians"]),
        CronTrigger(hour=4, minute=45, timezone=tz),
        id="enrich_politicians", name="AI enrich politicians (daily)", replace_existing=True,
    )

    # ── Weekly politician sync (Monday 05:00–05:05 BRT) ──────────────────

    scheduler.add_job(
        lambda: _run_etl_module("camara_politicians_weekly", WEEKLY_ETL_JOBS["camara_politicians_weekly"], ETL_DIR),
        CronTrigger(day_of_week="mon", hour=5, minute=0, timezone=tz),
        id="camara_politicians_weekly", name="Câmara politicians sync (weekly)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_etl_module("senado_politicians_weekly", WEEKLY_ETL_JOBS["senado_politicians_weekly"], ETL_DIR),
        CronTrigger(day_of_week="mon", hour=5, minute=5, timezone=tz),
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
app.include_router(digests.router,     prefix="/digests",     tags=["digests"])


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
    AI enrichment jobs are NOT triggered here — use /admin/enrich for that.
    Requires X-Admin-Key header matching ADMIN_API_KEY env var."""
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(_force_run_ingest_etl)
    return {"status": "refresh started", "jobs": list(ETL_JOBS.keys())}


@app.post("/admin/enrich", tags=["admin"])
def manual_enrich(background_tasks: BackgroundTasks, x_admin_key: str | None = Header(None)):
    """Trigger all AI enrichment jobs immediately.
    Separate from /admin/refresh to avoid running enrichment during ingestion.
    Requires X-Admin-Key header matching ADMIN_API_KEY env var."""
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(_force_run_enrich)
    ai_jobs = list(AI_ETL_JOBS.keys()) + list(ENRICH_JOBS.keys())
    return {"status": "enrichment started", "jobs": ai_jobs}


def _force_run_ingest_etl():
    """Run all data-ingestion ETL jobs sequentially. Does NOT include AI enrichment."""
    for job_name, module in ETL_JOBS.items():
        _run_etl_module(job_name, module, ETL_DIR)


def _force_run_enrich():
    """Run all AI enrichment jobs sequentially."""
    for job_name, module in AI_ETL_JOBS.items():
        _run_etl_module(job_name, module, ETL_DIR)
    for job_name, (script, extra_args) in ENRICH_JOBS.items():
        _run_enrich_script(job_name, script, extra_args)
