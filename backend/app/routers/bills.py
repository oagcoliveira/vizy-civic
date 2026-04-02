from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Bill

router = APIRouter()


@router.get("/")
def list_bills(
    source: str | None = Query(None),
    status: str | None = Query(None),
    policy_area: str | None = Query(None),
    year: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Bill)
    if source:
        query = query.filter(Bill.source == source)
    if status:
        query = query.filter(Bill.status == status)
    if policy_area:
        query = query.filter(Bill.policy_area == policy_area)
    if year:
        query = query.filter(Bill.year == year)
    total = query.count()
    items = query.order_by(Bill.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "items": items}


@router.get("/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill
