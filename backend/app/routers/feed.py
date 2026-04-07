from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import PoliticianFollow

router = APIRouter()


@router.get("/")
def get_feed(
    user_id: int = Query(...),
    event_type: str | None = Query(None, description="vote | speech | bill"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    """
    Returns reverse-chronological feed events for politicians followed by the user.
    Each item is a union of votes, speeches, and bill events.
    """
    followed = (
        db.query(PoliticianFollow.politician_id)
        .filter(PoliticianFollow.user_id == user_id)
        .all()
    )
    politician_ids = [f.politician_id for f in followed]
    if not politician_ids:
        return {"total": 0, "page": page, "items": []}

    # Build unified feed via raw SQL (union of event types)
    sql = text("""
        SELECT 'vote' AS event_type, iv.id, iv.politician_id,
               v.voted_at AS occurred_at, b.short_title AS title, iv.vote AS detail
        FROM core.individual_votes iv
        JOIN core.votacoes v ON v.id = iv.votacao_id
        LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
        LEFT JOIN core.bills b ON b.id = vb.bill_id
        WHERE iv.politician_id = ANY(:pids)

        UNION ALL

        SELECT 'speech' AS event_type, s.id, s.politician_id,
               s.delivered_at AS occurred_at, s.summary AS title, s.phase AS detail
        FROM core.speeches s
        WHERE s.politician_id = ANY(:pids)

        ORDER BY occurred_at DESC
        LIMIT :limit OFFSET :offset
    """)
    offset = (page - 1) * page_size
    rows = db.execute(sql, {"pids": politician_ids, "limit": page_size, "offset": offset}).fetchall()
    return {"page": page, "items": [dict(r._mapping) for r in rows]}
