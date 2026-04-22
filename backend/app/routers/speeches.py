from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db

router = APIRouter()


@router.get("/{speech_id}")
def get_speech(speech_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            s.id,
            s.delivered_at,
            s.phase,
            s.summary,
            s.keywords,
            s.full_text_url,
            p.id          AS politician_id,
            p.short_name  AS politician_short_name,
            p.name        AS politician_full_name,
            p.photo_url   AS politician_photo_url,
            pa.acronym    AS party_acronym,
            p.state
        FROM core.speeches s
        LEFT JOIN core.politicians p  ON p.id  = s.politician_id
        LEFT JOIN core.parties     pa ON pa.id = p.party_id
        WHERE s.id = :id
    """), {"id": speech_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Speech not found")

    return dict(row._mapping)
