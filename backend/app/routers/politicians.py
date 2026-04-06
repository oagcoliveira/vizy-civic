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


@router.get("/{politician_id}/stats")
def get_politician_stats(politician_id: int, db: Session = Depends(get_db)):
    votes = db.execute(
        text("SELECT count(*) FROM core.individual_votes WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    speeches = db.execute(
        text("SELECT count(*) FROM core.speeches WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    bills = db.execute(
        text("SELECT count(*) FROM core.bills WHERE author_politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    return {"votes": votes, "speeches": speeches, "bills": bills}


@router.get("/{politician_id}/votes")
def get_politician_votes(
    politician_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT iv.vote, iv.party_at_time, iv.party_orientation, iv.followed_orientation,
               v.voted_at, v.result, v.description,
               b.short_title, b.type, b.number, b.year
        FROM core.individual_votes iv
        JOIN core.votacoes v ON v.id = iv.votacao_id
        LEFT JOIN core.bills b ON b.id = v.bill_id
        WHERE iv.politician_id = :id
        ORDER BY v.voted_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {"id": politician_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
    total = db.execute(
        text("SELECT count(*) FROM core.individual_votes WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{politician_id}/speeches")
def get_politician_speeches(
    politician_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT id, delivered_at, phase, summary, keywords, full_text_url
        FROM core.speeches
        WHERE politician_id = :id
        ORDER BY delivered_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {"id": politician_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
    total = db.execute(
        text("SELECT count(*) FROM core.speeches WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}
