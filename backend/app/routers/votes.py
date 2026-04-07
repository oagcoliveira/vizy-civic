from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/")
def list_votacoes(
    source: str | None = Query(None),
    vote_type: str | None = Query(None),
    result: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    where = ["1=1"]
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if source:
        where.append("v.source = :source")
        params["source"] = source
    if vote_type:
        where.append("v.vote_type = :vote_type")
        params["vote_type"] = vote_type
    if result:
        where.append("v.result = :result")
        params["result"] = result

    where_clause = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT v.id, v.external_id, v.source, v.description, v.voted_at,
               v.vote_type, v.result, v.session_label,
               b.id AS bill_id, b.title AS bill_title, b.short_title AS bill_short_title,
               b.ementa AS bill_ementa, b.type AS bill_type, b.number AS bill_number, b.year AS bill_year
        FROM core.votacoes v
        LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
        LEFT JOIN core.bills b ON b.id = vb.bill_id
        WHERE {where_clause}
        ORDER BY v.voted_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT count(*) FROM core.votacoes v WHERE {where_clause}
    """), params).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{votacao_id}")
def get_votacao(votacao_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT v.id, v.external_id, v.source, v.description, v.voted_at,
               v.vote_type, v.result, v.session_label,
               b.id AS bill_id, b.title AS bill_title, b.short_title AS bill_short_title,
               b.ementa AS bill_ementa, b.type AS bill_type, b.number AS bill_number,
               b.year AS bill_year, b.full_text_url AS bill_url
        FROM core.votacoes v
        LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
        LEFT JOIN core.bills b ON b.id = vb.bill_id
        WHERE v.id = :id
    """), {"id": votacao_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Votação not found")

    result = dict(row._mapping)

    # All linked bills (not just primary)
    bills = db.execute(text("""
        SELECT b.id, b.title, b.short_title, b.ementa, b.type, b.number, b.year,
               b.full_text_url, vb.is_primary
        FROM core.votacao_bills vb
        JOIN core.bills b ON b.id = vb.bill_id
        WHERE vb.votacao_id = :id
        ORDER BY vb.is_primary DESC
    """), {"id": votacao_id}).fetchall()
    result["bills"] = [dict(b._mapping) for b in bills]

    return result


@router.get("/{votacao_id}/individual")
def get_individual_votes(
    votacao_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, le=600),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT iv.vote, iv.party_at_time, iv.party_orientation, iv.followed_orientation,
               p.id AS politician_id, p.short_name, p.name, p.photo_url, p.state
        FROM core.individual_votes iv
        JOIN core.politicians p ON p.id = iv.politician_id
        WHERE iv.votacao_id = :id
        ORDER BY p.short_name
        LIMIT :limit OFFSET :offset
    """), {"id": votacao_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()

    total = db.execute(
        text("SELECT count(*) FROM core.individual_votes WHERE votacao_id = :id"),
        {"id": votacao_id}
    ).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}
