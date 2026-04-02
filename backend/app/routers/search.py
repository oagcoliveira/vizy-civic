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
            SELECT id, name, short_name, state, current_office, photo_url
            FROM core.politicians
            WHERE to_tsvector('portuguese', name) @@ plainto_tsquery('portuguese', :q)
               OR name ILIKE :like
            LIMIT 10
        """),
        {"q": q, "like": f"%{q}%"},
    ).fetchall()
    results["politicians"] = [dict(r._mapping) for r in politicians]

    bills = db.execute(
        text("""
            SELECT id, type, number, year, short_title, status, policy_area
            FROM core.bills
            WHERE to_tsvector('portuguese', coalesce(short_title, title)) @@ plainto_tsquery('portuguese', :q)
            LIMIT 10
        """),
        {"q": q},
    ).fetchall()
    results["bills"] = [dict(r._mapping) for r in bills]

    speeches = db.execute(
        text("""
            SELECT s.id, s.politician_id, p.short_name AS politician_name,
                   s.delivered_at, s.summary
            FROM core.speeches s
            JOIN core.politicians p ON p.id = s.politician_id
            WHERE to_tsvector('portuguese', coalesce(s.summary, '')) @@ plainto_tsquery('portuguese', :q)
            LIMIT 10
        """),
        {"q": q},
    ).fetchall()
    results["speeches"] = [dict(r._mapping) for r in speeches]

    return results
