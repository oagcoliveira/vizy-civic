from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Votacao, IndividualVote

router = APIRouter()


@router.get("/")
def list_votacoes(
    source: str | None = Query(None),
    result: str | None = Query(None),
    bill_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Votacao)
    if source:
        query = query.filter(Votacao.source == source)
    if result:
        query = query.filter(Votacao.result == result)
    if bill_id:
        query = query.filter(Votacao.bill_id == bill_id)
    total = query.count()
    items = query.order_by(Votacao.voted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "items": items}


@router.get("/{votacao_id}/individual")
def get_individual_votes(votacao_id: int, db: Session = Depends(get_db)):
    votes = db.query(IndividualVote).filter(IndividualVote.votacao_id == votacao_id).all()
    return votes


@router.get("/politician/{politician_id}")
def get_politician_votes(
    politician_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(IndividualVote).filter(IndividualVote.politician_id == politician_id)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "items": items}
