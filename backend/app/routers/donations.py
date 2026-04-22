from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


def _build_filters(year, party_id, state,
                   source_type=None, politician_id=None, donor_type=None,
                   table_alias="d"):
    """Return (where_clauses, params) for common donation filters."""
    where = [f"{table_alias}.politician_id IS NOT NULL"]
    params: dict = {}
    if year:
        where.append(f"{table_alias}.election_year = :year")
        params["year"] = year
    if state:
        where.append(f"{table_alias}.state = :state")
        params["state"] = state
    if source_type:
        where.append(f"{table_alias}.source_type = :source_type")
        params["source_type"] = source_type
    if politician_id:
        where.append(f"{table_alias}.politician_id = :politician_id")
        params["politician_id"] = politician_id
    if donor_type:
        where.append(
            f"EXISTS (SELECT 1 FROM tse.donors _dr "
            f"WHERE _dr.id = {table_alias}.donor_id AND _dr.donor_type = :donor_type)"
        )
        params["donor_type"] = donor_type
    return where, params


# ── Politician-specific donations ─────────────────────────────────────────────

@router.get("/politician/{politician_id}")
def get_politician_donations(
    politician_id: int,
    election_year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    where = ["dn.politician_id = :pid"]
    params: dict = {"pid": politician_id}
    if election_year:
        where.append("dn.election_year = :year")
        params["year"] = election_year

    rows = db.execute(text(f"""
        SELECT d.name, d.donor_type, d.cpf_cnpj_masked, d.state AS donor_state,
               dn.amount_brl, dn.election_year, dn.receipt_date, dn.source_type
        FROM tse.donations dn
        JOIN tse.donors d ON d.id = dn.donor_id
        WHERE {' AND '.join(where)}
        ORDER BY dn.amount_brl DESC
        LIMIT 200
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


# ── Aggregate endpoints ───────────────────────────────────────────────────────

@router.get("/source-types")
def donation_source_types(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT DISTINCT source_type
        FROM tse.donations
        WHERE source_type IS NOT NULL
        ORDER BY source_type
    """)).fetchall()
    return [r.source_type for r in rows]


@router.get("/by-year")
def donations_by_year(
    party_id: int | None = Query(None),
    state: str | None = Query(None),
    source_type: str | None = Query(None),
    politician_id: int | None = Query(None),
    donor_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    where, params = _build_filters(None, party_id, state, source_type, politician_id, donor_type)
    joins = ""
    if party_id:
        joins = "JOIN core.politicians pol ON pol.id = d.politician_id"
        where.append("pol.party_id = :party_id")
        params["party_id"] = party_id

    rows = db.execute(text(f"""
        SELECT d.election_year,
               COALESCE(d.source_type, 'Outros') AS source_type,
               SUM(d.amount_brl) AS total_amount
        FROM tse.donations d
        {joins}
        WHERE {' AND '.join(where)} AND d.election_year IS NOT NULL
        GROUP BY d.election_year, source_type
        ORDER BY d.election_year, total_amount DESC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/summary")
def donations_summary(
    year: int | None = Query(None),
    party_id: int | None = Query(None),
    state: str | None = Query(None),
    source_type: str | None = Query(None),
    politician_id: int | None = Query(None),
    donor_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    where, params = _build_filters(year, party_id, state, source_type, politician_id, donor_type)
    joins = ""
    if party_id:
        joins = "JOIN core.politicians pol ON pol.id = d.politician_id"
        where.append("pol.party_id = :party_id")
        params["party_id"] = party_id

    row = db.execute(text(f"""
        SELECT COALESCE(SUM(d.amount_brl), 0)      AS total_amount,
               COUNT(DISTINCT d.donor_id)           AS donor_count,
               COUNT(DISTINCT d.politician_id)      AS politician_count
        FROM tse.donations d
        {joins}
        WHERE {' AND '.join(where)}
    """), params).fetchone()
    return dict(row._mapping)


@router.get("/by-party")
def donations_by_party(
    year: int | None = Query(None),
    state: str | None = Query(None),
    source_type: str | None = Query(None),
    politician_id: int | None = Query(None),
    donor_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    where, params = _build_filters(year, None, state, source_type, politician_id, donor_type)
    rows = db.execute(text(f"""
        SELECT pa.id, pa.acronym, pa.name,
               SUM(d.amount_brl)              AS total_amount,
               COUNT(DISTINCT d.politician_id) AS politician_count
        FROM tse.donations d
        JOIN core.politicians pol ON pol.id = d.politician_id
        JOIN core.parties pa     ON pa.id  = pol.party_id
        WHERE {' AND '.join(where)}
        GROUP BY pa.id, pa.acronym, pa.name
        ORDER BY total_amount DESC
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/top-politicians")
def donations_top_politicians(
    year: int | None = Query(None),
    party_id: int | None = Query(None),
    state: str | None = Query(None),
    source_type: str | None = Query(None),
    politician_id: int | None = Query(None),
    donor_type: str | None = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    where, params = _build_filters(year, party_id, state, source_type, politician_id, donor_type)
    params["limit"] = limit
    if party_id:
        where.append("pol.party_id = :party_id")
        params["party_id"] = party_id

    rows = db.execute(text(f"""
        SELECT pol.id, pol.short_name, pol.state, pol.photo_url,
               pa.acronym AS party_acronym,
               SUM(d.amount_brl)             AS total_amount,
               COUNT(DISTINCT d.donor_id)    AS donor_count
        FROM tse.donations d
        JOIN core.politicians pol ON pol.id = d.politician_id
        JOIN core.parties pa     ON pa.id  = pol.party_id
        WHERE {' AND '.join(where)}
        GROUP BY pol.id, pol.short_name, pol.state, pol.photo_url, pa.acronym
        ORDER BY total_amount DESC
        LIMIT :limit
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/top-donors")
def donations_top_donors(
    year: int | None = Query(None),
    party_id: int | None = Query(None),
    state: str | None = Query(None),
    source_type: str | None = Query(None),
    donor_type: str | None = Query(None),
    politician_id: int | None = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    where = ["dn.politician_id IS NOT NULL"]
    params: dict = {"limit": limit}
    if year:
        where.append("dn.election_year = :year")
        params["year"] = year
    if state:
        where.append("dn.state = :state")
        params["state"] = state
    if source_type:
        where.append("dn.source_type = :source_type")
        params["source_type"] = source_type
    if politician_id:
        where.append("dn.politician_id = :politician_id")
        params["politician_id"] = politician_id
    if donor_type:
        where.append("dr.donor_type = :donor_type")
        params["donor_type"] = donor_type

    joins = ""
    if party_id:
        joins = "JOIN core.politicians pol ON pol.id = dn.politician_id"
        where.append("pol.party_id = :party_id")
        params["party_id"] = party_id

    rows = db.execute(text(f"""
        SELECT dr.id, dr.name, dr.donor_type, dr.cpf_cnpj_masked,
               dr.state AS donor_state,
               SUM(dn.amount_brl)              AS total_amount,
               COUNT(DISTINCT dn.politician_id) AS recipient_count
        FROM tse.donations dn
        JOIN tse.donors dr ON dr.id = dn.donor_id
        {joins}
        WHERE {' AND '.join(where)}
        GROUP BY dr.id, dr.name, dr.donor_type, dr.cpf_cnpj_masked, dr.state
        ORDER BY total_amount DESC
        LIMIT :limit
    """), params).fetchall()
    return [dict(r._mapping) for r in rows]
