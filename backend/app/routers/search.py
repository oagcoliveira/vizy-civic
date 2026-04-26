from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/")
def search(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    """Full-text search over politicians, bills, and speeches."""
    results = {"politicians": [], "bills": [], "speeches": []}

    politicians = db.execute(
        text("""
            SELECT p.id, p.short_name, p.name, p.state, p.current_office,
                   p.photo_url, pa.acronym AS party_acronym
            FROM core.politicians p
            LEFT JOIN core.parties pa ON pa.id = p.party_id
            WHERE p.fts @@ plainto_tsquery('portuguese', :q)
               OR p.name ILIKE :like
               OR p.short_name ILIKE :like
            LIMIT 10
        """),
        {"q": q, "like": f"%{q}%"},
    ).fetchall()
    results["politicians"] = [dict(r._mapping) for r in politicians]

    bills = db.execute(
        text("""
            SELECT id, type, number, year, short_title, ementa, status, policy_area
            FROM core.bills
            WHERE fts @@ plainto_tsquery('portuguese', :q)
               OR ementa ILIKE :like
               OR short_title ILIKE :like
        """),
        {"q": q, "like": f"%{q}%"},
    ).fetchall()
    results["bills"] = [dict(r._mapping) for r in bills]

    speeches = db.execute(
        text("""
            SELECT s.id, s.politician_id, p.short_name AS politician_name,
                   s.delivered_at, s.summary
            FROM core.speeches s
            LEFT JOIN core.politicians p ON p.id = s.politician_id
            WHERE s.fts @@ plainto_tsquery('portuguese', :q)
            LIMIT 10
        """),
        {"q": q},
    ).fetchall()
    results["speeches"] = [dict(r._mapping) for r in speeches]

    return results
