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
    session_label: str | None = Query(None),
    bill_type: str | None = Query(None),
    policy_areas: str | None = Query(None, description="Comma-separated policy areas, e.g. Saúde,Educação"),
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
    if session_label == "__outros__":
        # Exclude all sessions with >= 600 votes — show only the long-tail ones
        where.append("""
            v.session_label NOT IN (
                SELECT session_label FROM core.votacoes
                WHERE session_label IS NOT NULL
                GROUP BY session_label HAVING COUNT(*) >= 600
            )
        """)
    elif session_label:
        where.append("v.session_label = :session_label")
        params["session_label"] = session_label
    if bill_type:
        where.append("b.type = :bill_type")
        params["bill_type"] = bill_type
    if policy_areas:
        _pa_list = [a.strip() for a in policy_areas.split(",") if a.strip()]
        if _pa_list:
            pa_placeholders = ", ".join(f":pa_{i}" for i in range(len(_pa_list)))
            where.append(f"b.policy_area IN ({pa_placeholders})")
            for i, a in enumerate(_pa_list):
                params[f"pa_{i}"] = a

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
        SELECT count(*) FROM core.votacoes v
        LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
        LEFT JOIN core.bills b ON b.id = vb.bill_id
        WHERE {where_clause}
    """), params).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/filter-options")
def get_filter_options(db: Session = Depends(get_db)):
    """Returns available session labels and bill types for filter dropdowns."""
    labels = db.execute(text("""
        SELECT session_label, COUNT(*) as c
        FROM core.votacoes
        WHERE session_label IS NOT NULL
        GROUP BY session_label ORDER BY c DESC
    """)).fetchall()
    bill_types = db.execute(text("""
        SELECT DISTINCT b.type
        FROM core.bills b
        JOIN core.votacao_bills vb ON vb.bill_id = b.id
        WHERE b.type IS NOT NULL
        ORDER BY b.type
    """)).fetchall()
    main = [r[0] for r in labels if r[1] >= 600]
    outros_count = sum(r[1] for r in labels if r[1] < 600)
    policy_areas_rows = db.execute(text("""
        SELECT DISTINCT b.policy_area
        FROM core.bills b
        JOIN core.votacao_bills vb ON vb.bill_id = b.id
        WHERE b.policy_area IS NOT NULL
        ORDER BY b.policy_area
    """)).fetchall()
    return {
        "session_labels": main,
        "session_labels_outros_count": outros_count,
        "bill_types": [r[0] for r in bill_types],
        "policy_areas": [r[0] for r in policy_areas_rows],
    }


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
