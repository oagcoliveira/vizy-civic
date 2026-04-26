import os
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import BillTrack, User
from app.routers.auth import get_current_user

# Admin e-mail — only this user may trigger per-bill enrichment
ADMIN_EMAIL = "oagcoliveira@gmail.com"

# Paths resolved relative to this file so they work both locally and in Railway
_BACKEND_DIR = Path(__file__).parent.parent.parent          # backend/
_ETL_DIR     = _BACKEND_DIR.parent / "etl"                  # etl/

# One lock per bill to prevent concurrent enrichment of the same bill
_enrich_locks: dict[int, threading.Lock] = {}
_enrich_locks_mutex = threading.Lock()

router = APIRouter()


@router.get("/")
def list_bills(
    source: str | None = Query(None),
    type: str | None = Query(None),
    types: str | None = Query(None, description="Comma-separated list of bill types, e.g. PL,PEC,MPV"),
    status: str | None = Query(None),
    policy_area: str | None = Query(None),
    policy_areas: str | None = Query(None, description="Comma-separated policy areas, e.g. Saúde,Educação"),
    year: int | None = Query(None),
    search: str | None = Query(None),
    author_politician_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    where = ["1=1"]
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if source:
        where.append("source = :source")
        params["source"] = source
    # Support both ?type=PL (single, legacy) and ?types=PL,PEC,MPV (multi-select)
    _type_list = [t.strip() for t in types.split(",") if t.strip()] if types else ([type] if type else [])
    if _type_list:
        placeholders = ", ".join(f":type_{i}" for i in range(len(_type_list)))
        where.append(f"type IN ({placeholders})")
        for i, t in enumerate(_type_list):
            params[f"type_{i}"] = t
    if status:
        where.append("status = :status")
        params["status"] = status
    # Support both ?policy_area=X (single, legacy) and ?policy_areas=X,Y (multi-select)
    _pa_list = [a.strip() for a in policy_areas.split(",") if a.strip()] if policy_areas else ([policy_area] if policy_area else [])
    if _pa_list:
        pa_placeholders = ", ".join(f":pa_{i}" for i in range(len(_pa_list)))
        where.append(f"policy_area IN ({pa_placeholders})")
        for i, a in enumerate(_pa_list):
            params[f"pa_{i}"] = a
    if year:
        where.append("year = :year")
        params["year"] = year
    if search:
        where.append("(title ILIKE :search OR ementa ILIKE :search)")
        params["search"] = f"%{search}%"
    if author_politician_id:
        where.append("author_politician_id = :author_politician_id")
        params["author_politician_id"] = author_politician_id

    where_clause = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT id, source, external_id, type, number, year, title, ementa,
               short_title, summary, status, policy_area, policy_tags,
               author_label, full_text_url, presented_at, updated_at
        FROM core.bills
        WHERE {where_clause}
        ORDER BY presented_at DESC NULLS LAST, year DESC NULLS LAST, number DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT count(*) FROM core.bills WHERE {where_clause}
    """), params).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/policy-areas")
def get_policy_areas(db: Session = Depends(get_db)):
    """Returns all distinct policy_area values in the bills table."""
    rows = db.execute(text("""
        SELECT DISTINCT policy_area
        FROM core.bills
        WHERE policy_area IS NOT NULL
        ORDER BY policy_area
    """)).fetchall()
    return {"policy_areas": [r[0] for r in rows]}


@router.get("/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT b.id, b.source, b.external_id, b.type, b.number, b.year,
               b.title, b.ementa, b.short_title, b.summary, b.status,
               b.policy_area, b.policy_tags, b.is_controversial,
               b.author_label, b.full_text_url, b.updated_at,
               p.id AS author_politician_id, p.short_name AS author_name,
               p.photo_url AS author_photo, p.state AS author_state,
               pa.acronym AS author_party,
               -- Completeness signals used by the frontend Enrich button
               (b.status IS NULL) AS missing_detail,
               (b.short_title IS NULL OR b.policy_area IS NULL) AS missing_ai,
               NOT EXISTS (
                   SELECT 1 FROM core.legislative_events le WHERE le.bill_id = b.id
               ) AS missing_tramitacoes,
               EXISTS (
                   SELECT 1 FROM core.legislative_events le
                   WHERE le.bill_id = b.id
                     AND le.summary IS NULL
                     AND (le.stage IS NOT NULL OR le.description IS NOT NULL)
               ) AS missing_event_summaries
        FROM core.bills b
        LEFT JOIN core.politicians p ON p.id = b.author_politician_id
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE b.id = :id
    """), {"id": bill_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Bill not found")

    data = dict(row._mapping)

    # Derive a single boolean the frontend can use to decide whether to show the Enrich button
    ENRICH_TYPES = ("PL", "PLP", "PEC", "MPV", "PDL", "PRC", "MSC", "TVR", "PLN", "PDC")
    data["needs_enrichment"] = (
        data["source"] == "camara"
        and (
            data["missing_detail"]
            or data["missing_tramitacoes"]
            or (data["type"] in ENRICH_TYPES and data["ementa"] and data["missing_ai"])
            or data["missing_event_summaries"]
        )
    )

    return data


@router.get("/{bill_id}/votacoes")
def get_bill_votacoes(
    bill_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT v.id, v.external_id, v.description, v.voted_at, v.result,
               v.vote_type, vb.is_primary
        FROM core.votacao_bills vb
        JOIN core.votacoes v ON v.id = vb.votacao_id
        WHERE vb.bill_id = :bid
        ORDER BY v.voted_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {"bid": bill_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()

    total = db.execute(
        text("SELECT count(*) FROM core.votacao_bills WHERE bill_id = :bid"),
        {"bid": bill_id}
    ).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{bill_id}/events")
def get_bill_events(bill_id: int, db: Session = Depends(get_db)):
    """Returns legislative events (tramitações) for a bill, oldest first."""
    rows = db.execute(text("""
        SELECT id, sequence, event_date, stage, description, summary, venue
        FROM core.legislative_events
        WHERE bill_id = :bid
        ORDER BY sequence ASC
    """), {"bid": bill_id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/{bill_id}/track")
def get_track_status(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check whether the authenticated user is tracking this bill."""
    track = db.query(BillTrack).filter_by(user_id=current_user.id, bill_id=bill_id).first()
    return {"tracking": track is not None}


@router.post("/{bill_id}/track", status_code=status.HTTP_201_CREATED)
def track_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track a bill. Idempotent — no error if already tracking."""
    existing = db.query(BillTrack).filter_by(user_id=current_user.id, bill_id=bill_id).first()
    if not existing:
        db.add(BillTrack(user_id=current_user.id, bill_id=bill_id))
        db.commit()
    return {"tracking": True}


@router.delete("/{bill_id}/track", status_code=status.HTTP_200_OK)
def untrack_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Untrack a bill. Idempotent — no error if not tracking."""
    existing = db.query(BillTrack).filter_by(user_id=current_user.id, bill_id=bill_id).first()
    if existing:
        db.delete(existing)
        db.commit()
    return {"tracking": False}


# ---------------------------------------------------------------------------
# Per-bill enrichment
# ---------------------------------------------------------------------------

def _get_bill_lock(bill_id: int) -> threading.Lock:
    """Return (creating if needed) a per-bill threading lock."""
    with _enrich_locks_mutex:
        if bill_id not in _enrich_locks:
            _enrich_locks[bill_id] = threading.Lock()
        return _enrich_locks[bill_id]


def _run_bill_enrichment(bill_id: int) -> None:
    """Background task: run the full enrichment pipeline for one bill."""
    lock = _get_bill_lock(bill_id)
    if not lock.acquire(blocking=False):
        print(f"[enrich_bill] bill_id={bill_id}: already running — skipped", flush=True)
        return
    try:
        from dotenv import dotenv_values
        env = {
            **os.environ,
            **dotenv_values(_ETL_DIR / ".env"),
            **dotenv_values(_BACKEND_DIR / ".env"),
        }
        if not env.get("DATABASE_URL"):
            print(f"[enrich_bill] bill_id={bill_id}: DATABASE_URL not set — aborting", flush=True)
            return
        if not _ETL_DIR.exists():
            print(f"[enrich_bill] bill_id={bill_id}: ETL_DIR not found at {_ETL_DIR} — aborting", flush=True)
            return

        print(f"[enrich_bill] bill_id={bill_id}: starting subprocess", flush=True)
        subprocess.run(
            ["python", "-m", "camara.bill_enrich_single", "--bill-id", str(bill_id)],
            cwd=str(_ETL_DIR),
            env=env,
            timeout=300,   # 5 min is more than enough for a single bill
            check=False,
        )
        print(f"[enrich_bill] bill_id={bill_id}: subprocess finished", flush=True)
    except subprocess.TimeoutExpired:
        print(f"[enrich_bill] bill_id={bill_id}: timed out after 300s", flush=True)
    except Exception as exc:
        print(f"[enrich_bill] bill_id={bill_id}: error — {exc}", flush=True)
    finally:
        lock.release()


@router.post("/{bill_id}/enrich", status_code=status.HTTP_202_ACCEPTED)
def enrich_bill(
    bill_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger the full enrichment pipeline for a single Câmara bill.

    Runs sequentially in the background:
      1. Detail ingest  — status, author, full_text_url  (Câmara API)
      2. Tramitações    — legislative events              (Câmara API)
      3. AI bill        — short_title, summary, policy_area (Claude Haiku)
      4. AI events      — plain-language event summaries  (Claude Haiku)

    Access is restricted to the admin user.
    Returns 409 if the bill is already fully enriched.
    """
    if current_user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Verify the bill exists and is a Câmara bill
    row = db.execute(text("""
        SELECT id, source, status, short_title, policy_area, ementa, type,
               EXISTS (
                   SELECT 1 FROM core.legislative_events WHERE bill_id = core.bills.id
               ) AS has_events
        FROM core.bills
        WHERE id = :id
    """), {"id": bill_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Bill not found")

    if row.source != "camara":
        raise HTTPException(
            status_code=422,
            detail=f"Only 'camara' bills are supported for per-bill enrichment (this bill has source='{row.source}').",
        )

    # Determine whether there is actually anything to do
    ENRICH_TYPES = ("PL", "PLP", "PEC", "MPV", "PDL", "PRC", "MSC", "TVR", "PLN", "PDC")
    needs_detail   = row.status is None
    needs_tramit   = not row.has_events
    needs_ai_bill  = (
        row.type in ENRICH_TYPES
        and row.ementa is not None
        and (row.short_title is None or row.policy_area is None)
    )
    needs_ai_events = db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM core.legislative_events
            WHERE bill_id = :id AND summary IS NULL
              AND (stage IS NOT NULL OR description IS NOT NULL)
        )
    """), {"id": bill_id}).scalar()

    if not any([needs_detail, needs_tramit, needs_ai_bill, needs_ai_events]):
        raise HTTPException(
            status_code=409,
            detail="Bill is already fully enriched — nothing to do.",
        )

    background_tasks.add_task(_run_bill_enrichment, bill_id)

    return {
        "status": "enrichment_started",
        "bill_id": bill_id,
        "pending": {
            "detail": needs_detail,
            "tramitacoes": needs_tramit,
            "ai_bill": needs_ai_bill,
            "ai_events": needs_ai_events,
        },
    }
