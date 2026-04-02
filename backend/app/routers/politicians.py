from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Politician

router = APIRouter()


@router.get("/")
def list_politicians(
    source: str | None = Query(None, description="'camara' or 'senado'"),
    state: str | None = Query(None),
    party: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Politician).filter(Politician.is_active == True)
    if source:
        query = query.filter(Politician.source == source)
    if state:
        query = query.filter(Politician.state == state)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "items": items}


@router.get("/{politician_id}")
def get_politician(politician_id: int, db: Session = Depends(get_db)):
    politician = db.query(Politician).filter(Politician.id == politician_id).first()
    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")
    return politician
