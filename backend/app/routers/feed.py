from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import BillTrack, PoliticianFollow, User
from app.routers.auth import get_current_user

router = APIRouter()


@router.get("/")
def get_feed(
    event_type: str | None = Query(None, description="vote | speech | bill_vote"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns reverse-chronological feed events for the authenticated user.

    Sources:
      - vote       — a politician the user follows cast a vote
      - speech     — a politician the user follows delivered a speech
      - bill_vote  — a votação was held on a bill the user is tracking

    All three branches are merged into a single chronological stream.
    The feed is still returned even if the user only follows politicians or
    only tracks bills (whichever subset has data is shown).
    """
    followed = (
        db.query(PoliticianFollow.politician_id)
        .filter(PoliticianFollow.user_id == current_user.id)
        .all()
    )
    politician_ids = [f.politician_id for f in followed]

    tracked = (
        db.query(BillTrack.bill_id)
        .filter(BillTrack.user_id == current_user.id)
        .all()
    )
    bill_ids = [t.bill_id for t in tracked]

    if not politician_ids and not bill_ids:
        return {"total": 0, "page": page, "items": []}

    # ---------------------------------------------------------------------------
    # Build the unified feed via raw SQL.
    #
    # All three branches share the same output columns:
    #   event_type  — 'vote' | 'speech' | 'bill_vote'
    #   id          — the primary key of the event row (individual_vote, speech, votacao)
    #   politician_id — NULL for bill_vote events
    #   bill_id     — NULL for vote/speech events; the tracked bill id for bill_vote
    #   votacao_id  — the votacao id (for linking); NULL for speech events
    #   occurred_at — timestamp used for ordering
    #   title       — human-readable headline
    #   detail      — secondary label (vote value, speech phase, or votacao result)
    # ---------------------------------------------------------------------------

    # Branches that require politician follows
    politician_branches = ""
    if politician_ids:
        politician_branches = """
            SELECT 'vote'   AS event_type,
                   iv.id,
                   iv.politician_id,
                   NULL::int                                    AS bill_id,
                   iv.votacao_id,
                   v.voted_at                                   AS occurred_at,
                   COALESCE(b.short_title, b.ementa, v.description) AS title,
                   iv.vote                                      AS detail
            FROM core.individual_votes iv
            JOIN core.votacoes v ON v.id = iv.votacao_id
            LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
            LEFT JOIN core.bills b ON b.id = vb.bill_id
            WHERE iv.politician_id = ANY(:pids)

            UNION ALL

            SELECT 'speech' AS event_type,
                   s.id,
                   s.politician_id,
                   NULL::int  AS bill_id,
                   NULL::int  AS votacao_id,
                   s.delivered_at AS occurred_at,
                   s.summary      AS title,
                   s.phase        AS detail
            FROM core.speeches s
            WHERE s.politician_id = ANY(:pids)
        """

    # Branch that requires tracked bills
    bill_branch = ""
    if bill_ids:
        bill_branch = """
            SELECT 'bill_vote' AS event_type,
                   v.id,
                   NULL::int   AS politician_id,
                   b.id        AS bill_id,
                   v.id        AS votacao_id,
                   v.voted_at  AS occurred_at,
                   COALESCE(b.short_title, b.ementa, v.description) AS title,
                   v.result    AS detail
            FROM core.votacao_bills vb
            JOIN core.bills b   ON b.id  = vb.bill_id
            JOIN core.votacoes v ON v.id = vb.votacao_id
            WHERE b.id = ANY(:bids)
        """

    # Combine whichever branches are active
    if politician_branches and bill_branch:
        inner = f"{politician_branches}\n            UNION ALL\n            {bill_branch}"
    elif politician_branches:
        inner = politician_branches
    else:
        inner = bill_branch

    # Optional event_type filter applied to the outer query
    type_filter = ""
    if event_type in ("vote", "speech", "bill_vote"):
        type_filter = "WHERE event_type = :event_type"

    sql = text(f"""
        SELECT event_type, id, politician_id, bill_id, votacao_id,
               occurred_at, title, detail
        FROM (
            {inner}
        ) combined
        {type_filter}
        ORDER BY occurred_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    offset = (page - 1) * page_size
    params: dict = {
        "limit": page_size,
        "offset": offset,
    }
    if politician_ids:
        params["pids"] = politician_ids
    if bill_ids:
        params["bids"] = bill_ids
    if event_type in ("vote", "speech", "bill_vote"):
        params["event_type"] = event_type

    rows = db.execute(sql, params).fetchall()
    return {"page": page, "items": [dict(r._mapping) for r in rows]}
