"""
Vizy API — FastAPI application entry point.

Scheduling strategy
-------------------
ETL and AI enrichment jobs are scheduled via APScheduler (BackgroundScheduler).
All times are in America/Sao_Paulo (BRT, UTC-3).

Fixed daily schedule:
  03:00  camara_votes_daily
  03:05  camara_bills_ingest_daily      (discovery + detail backfill, capped at 300/run)
  03:20  camara_bills_tramitacoes_daily (capped at 500/run)
  03:35  camara_speeches_daily          (timeout=1800s — 513 deputies × API rate limit)
  03:45  camara_commissions_sync
  04:00  camara_bills_enrich_daily      (AI — Claude Haiku, capped at 200/run)
  04:15  enrich_speeches                (AI — Claude Haiku, batch 300)
  04:30  enrich_legislative_events      (AI — Claude Haiku, batch 200)
  04:45  enrich_politicians             (AI — Claude Sonnet, batch 50)
  Monday 05:00  camara_politicians_weekly
  Monday 05:05  senado_politicians_weekly

Every-2h conditional triggers (run only if there is pending work):
  */2h  camara_bills_ingest_daily      — fires if any bill has status IS NULL
  */2h  camara_bills_tramitacoes_daily — fires if any active bill has no tramitações
  */2h  camara_bills_enrich_daily      — fires if any bill has short_title IS NULL or policy_area IS NULL

Mutual exclusion:
  Each of the three 2h-trigger jobs holds a threading.Lock while running.
  The lock is shared between the 2h trigger and the daily cron trigger for the
  same job, so they can never overlap.  Ingestion locks and enrichment locks are
  separate, so ingestion and enrichment can still run concurrently if needed.

Admin endpoints:
  POST /admin/refresh  — triggers data-ingestion ETL jobs only (no AI enrichment)
  POST /admin/enrich   — triggers AI enrichment jobs only
"""

import os
import subprocess
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
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
ETL_JOBS: dict[str, str] = {
    "camara_votes_daily":             "camara.votes_daily",
    "camara_bills_ingest_daily":      "camara.bills_ingest_daily",
    "camara_bills_tramitacoes_daily": "camara.bills_tramitacoes_daily",
    "camara_speeches_daily":          "camara.speeches_daily",
    "camara_commissions_sync":        "camara.commissions_sync",
}

# Weekly data-ingestion jobs
WEEKLY_ETL_JOBS: dict[str, str] = {
    "camara_politicians_weekly": "camara.politicians_weekly",
    "senado_politicians_weekly": "senado.politicians_weekly",
}

# AI enrichment ETL jobs (run as `python -m <module>` inside ETL_DIR)
AI_ETL_JOBS: dict[str, str] = {
    "camara_bills_enrich_daily": "camara.bills_enrich_daily",
}

# AI enrichment scripts (run as `python <script>` inside BACKEND_DIR)
ENRICH_JOBS: dict[str, tuple[str, list[str]]] = {
    "enrich_speeches":           ("enrich_speeches.py",           ["--limit", "300"]),
    "enrich_legislative_events": ("enrich_legislative_events.py", ["--limit", "200"]),
    "enrich_politicians":        ("enrich_politicians.py",         ["--limit", "50"]),
}

# ---------------------------------------------------------------------------
# Per-job threading locks (shared between daily cron and 2h conditional trigger)
# ---------------------------------------------------------------------------
_INGEST_LOCK   = threading.Lock()   # shared by bills_ingest_daily (cron + 2h)
_TRAMIT_LOCK   = threading.Lock()   # shared by bills_tramitacoes_daily (cron + 2h)
_ENRICH_LOCK   = threading.Lock()   # shared by bills_enrich_daily (cron + 2h)

# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _build_etl_env() -> dict:
    return {**os.environ, **_ETL_ENV, **_BACKEND_ENV}


def _write_failed_run(job_name: str, error: str) -> None:
    """Write a failed etl_runs entry from the scheduler side (e.g., on timeout/crash)."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO jobs.etl_runs
                        (job_name, started_at, finished_at, status, error_message)
                    VALUES (:job, now(), now(), 'failed', :error)
                """),
                {"job": job_name, "error": error},
            )
    except Exception as exc:
        print(f"[scheduler] _write_failed_run failed: {exc}")


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
        _write_failed_run(job_name, f"subprocess timed out after {timeout}s")
    except Exception as exc:
        print(f"[scheduler] {job_name}: error — {exc}")
        _write_failed_run(job_name, str(exc))


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
        _write_failed_run(job_name, f"subprocess timed out after {timeout}s")
    except Exception as exc:
        print(f"[scheduler] {job_name}: error — {exc}")
        _write_failed_run(job_name, str(exc))

# ---------------------------------------------------------------------------
# Conditional check helpers (used by 2h triggers)
# ---------------------------------------------------------------------------

def _has_bills_missing_detail() -> bool:
    """Return True if any camara bill has status IS NULL."""
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM core.bills WHERE source = 'camara' AND status IS NULL")
            ).scalar()
        return (count or 0) > 0
    except Exception as exc:
        print(f"[scheduler] check bills_missing_detail failed: {exc}")
        return False


def _has_bills_missing_tramitacoes() -> bool:
    """Return True if any active camara bill has no tramitações rows."""
    try:
        with engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM core.bills b
                WHERE b.source = 'camara'
                  AND NOT EXISTS (
                      SELECT 1 FROM core.legislative_events le WHERE le.bill_id = b.id
                  )
                  AND NOT (b.status IS NOT NULL AND (
                      lower(b.status) LIKE '%arquivad%' OR
                      lower(b.status) LIKE '%prejudicad%' OR
                      lower(b.status) LIKE '%encerrad%' OR
                      lower(b.status) LIKE '%retira%'
                  ))
            """)).scalar()
        return (count or 0) > 0
    except Exception as exc:
        print(f"[scheduler] check bills_missing_tramitacoes failed: {exc}")
        return False


def _has_bills_missing_enrichment() -> bool:
    """Return True if any qualifying camara bill is missing short_title or policy_area."""
    try:
        with engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM core.bills
                WHERE source = 'camara'
                  AND type IN ('PL','PLP','PEC','MPV','PDL','PRC','MSC','TVR','PLN','PDC')
                  AND ementa IS NOT NULL
                  AND (short_title IS NULL OR policy_area IS NULL)
            """)).scalar()
        return (count or 0) > 0
    except Exception as exc:
        print(f"[scheduler] check bills_missing_enrichment failed: {exc}")
        return False

# ---------------------------------------------------------------------------
# Locked job runners (used by both cron and 2h triggers)
# ---------------------------------------------------------------------------

def _run_bills_ingest(source: str = "cron"):
    """Run bills_ingest_daily under the ingest lock. Skips if already running."""
    if not _INGEST_LOCK.acquire(blocking=False):
        print(f"[scheduler] camara_bills_ingest_daily ({source}): skipped — already running")
        return
    try:
        _run_etl_module(
            "camara_bills_ingest_daily",
            ETL_JOBS["camara_bills_ingest_daily"],
            ETL_DIR,
            timeout=900,
        )
    finally:
        _INGEST_LOCK.release()


def _run_bills_tramitacoes(source: str = "cron"):
    """Run bills_tramitacoes_daily under the tramit lock. Skips if already running."""
    if not _TRAMIT_LOCK.acquire(blocking=False):
        print(f"[scheduler] camara_bills_tramitacoes_daily ({source}): skipped — already running")
        return
    try:
        _run_etl_module(
            "camara_bills_tramitacoes_daily",
            ETL_JOBS["camara_bills_tramitacoes_daily"],
            ETL_DIR,
        )
    finally:
        _TRAMIT_LOCK.release()


def _run_bills_enrich(source: str = "cron"):
    """Run bills_enrich_daily under the enrich lock. Skips if already running."""
    if not _ENRICH_LOCK.acquire(blocking=False):
        print(f"[scheduler] camara_bills_enrich_daily ({source}): skipped — already running")
        return
    try:
        _run_etl_module(
            "camara_bills_enrich_daily",
            AI_ETL_JOBS["camara_bills_enrich_daily"],
            ETL_DIR,
            timeout=1800,  # increased from 900s — enriches 200 bills via Anthropic API
        )
    finally:
        _ENRICH_LOCK.release()

# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

def _build_scheduler() -> BackgroundScheduler:
    tz = "America/Sao_Paulo"
    scheduler = BackgroundScheduler(timezone=tz)

    # ── Daily data-ingestion jobs (03:00–03:45 BRT) ──────────────────────
    scheduler.add_job(
        lambda: _run_etl_module("camara_votes_daily", ETL_JOBS["camara_votes_daily"], ETL_DIR),
        CronTrigger(hour=3, minute=0, timezone=tz),
        id="camara_votes_daily", name="Câmara votes (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_bills_ingest("cron"),
        CronTrigger(hour=3, minute=5, timezone=tz),
        id="camara_bills_ingest_daily", name="Câmara bills ingestion + detail (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_bills_tramitacoes("cron"),
        CronTrigger(hour=3, minute=20, timezone=tz),
        id="camara_bills_tramitacoes_daily", name="Câmara tramitações (daily)", replace_existing=True,
    )
    def _run_speeches_daily():
        """Run speeches_daily and emit a warning when 0 speeches are fetched on a weekday."""
        _run_etl_module("camara_speeches_daily", ETL_JOBS["camara_speeches_daily"], ETL_DIR, timeout=1800)
        # Check if today is a weekday (Mon=0 … Fri=4) in BRT and the run fetched nothing.
        # A zero-fetch on a weekday usually means the Câmara API was unavailable.
        now_brt = datetime.now(ZoneInfo("America/Sao_Paulo"))
        if now_brt.weekday() < 5:  # Mon–Fri
            try:
                with engine.connect() as conn:
                    last = conn.execute(
                        text("""
                            SELECT fetched FROM jobs.etl_runs
                            WHERE job_name = 'camara_speeches_daily'
                            ORDER BY finished_at DESC LIMIT 1
                        """)
                    ).fetchone()
                if last and (last[0] or 0) == 0:
                    print(
                        "[scheduler] camara_speeches_daily: WARNING — 0 speeches fetched on a weekday. "
                        "The Câmara /discursos API may have been unavailable."
                    )
            except Exception as exc:
                print(f"[scheduler] camara_speeches_daily: could not check fetch count: {exc}")

    scheduler.add_job(
        _run_speeches_daily,
        CronTrigger(hour=3, minute=35, timezone=tz),
        id="camara_speeches_daily", name="Câmara speeches (daily)", replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_etl_module("camara_commissions_sync", ETL_JOBS["camara_commissions_sync"], ETL_DIR),
        CronTrigger(hour=3, minute=45, timezone=tz),
        id="camara_commissions_sync", name="Câmara commissions sync (daily)", replace_existing=True,
    )

    # ── Daily AI enrichment jobs (04:00–04:45 BRT) ───────────────────────
    scheduler.add_job(
        lambda: _run_bills_enrich("cron"),
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

    # ── Every-2h conditional triggers ────────────────────────────────────
    # Each trigger checks whether there is pending work before running.
    # The same threading lock is shared with the daily cron job, so the two
    # can never overlap for the same job.
    scheduler.add_job(
        lambda: _has_bills_missing_detail() and _run_bills_ingest("2h-trigger"),
        IntervalTrigger(hours=2, timezone=tz),
        id="camara_bills_ingest_2h", name="Câmara bills detail backfill (every 2h, conditional)",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _has_bills_missing_tramitacoes() and _run_bills_tramitacoes("2h-trigger"),
        IntervalTrigger(hours=2, timezone=tz),
        id="camara_bills_tramitacoes_2h", name="Câmara tramitações backfill (every 2h, conditional)",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _has_bills_missing_enrichment() and _run_bills_enrich("2h-trigger"),
        IntervalTrigger(hours=2, timezone=tz),
        id="camara_bills_enrich_2h", name="Câmara bills AI enrichment (every 2h, conditional)",
        replace_existing=True,
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
    print("[scheduler] APScheduler started — ETL jobs scheduled (daily cron + every-2h conditional)")
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
    AI enrichment jobs are NOT triggered here — use /admin/enrich for that."""
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(_force_run_ingest_etl)
    return {"status": "refresh started", "jobs": list(ETL_JOBS.keys())}


@app.post("/admin/enrich", tags=["admin"])
def manual_enrich(background_tasks: BackgroundTasks, x_admin_key: str | None = Header(None)):
    """Trigger all AI enrichment jobs immediately.
    Separate from /admin/refresh to avoid running enrichment during ingestion."""
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(_force_run_enrich)
    ai_jobs = list(AI_ETL_JOBS.keys()) + list(ENRICH_JOBS.keys())
    return {"status": "enrichment started", "jobs": ai_jobs}


def _force_run_ingest_etl():
    """Run all data-ingestion ETL jobs sequentially. Does NOT include AI enrichment."""
    for job_name, module in ETL_JOBS.items():
        if job_name == "camara_bills_ingest_daily":
            _run_bills_ingest("admin/refresh")
        elif job_name == "camara_bills_tramitacoes_daily":
            _run_bills_tramitacoes("admin/refresh")
        else:
            _run_etl_module(job_name, module, ETL_DIR)


def _force_run_enrich():
    """Run all AI enrichment jobs sequentially."""
    _run_bills_enrich("admin/enrich")
    for job_name, (script, extra_args) in ENRICH_JOBS.items():
        _run_enrich_script(job_name, script, extra_args)
