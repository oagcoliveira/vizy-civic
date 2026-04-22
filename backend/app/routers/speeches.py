from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db

router = APIRouter()

SPEECH_COLS = """
    s.id,
    s.delivered_at,
    s.phase,
    s.summary,
    s.keywords,
    s.full_text_url,
    s.transcricao,
    s.policy_tags,
    p.id          AS politician_id,
    p.short_name  AS politician_short_name,
    p.name        AS politician_full_name,
    p.photo_url   AS politician_photo_url,
    pa.acronym    AS party_acronym,
    p.state
"""

SPEECH_JOINS = """
    FROM core.speeches s
    LEFT JOIN core.politicians p  ON p.id  = s.politician_id
    LEFT JOIN core.parties     pa ON pa.id = p.party_id
"""


@router.get("/")
def list_speeches(
    politician_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List speeches with optional filtering by politician. Returns total count and paginated items."""
    where = []
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if politician_id is not None:
        where.append("s.politician_id = :politician_id")
        params["politician_id"] = politician_id

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(text(f"""
        SELECT {SPEECH_COLS}
        {SPEECH_JOINS}
        {where_clause}
        ORDER BY s.delivered_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) {SPEECH_JOINS} {where_clause}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{speech_id}")
def get_speech(speech_id: int, db: Session = Depends(get_db)):
    """Get a single speech by ID."""
    row = db.execute(text(f"""
        SELECT {SPEECH_COLS}
        {SPEECH_JOINS}
        WHERE s.id = :id
    """), {"id": speech_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Speech not found")

    return dict(row._mapping)
