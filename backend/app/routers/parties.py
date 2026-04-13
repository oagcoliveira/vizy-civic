from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/")
def list_parties(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT p.id, p.acronym, p.name, p.ideology, p.website_url,
               COUNT(pol.id) AS deputy_count
        FROM core.parties p
        LEFT JOIN core.politicians pol
               ON pol.party_id = p.id AND pol.is_active = TRUE
        GROUP BY p.id
        ORDER BY p.acronym
    """)).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/{party_id}")
def get_party(party_id: int, db: Session = Depends(get_db)):
    party = db.execute(text("""
        SELECT id, acronym, name, ideology, website_url, description
        FROM core.parties WHERE id = :id
    """), {"id": party_id}).fetchone()
    if not party:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Party not found")

    members = db.execute(text("""
        SELECT pol.id, pol.short_name, pol.name, pol.state, pol.photo_url,
               pol.current_office
        FROM core.politicians pol
        WHERE pol.party_id = :pid AND pol.is_active = TRUE
        ORDER BY pol.short_name
    """), {"pid": party_id}).fetchall()

    return {
        **dict(party._mapping),
        "members": [dict(r._mapping) for r in members],
    }
