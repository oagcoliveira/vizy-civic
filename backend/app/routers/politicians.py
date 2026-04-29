from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
import re
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import PoliticianFollow
from app.models.core import Politician
from app.routers.auth import get_current_user
from app.models.auth import User

router = APIRouter()

POLITICIAN_COLS = """
    p.id, p.short_name, p.name, p.state, p.current_office,
    p.photo_url, p.gender, p.ai_bio, p.email, p.website_url,
    pa.acronym AS party
"""


_COMMITTEE_NAME_OVERRIDES = {
    "1SECM": "1ª Secretaria",
    "2SECM": "2ª Secretaria",
    "3SECM": "3ª Secretaria",
    "4SECM": "4ª Secretaria",
    "1VIPR": "1ª Vice-Presidência",
    "2VIPR": "2ª Vice-Presidência",
    "BANEGRA": "Bancada Negra",
    "CAPADR": "Agricultura",
    "CASP": "Administração e Serviço Público",
    "CCJC": "Constituição e Justiça",
    "CCOM": "Comunicação",
    "CCOMSOC": "Conselho de Comunicação Social",
    "CCTI": "Ciência, Tecnologia e Inovação",
    "CCULT": "Cultura",
    "CDC": "Defesa do Consumidor",
    "CDE": "Desenvolvimento Econômico",
    "CDHMIR": "Direitos Humanos e Igualdade Racial",
    "CDMULHER": "Direitos da Mulher",
    "CDU": "Desenvolvimento Urbano",
    "CE": "Educação",
    "CESPO": "Esporte",
    "CFT": "Finanças e Tributação",
    "CFFC": "Fiscalização e Controle",
    "CIDOSO": "Pessoa Idosa",
    "CINDRE": "Integração Nacional",
    "CLP": "Legislação Participativa",
    "CMADS": "Meio Ambiente",
    "CME": "Minas e Energia",
    "CMULHER": "Direitos da Mulher",
    "CPD": "Pessoas com Deficiência",
    "CPOVOS": "Amazônia e Povos Originários",
    "CREDN": "Relações Exteriores e Defesa",
    "CSPCCO": "Segurança Pública",
    "CSSF": "Saúde",
    "CTASP": "Trabalho e Serviço Público",
    "CVT": "Viação e Transportes",
}

_SMALL_WORDS = {"a", "à", "ao", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "para"}
_VERBOSE_REPLACEMENTS = (
    (r"Agricultura,\s*Pecu[áa]ria,\s*Abastecimento\s+e\s+Desenvolvimento\s+Rural", "Agricultura"),
    (r"Administra[çc][aã]o\s+e\s+Servi[çc]o\s+P[úu]blico", "Administração e Serviço Público"),
    (r"Constitui[çc][aã]o\s+e\s+Justi[çc]a\s+e\s+de\s+Cidadania", "Constituição e Justiça"),
    (r"Direitos\s+Humanos,\s*Minorias\s+e\s+Igualdade\s+Racial", "Direitos Humanos e Igualdade Racial"),
    (r"Fiscaliza[çc][aã]o\s+Financeira\s+e\s+Controle", "Fiscalização e Controle"),
    (r"Seguran[çc]a\s+P[úu]blica\s+e\s+Combate\s+ao\s+Crime\s+Organizado", "Segurança Pública"),
    (r"Rela[çc][õo]es\s+Exteriores\s+e\s+de\s+Defesa\s+Nacional", "Relações Exteriores e Defesa"),
    (r"Trabalho,\s*de\s+Administra[çc][aã]o\s+e\s+Servi[çc]o\s+P[úu]blico", "Trabalho e Serviço Público"),
    (r"Defesa\s+dos\s+Direitos\s+das\s+Pessoas\s+com\s+Defici[êe]ncia", "Pessoas com Deficiência"),
    (r"Defesa\s+dos\s+Direitos\s+da\s+Mulher", "Direitos da Mulher"),
    (r"Defesa\s+dos\s+Direitos\s+da\s+Pessoa\s+Idosa", "Pessoa Idosa"),
    (r"Amaz[ôo]nia\s+e\s+dos\s+Povos\s+Origin[áa]rios\s+e\s+Tradicionais", "Amazônia e Povos Originários"),
    (r"Integra[çc][aã]o\s+Nacional\s+e\s+Desenvolvimento\s+Regional", "Integração Nacional"),
)


def _committee_display_name_expr(db: Session) -> str:
    """Return a safe SQL expression for committee labels before or after clean_name migration."""
    has_clean_name = db.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'core'
              AND table_name = 'committees'
              AND column_name = 'clean_name'
        )
    """)).scalar()
    return "COALESCE(NULLIF(c.clean_name, ''), c.name)" if has_clean_name else "c.name"


def _titlecase_pt(label: str) -> str:
    words = label.lower().split()
    return " ".join(word if i > 0 and word in _SMALL_WORDS else word[:1].upper() + word[1:] for i, word in enumerate(words))


def _clean_committee_label(name: str | None, acronym: str | None, display_name: str | None = None) -> str | None:
    """Clean committee labels at read time, falling back to the API name when needed."""
    acronym_key = (acronym or "").strip().upper()
    if acronym_key in _COMMITTEE_NAME_OVERRIDES:
        return _COMMITTEE_NAME_OVERRIDES[acronym_key]

    label = " ".join((display_name or name or "").split())
    if not label:
        return None

    for prefix in ("Comissão Permanente ", "Comissão de ", "Comissão da ", "Comissão do ", "Comissão das ", "Comissão dos ", "Comissão "):
        if label.lower().startswith(prefix.lower()):
            label = label[len(prefix):]
            break

    for prefix in ("Especial destinada a ", "Especial destinada ao ", "Especial destinada à "):
        if label.lower().startswith(prefix.lower()):
            label = "Especial: " + label[len(prefix):]
            break

    for pattern, replacement in _VERBOSE_REPLACEMENTS:
        label = re.sub(pattern, replacement, label, flags=re.IGNORECASE)

    label = _titlecase_pt(label)
    return (label[:87].rstrip() + "...") if len(label) > 90 else (label or None)


def _normalize_committee_rows(rows) -> list[dict]:
    items = [dict(r._mapping) for r in rows]
    for item in items:
        item["display_name"] = _clean_committee_label(item.get("name"), item.get("acronym"), item.get("display_name")) or item.get("display_name") or item.get("name")
    return items


@router.get("/")
def list_politicians(
    source: str | None = Query(None, description="'camara' or 'senado'"),
    state: str | None = Query(None),
    party: str | None = Query(None),
    search: str | None = Query(None),
    committee_id: int | None = Query(None, description="Filter by active committee membership"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    where = ["p.is_active = TRUE"]
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if source:
        where.append("p.source = :source")
        params["source"] = source
    if state:
        where.append("p.state = :state")
        params["state"] = state
    if party:
        where.append("pa.acronym = :party")
        params["party"] = party
    if search:
        where.append("p.short_name ILIKE :search")
        params["search"] = f"%{search}%"
    if committee_id:
        where.append("""
            EXISTS (
                SELECT 1
                FROM core.committee_memberships cm
                WHERE cm.politician_id = p.id
                  AND cm.committee_id = :committee_id
                  AND (cm.ended_at IS NULL OR cm.ended_at >= CURRENT_DATE)
            )
        """)
        params["committee_id"] = committee_id

    where_clause = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT {POLITICIAN_COLS}
        FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE {where_clause}
        ORDER BY p.short_name
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT count(*) FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE {where_clause}
    """), params).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/autocomplete/all")
def politicians_autocomplete(db: Session = Depends(get_db)):
    """Lightweight full list for client-side autocomplete (id, short_name, state, party)."""
    rows = db.execute(text("""
        SELECT p.id, p.short_name, p.state, pa.acronym AS party
        FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE p.is_active = TRUE
        ORDER BY p.short_name
    """)).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/filters/committees")
def list_committee_filters(
    source: str | None = Query("camara", description="Filter committee options by source"),
    db: Session = Depends(get_db),
):
    """Returns active committees with active member counts for listing filters."""
    display_name_expr = _committee_display_name_expr(db)
    where = ["c.is_active = TRUE", "p.is_active = TRUE", "(cm.ended_at IS NULL OR cm.ended_at >= CURRENT_DATE)"]
    params: dict = {}

    if source:
        where.append("c.source = :source")
        where.append("p.source = :source")
        params["source"] = source

    where_clause = " AND ".join(where)
    rows = db.execute(text(f"""
        SELECT c.id, c.acronym, c.name,
               {display_name_expr} AS display_name,
               count(DISTINCT cm.politician_id) AS member_count
        FROM core.committees c
        JOIN core.committee_memberships cm ON cm.committee_id = c.id
        JOIN core.politicians p ON p.id = cm.politician_id
        WHERE {where_clause}
        GROUP BY c.id, c.acronym, c.name, {display_name_expr}
        ORDER BY COALESCE(NULLIF(c.acronym, ''), {display_name_expr})
    """), params).fetchall()
    return _normalize_committee_rows(rows)


@router.get("/{politician_id}")
def get_politician(politician_id: int, db: Session = Depends(get_db)):
    row = db.execute(text(f"""
        SELECT {POLITICIAN_COLS}
        FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE p.id = :id
    """), {"id": politician_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Politician not found")
    return dict(row._mapping)


@router.get("/{politician_id}/stats")
def get_politician_stats(politician_id: int, db: Session = Depends(get_db)):
    votes = db.execute(
        text("SELECT count(*) FROM core.individual_votes WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    speeches = db.execute(
        text("SELECT count(*) FROM core.speeches WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    bills = db.execute(
        text("SELECT count(*) FROM core.bills WHERE author_politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    return {"votes": votes, "speeches": speeches, "bills": bills}


@router.get("/{politician_id}/votes")
def get_politician_votes(
    politician_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT iv.vote, iv.party_at_time, iv.party_orientation, iv.followed_orientation,
               v.id AS votacao_id, v.external_id AS votacao_external_id,
               v.voted_at, v.result, v.description,
               b.id AS bill_id, b.short_title, b.ementa, b.type, b.number, b.year
        FROM core.individual_votes iv
        JOIN core.votacoes v ON v.id = iv.votacao_id
        LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
        LEFT JOIN core.bills b ON b.id = vb.bill_id
        WHERE iv.politician_id = :id
        ORDER BY v.voted_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {"id": politician_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
    total = db.execute(
        text("SELECT count(*) FROM core.individual_votes WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{politician_id}/activity")
def get_politician_activity(
    politician_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    """Merged reverse-chronological timeline of votes and speeches."""
    rows = db.execute(text("""
        SELECT event_type, event_date, event_id, title, description, vote, votacao_id
        FROM (
            SELECT
                'vote' AS event_type,
                v.voted_at AS event_date,
                iv.id AS event_id,
                COALESCE(b.short_title, b.ementa, v.description) AS title,
                NULL AS description,
                iv.vote AS vote,
                v.id AS votacao_id
            FROM core.individual_votes iv
            JOIN core.votacoes v ON v.id = iv.votacao_id
            LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
            LEFT JOIN core.bills b ON b.id = vb.bill_id
            WHERE iv.politician_id = :id

            UNION ALL

            SELECT
                'speech' AS event_type,
                s.delivered_at AS event_date,
                s.id AS event_id,
                s.phase AS title,
                s.summary AS description,
                NULL AS vote,
                NULL AS votacao_id
            FROM core.speeches s
            WHERE s.politician_id = :id
        ) combined
        ORDER BY event_date DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {"id": politician_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()

    total = db.execute(text("""
        SELECT (
            SELECT count(*) FROM core.individual_votes WHERE politician_id = :id
        ) + (
            SELECT count(*) FROM core.speeches WHERE politician_id = :id
        )
    """), {"id": politician_id}).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{politician_id}/speeches")
def get_politician_speeches(
    politician_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT id, delivered_at, phase, summary, keywords, full_text_url
        FROM core.speeches
        WHERE politician_id = :id
        ORDER BY delivered_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {"id": politician_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
    total = db.execute(
        text("SELECT count(*) FROM core.speeches WHERE politician_id = :id"),
        {"id": politician_id}
    ).scalar()
    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{politician_id}/committees")
def get_politician_committees(politician_id: int, db: Session = Depends(get_db)):
    """Returns active committee memberships for a politician."""
    display_name_expr = _committee_display_name_expr(db)
    rows = db.execute(text(f"""
        SELECT c.id, c.acronym, c.name,
               {display_name_expr} AS display_name,
               cm.role, cm.started_at, cm.ended_at
        FROM core.committee_memberships cm
        JOIN core.committees c ON c.id = cm.committee_id
        WHERE cm.politician_id = :id
        ORDER BY cm.ended_at IS NOT NULL, cm.started_at DESC NULLS LAST
    """), {"id": politician_id}).fetchall()
    return _normalize_committee_rows(rows)


@router.get("/{politician_id}/follow")
def get_follow_status(
    politician_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check whether the authenticated user follows this politician."""
    follows = db.query(PoliticianFollow).filter_by(
        user_id=current_user.id, politician_id=politician_id
    ).first()
    return {"following": follows is not None}


@router.post("/{politician_id}/follow", status_code=status.HTTP_201_CREATED)
def follow_politician(
    politician_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Follow a politician. Idempotent — no error if already following."""
    existing = db.query(PoliticianFollow).filter_by(
        user_id=current_user.id, politician_id=politician_id
    ).first()
    if not existing:
        db.add(PoliticianFollow(user_id=current_user.id, politician_id=politician_id))
        db.commit()
    return {"following": True}


@router.delete("/{politician_id}/follow", status_code=status.HTTP_200_OK)
def unfollow_politician(
    politician_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unfollow a politician. Idempotent — no error if not following."""
    existing = db.query(PoliticianFollow).filter_by(
        user_id=current_user.id, politician_id=politician_id
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
    return {"following": False}
