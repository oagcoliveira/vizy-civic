from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import PoliticianFollow, User
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/")
def get_feed(
    event_type: str | None = Query(None, description="vote | speech"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns reverse-chronological feed events for politicians followed by the authenticated user.
    Each item is a union of votes and speeches.
    """
    followed = (
        db.query(PoliticianFollow.politician_id)
        .filter(PoliticianFollow.user_id == current_user.id)
        .all()
    )
    politician_ids = [f.politician_id for f in followed]
    if not politician_ids:
        return {"total": 0, "page": page, "items": []}

    # Build unified feed via raw SQL (union of event types).
    # Wrapped in a subquery so ORDER BY / LIMIT / OFFSET apply to the full union.
    # NULLS LAST ensures rows with no date don't float to the top.
    # event_type filter is applied when provided.
    type_filter = ""
    if event_type in ("vote", "speech"):
        type_filter = "WHERE event_type = :event_type"

    sql = text(f"""
        SELECT event_type, id, politician_id, occurred_at, title, detail
        FROM (
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
        ) combined
        {type_filter}
        ORDER BY occurred_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    offset = (page - 1) * page_size
    params: dict = {"pids": politician_ids, "limit": page_size, "offset": offset}
    if event_type in ("vote", "speech"):
        params["event_type"] = event_type

    rows = db.execute(sql, params).fetchall()
    return {"page": page, "items": [dict(r._mapping) for r in rows]}
