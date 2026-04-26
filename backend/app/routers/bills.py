import json
import os
import sys
import threading
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import BillTrack, User
from app.routers.auth import get_current_user

# ETL_DIR: in the Docker container this is /app/etl; locally it's backend/../etl.
# We read the same env var that main.py uses so the two are always in sync.
_ETL_DIR = Path(os.environ.get("ETL_DIR", str(Path(__file__).parent.parent / "etl")))

# One lock per bill to prevent concurrent enrichment of the same bill
_enrich_locks: dict[int, threading.Lock] = {}
_enrich_locks_mutex = threading.Lock()

router = APIRouter()


@router.get("/")
def list_bills(
    source: str | None = Query(None),
    type: str | None = Query(None),
    types: str | None = Query(None, description="Comma-separated list of bill types, e.g. PL,PEC,MPV"),
    status: str | None = Query(None),
    policy_area: str | None = Query(None),
    policy_areas: str | None = Query(None, description="Comma-separated policy areas, e.g. Saúde,Educação"),
    year: int | None = Query(None),
    search: str | None = Query(None),
    author_politician_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    where = ["1=1"]
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if source:
        where.append("source = :source")
        params["source"] = source
    # Support both ?type=PL (single, legacy) and ?types=PL,PEC,MPV (multi-select)
    _type_list = [t.strip() for t in types.split(",") if t.strip()] if types else ([type] if type else [])
    if _type_list:
        placeholders = ", ".join(f":type_{i}" for i in range(len(_type_list)))
        where.append(f"type IN ({placeholders})")
        for i, t in enumerate(_type_list):
            params[f"type_{i}"] = t
    if status:
        where.append("status = :status")
        params["status"] = status
    # Support both ?policy_area=X (single, legacy) and ?policy_areas=X,Y (multi-select)
    _pa_list = [a.strip() for a in policy_areas.split(",") if a.strip()] if policy_areas else ([policy_area] if policy_area else [])
    if _pa_list:
        pa_placeholders = ", ".join(f":pa_{i}" for i in range(len(_pa_list)))
        where.append(f"policy_area IN ({pa_placeholders})")
        for i, a in enumerate(_pa_list):
            params[f"pa_{i}"] = a
    if year:
        where.append("year = :year")
        params["year"] = year
    if search:
        where.append("(title ILIKE :search OR ementa ILIKE :search)")
        params["search"] = f"%{search}%"
    if author_politician_id:
        where.append("author_politician_id = :author_politician_id")
        params["author_politician_id"] = author_politician_id

    where_clause = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT id, source, external_id, type, number, year, title, ementa,
               short_title, summary, status, policy_area, policy_tags,
               author_label, full_text_url, presented_at, updated_at
        FROM core.bills
        WHERE {where_clause}
        ORDER BY presented_at DESC NULLS LAST, year DESC NULLS LAST, number DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT count(*) FROM core.bills WHERE {where_clause}
    """), params).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/policy-areas")
def get_policy_areas(db: Session = Depends(get_db)):
    """Returns all distinct policy_area values in the bills table."""
    rows = db.execute(text("""
        SELECT DISTINCT policy_area
        FROM core.bills
        WHERE policy_area IS NOT NULL
        ORDER BY policy_area
    """)).fetchall()
    return {"policy_areas": [r[0] for r in rows]}


@router.get("/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT b.id, b.source, b.external_id, b.type, b.number, b.year,
               b.title, b.ementa, b.short_title, b.summary, b.status,
               b.policy_area, b.policy_tags, b.is_controversial,
               b.author_label, b.full_text_url, b.updated_at,
               p.id AS author_politician_id, p.short_name AS author_name,
               p.photo_url AS author_photo, p.state AS author_state,
               pa.acronym AS author_party,
               -- Completeness signals used by the frontend Enrich button
               (b.status IS NULL) AS missing_detail,
               (b.short_title IS NULL OR b.policy_area IS NULL) AS missing_ai,
               NOT EXISTS (
                   SELECT 1 FROM core.legislative_events le WHERE le.bill_id = b.id
               ) AS missing_tramitacoes,
               EXISTS (
                   SELECT 1 FROM core.legislative_events le
                   WHERE le.bill_id = b.id
                     AND le.summary IS NULL
                     AND (le.stage IS NOT NULL OR le.description IS NOT NULL)
               ) AS missing_event_summaries
        FROM core.bills b
        LEFT JOIN core.politicians p ON p.id = b.author_politician_id
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE b.id = :id
    """), {"id": bill_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Bill not found")

    data = dict(row._mapping)

    # Derive a single boolean the frontend can use to decide whether to show the Enrich button
    ENRICH_TYPES = ("PL", "PLP", "PEC", "MPV", "PDL", "PRC", "MSC", "TVR", "PLN", "PDC")
    data["needs_enrichment"] = (
        data["source"] == "camara"
        and (
            data["missing_detail"]
            or data["missing_tramitacoes"]
            or (data["type"] in ENRICH_TYPES and data["ementa"] and data["missing_ai"])
            or data["missing_event_summaries"]
        )
    )

    return data


@router.get("/{bill_id}/votacoes")
def get_bill_votacoes(
    bill_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT v.id, v.external_id, v.description, v.voted_at, v.result,
               v.vote_type, vb.is_primary
        FROM core.votacao_bills vb
        JOIN core.votacoes v ON v.id = vb.votacao_id
        WHERE vb.bill_id = :bid
        ORDER BY v.voted_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), {"bid": bill_id, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()

    total = db.execute(
        text("SELECT count(*) FROM core.votacao_bills WHERE bill_id = :bid"),
        {"bid": bill_id}
    ).scalar()

    return {"total": total, "page": page, "items": [dict(r._mapping) for r in rows]}


@router.get("/{bill_id}/events")
def get_bill_events(bill_id: int, db: Session = Depends(get_db)):
    """Returns legislative events (tramitações) for a bill, oldest first."""
    rows = db.execute(text("""
        SELECT id, sequence, event_date, stage, description, summary, venue
        FROM core.legislative_events
        WHERE bill_id = :bid
        ORDER BY sequence ASC
    """), {"bid": bill_id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/{bill_id}/track")
def get_track_status(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check whether the authenticated user is tracking this bill."""
    track = db.query(BillTrack).filter_by(user_id=current_user.id, bill_id=bill_id).first()
    return {"tracking": track is not None}


@router.post("/{bill_id}/track", status_code=status.HTTP_201_CREATED)
def track_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track a bill. Idempotent — no error if already tracking."""
    existing = db.query(BillTrack).filter_by(user_id=current_user.id, bill_id=bill_id).first()
    if not existing:
        db.add(BillTrack(user_id=current_user.id, bill_id=bill_id))
        db.commit()
    return {"tracking": True}


@router.delete("/{bill_id}/track", status_code=status.HTTP_200_OK)
def untrack_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Untrack a bill. Idempotent — no error if not tracking."""
    existing = db.query(BillTrack).filter_by(user_id=current_user.id, bill_id=bill_id).first()
    if existing:
        db.delete(existing)
        db.commit()
    return {"tracking": False}


# ---------------------------------------------------------------------------
# Per-bill enrichment
# ---------------------------------------------------------------------------

def _get_bill_lock(bill_id: int) -> threading.Lock:
    """Return (creating if needed) a per-bill threading lock."""
    with _enrich_locks_mutex:
        if bill_id not in _enrich_locks:
            _enrich_locks[bill_id] = threading.Lock()
        return _enrich_locks[bill_id]


def _run_bill_enrichment(bill_id: int) -> None:
    """
    Background task: run the full enrichment pipeline for one bill, in-process.

    Runs four sequential steps:
      1. Detail ingest  — status, author, full_text_url  (Câmara API)
      2. Tramitações    — legislative events              (Câmara API)
      3. AI bill        — short_title, summary, policy_area (Claude Haiku)
      4. AI events      — plain-language event summaries  (Claude Haiku)

    The ETL modules are imported dynamically from ETL_DIR so this works both
    locally (etl/ next to backend/) and in the Docker container (/app/etl/).
    """
    lock = _get_bill_lock(bill_id)
    if not lock.acquire(blocking=False):
        print(f"[enrich_bill] bill_id={bill_id}: already running — skipped", flush=True)
        return

    try:
        etl_dir = str(_ETL_DIR)
        if etl_dir not in sys.path:
            sys.path.insert(0, etl_dir)

        # Import ETL helpers (safe to do after sys.path is patched)
        from camara.client import get as camara_get                          # noqa: E402
        from camara.bills_ingest_daily import (                              # noqa: E402
            _fetch_bill_detail, _resolve_author_politician_id
        )
        from camara.bills_enrich_daily import generate_ai_enrichment, ENRICH_TYPES  # noqa: E402
        from db import engine as etl_engine                                  # noqa: E402
        from sqlalchemy import text as sa_text                               # noqa: E402
        import anthropic, json as _json, time as _time                       # noqa: E402

        print(f"[enrich_bill] bill_id={bill_id}: starting enrichment", flush=True)

        # ------------------------------------------------------------------ #
        # Resolve bill from DB
        # ------------------------------------------------------------------ #
        with etl_engine.connect() as conn:
            row = conn.execute(sa_text("""
                SELECT id, external_id, source, status, short_title, policy_area,
                       ementa, type
                FROM core.bills WHERE id = :id
            """), {"id": bill_id}).fetchone()

        if not row:
            print(f"[enrich_bill] bill_id={bill_id}: not found in DB", flush=True)
            return

        external_id = row.external_id

        # ------------------------------------------------------------------ #
        # Step 1: Detail ingest (Câmara API)
        # ------------------------------------------------------------------ #
        print(f"[enrich_bill] bill_id={bill_id}: step 1 — detail ingest", flush=True)
        detail = _fetch_bill_detail(external_id)
        if detail:
            author_politician_id = _resolve_author_politician_id(detail.get("author_external_id"))
            with etl_engine.begin() as conn:
                conn.execute(sa_text("""
                    UPDATE core.bills SET
                        status               = COALESCE(:status,               status),
                        full_text_url        = COALESCE(:full_text_url,        full_text_url),
                        author_label         = COALESCE(:author_label,         author_label),
                        author_politician_id = COALESCE(:author_politician_id, author_politician_id),
                        updated_at           = now()
                    WHERE id = :id
                """), {
                    "id": bill_id,
                    "status": detail.get("status"),
                    "full_text_url": detail.get("full_text_url"),
                    "author_label": detail.get("author_label"),
                    "author_politician_id": author_politician_id,
                })
            print(f"[enrich_bill] bill_id={bill_id}: step 1 done — status={detail.get('status')!r}", flush=True)
        else:
            print(f"[enrich_bill] bill_id={bill_id}: step 1 — no detail returned from API", flush=True)

        # ------------------------------------------------------------------ #
        # Step 2: Tramitações ingest (Câmara API)
        # ------------------------------------------------------------------ #
        print(f"[enrich_bill] bill_id={bill_id}: step 2 — tramitações ingest", flush=True)
        try:
            events = camara_get(f"/proposicoes/{external_id}/tramitacoes").get("dados", [])
        except Exception as e:
            print(f"[enrich_bill] bill_id={bill_id}: step 2 WARNING — {e}", flush=True)
            events = []

        if events:
            rows_to_insert = []
            for ev in events:
                raw_date = ev.get("dataHora") or ev.get("data")
                rows_to_insert.append({
                    "bill_id": bill_id,
                    "sequence": ev.get("sequencia", 0),
                    "event_date": raw_date[:10] if raw_date else None,
                    "stage": (ev.get("descricaoTramitacao") or "")[:255] or None,
                    "description": ev.get("descricaoSituacao") or None,
                    "venue": (ev.get("siglaOrgao") or "")[:100] or None,
                })
            with etl_engine.begin() as conn:
                result = conn.execute(sa_text("""
                    INSERT INTO core.legislative_events
                        (bill_id, sequence, event_date, stage, description, venue)
                    VALUES
                        (:bill_id, :sequence, :event_date, :stage, :description, :venue)
                    ON CONFLICT (bill_id, sequence) DO NOTHING
                """), rows_to_insert)
                inserted = result.rowcount
            print(f"[enrich_bill] bill_id={bill_id}: step 2 done — {inserted} new events", flush=True)
        else:
            print(f"[enrich_bill] bill_id={bill_id}: step 2 — no events returned", flush=True)

        # Re-read bill to get fresh ementa/type after potential step-1 update
        with etl_engine.connect() as conn:
            row = conn.execute(sa_text("""
                SELECT id, type, number, year, title, ementa, short_title, policy_area
                FROM core.bills WHERE id = :id
            """), {"id": bill_id}).fetchone()

        # ------------------------------------------------------------------ #
        # Step 3: AI bill enrichment (Claude Haiku)
        # ------------------------------------------------------------------ #
        print(f"[enrich_bill] bill_id={bill_id}: step 3 — AI bill enrichment", flush=True)
        if (
            row
            and row.type in ENRICH_TYPES
            and row.ementa
            and (row.short_title is None or row.policy_area is None)
        ):
            try:
                ai = generate_ai_enrichment(
                    ementa=row.ementa,
                    title=row.title,
                    bill_type=row.type,
                    number=row.number,
                    year=row.year,
                )
                if any(ai.values()):
                    with etl_engine.begin() as conn:
                        conn.execute(sa_text("""
                            UPDATE core.bills SET
                                short_title = COALESCE(:short_title, short_title),
                                summary     = COALESCE(:summary,     summary),
                                policy_area = COALESCE(:policy_area, policy_area),
                                updated_at  = now()
                            WHERE id = :id
                        """), {
                            "id": bill_id,
                            "short_title": ai.get("short_title"),
                            "summary": ai.get("summary"),
                            "policy_area": ai.get("policy_area"),
                        })
                    print(f"[enrich_bill] bill_id={bill_id}: step 3 done — short_title={ai.get('short_title')!r}", flush=True)
                else:
                    print(f"[enrich_bill] bill_id={bill_id}: step 3 — AI returned empty result", flush=True)
            except Exception as exc:
                print(f"[enrich_bill] bill_id={bill_id}: step 3 FAILED — {exc}", flush=True)
        else:
            print(f"[enrich_bill] bill_id={bill_id}: step 3 — skipped (already enriched or no ementa)", flush=True)

        # ------------------------------------------------------------------ #
        # Step 4: AI legislative-event enrichment (Claude Haiku)
        # ------------------------------------------------------------------ #
        print(f"[enrich_bill] bill_id={bill_id}: step 4 — AI event enrichment", flush=True)
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            with etl_engine.connect() as conn:
                event_rows = conn.execute(sa_text("""
                    SELECT id, stage, description, venue
                    FROM core.legislative_events
                    WHERE bill_id = :bid
                      AND summary IS NULL
                      AND (stage IS NOT NULL OR description IS NOT NULL)
                    ORDER BY sequence ASC
                """), {"bid": bill_id}).fetchall()

            event_list = [dict(r._mapping) for r in event_rows]
            ok = 0
            for item in event_list:
                try:
                    parts = []
                    if item["stage"]:
                        parts.append(f"Fase: {item['stage']}")
                    if item["description"]:
                        parts.append(f"Situação: {item['description']}")
                    if item["venue"]:
                        parts.append(f"Órgão: {item['venue']}")
                    if not parts:
                        continue

                    prompt = (
                        "Você é um assistente de tecnologia cívica. Traduza esta etapa legislativa burocrática "
                        "para uma frase curta e clara em português simples (máximo 10 palavras), "
                        "como se explicasse para um cidadão leigo.\n\n"
                        + "\n".join(parts)
                        + '\n\nResponda APENAS com JSON no formato: {"label": "frase em português simples"}'
                    )
                    client = anthropic.Anthropic(api_key=anthropic_key)
                    msg = client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=100,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    raw = msg.content[0].text.strip()
                    if "```" in raw:
                        raw = raw.split("```")[1].lstrip("json").strip()
                    label = _json.loads(raw).get("label")
                    if label:
                        with etl_engine.begin() as conn:
                            conn.execute(
                                sa_text("UPDATE core.legislative_events SET summary = :s WHERE id = :id"),
                                {"s": label, "id": item["id"]},
                            )
                        ok += 1
                except Exception as exc:
                    print(f"[enrich_bill] bill_id={bill_id}: step 4 event id={item['id']} FAILED — {exc}", flush=True)
                finally:
                    _time.sleep(0.3)

            print(f"[enrich_bill] bill_id={bill_id}: step 4 done — {ok}/{len(event_list)} events enriched", flush=True)
        else:
            print(f"[enrich_bill] bill_id={bill_id}: step 4 — skipped (ANTHROPIC_API_KEY not set)", flush=True)

        print(f"[enrich_bill] bill_id={bill_id}: all steps complete", flush=True)

    except Exception as exc:
        print(f"[enrich_bill] bill_id={bill_id}: unexpected error — {exc}", flush=True)
    finally:
        lock.release()


@router.post("/{bill_id}/enrich", status_code=status.HTTP_202_ACCEPTED)
def enrich_bill(
    bill_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger the full enrichment pipeline for a single Câmara bill.

    Runs sequentially in the background (in-process):
      1. Detail ingest  — status, author, full_text_url  (Câmara API)
      2. Tramitações    — legislative events              (Câmara API)
      3. AI bill        — short_title, summary, policy_area (Claude Haiku)
      4. AI events      — plain-language event summaries  (Claude Haiku)

    Any authenticated user may trigger this.
    Returns 409 if the bill is already fully enriched.
    """
    # Verify the bill exists and is a Câmara bill
    row = db.execute(text("""
        SELECT id, source, status, short_title, policy_area, ementa, type,
               EXISTS (
                   SELECT 1 FROM core.legislative_events WHERE bill_id = core.bills.id
               ) AS has_events
        FROM core.bills
        WHERE id = :id
    """), {"id": bill_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Bill not found")

    if row.source != "camara":
        raise HTTPException(
            status_code=422,
            detail=f"Only 'camara' bills are supported for per-bill enrichment (this bill has source='{row.source}').",
        )

    # Determine whether there is actually anything to do
    ENRICH_TYPES = ("PL", "PLP", "PEC", "MPV", "PDL", "PRC", "MSC", "TVR", "PLN", "PDC")
    needs_detail   = row.status is None
    needs_tramit   = not row.has_events
    needs_ai_bill  = (
        row.type in ENRICH_TYPES
        and row.ementa is not None
        and (row.short_title is None or row.policy_area is None)
    )
    needs_ai_events = db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM core.legislative_events
            WHERE bill_id = :id AND summary IS NULL
              AND (stage IS NOT NULL OR description IS NOT NULL)
        )
    """), {"id": bill_id}).scalar()

    if not any([needs_detail, needs_tramit, needs_ai_bill, needs_ai_events]):
        raise HTTPException(
            status_code=409,
            detail="Bill is already fully enriched — nothing to do.",
        )

    background_tasks.add_task(_run_bill_enrichment, bill_id)

    return {
        "status": "enrichment_started",
        "bill_id": bill_id,
        "pending": {
            "detail": needs_detail,
            "tramitacoes": needs_tramit,
            "ai_bill": needs_ai_bill,
            "ai_events": needs_ai_events,
        },
    }
