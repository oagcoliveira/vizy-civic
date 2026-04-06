from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Politician

router = APIRouter()

POLITICIAN_COLS = """
    p.id, p.short_name, p.name, p.state, p.current_office,
    p.photo_url, p.gender, p.ai_bio, p.email, p.website_url,
    pa.acronym AS party
"""


@router.get("/")
def list_politicians(
    source: str | None = Query(None, description="'camara' or 'senado'"),
    state: str | None = Query(None),
    party: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    where = ["p.is_active = TRUE"]
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if source:
        where.append("p.source = :source")
        params["source"] = source
    if state:
        where.append("p.state = :state")
        params["state"] = state
    if party:
        where.append("pa.acronym = :party")
        params["party"] = party
    if search:
        where.append("p.short_name ILIKE :search")
        params["search"] = f"%{search}%"

    where_clause = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT {POLITICIAN_COLS}
        FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE {where_clause}
        ORDER BY p.short_name
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT count(*) FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE {where_clause}
    """), params).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{politician_id}")
def get_politician(politician_id: int, db: Session = Depends(get_db)):
    row = db.execute(text(f"""
        SELECT {POLITICIAN_COLS}
        FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE p.id = :id
    """), {"id": politician_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Politician not found")
    return dict(row._mapping)
