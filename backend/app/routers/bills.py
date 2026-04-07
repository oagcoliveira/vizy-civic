from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/")
def list_bills(
    source: str | None = Query(None),
    status: str | None = Query(None),
    policy_area: str | None = Query(None),
    year: int | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    where = ["1=1"]
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if source:
        where.append("source = :source")
        params["source"] = source
    if status:
        where.append("status = :status")
        params["status"] = status
    if policy_area:
        where.append("policy_area = :policy_area")
        params["policy_area"] = policy_area
    if year:
        where.append("year = :year")
        params["year"] = year
    if search:
        where.append("(title ILIKE :search OR ementa ILIKE :search)")
        params["search"] = f"%{search}%"

    where_clause = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT id, source, external_id, type, number, year, title, ementa,
               short_title, summary, status, policy_area, policy_tags,
               author_label, full_text_url, updated_at
        FROM core.bills
        WHERE {where_clause}
        ORDER BY updated_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT count(*) FROM core.bills WHERE {where_clause}
    """), params).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT b.id, b.source, b.external_id, b.type, b.number, b.year,
               b.title, b.ementa, b.short_title, b.summary, b.status,
               b.policy_area, b.policy_tags, b.is_controversial,
               b.author_label, b.full_text_url, b.updated_at,
               p.id AS author_politician_id, p.short_name AS author_name,
               p.photo_url AS author_photo, p.state AS author_state,
               pa.acronym AS author_party
        FROM core.bills b
        LEFT JOIN core.politicians p ON p.id = b.author_politician_id
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE b.id = :id
    """), {"id": bill_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Bill not found")

    return dict(row._mapping)


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
