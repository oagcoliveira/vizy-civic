from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/politician/{politician_id}")
def get_politician_donations(
    politician_id: int,
    election_year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    # Raw SQL for TSE schema tables
    sql = """
        SELECT d.name, d.donor_type, d.cpf_cnpj_masked, d.state,
               dn.amount_brl, dn.election_year, dn.receipt_date, dn.source_type
        FROM tse.donations dn
        JOIN tse.donors d ON d.id = dn.donor_id
        WHERE dn.politician_id = :politician_id
    """
    params = {"politician_id": politician_id}
    if election_year:
        sql += " AND dn.election_year = :year"
        params["year"] = election_year
    sql += " ORDER BY dn.amount_brl DESC LIMIT 200"
    result = db.execute(sql, params)
    return [dict(row) for row in result]
