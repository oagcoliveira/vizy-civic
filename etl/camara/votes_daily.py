"""
Daily ETL: Câmara nominal votes.

Fetches new votações since last successful run, then fetches individual votes
for each nominal votação and upserts into core.votacoes and core.individual_votes.

Usage:
    python -m camara.votes_daily
"""

import json
import sys
from datetime import date, timedelta

from sqlalchemy import text

from db import engine, last_successful_run, log_run
from camara.client import paginate, get

JOB_NAME = "camara_votes_daily"
CHUNK_DAYS = 30  # smaller chunks = fewer pages per request, less likely to hit timeouts


def _date_chunks(since: str, until: str):
    """Yield (start, end) pairs spanning [since, until] in CHUNK_DAYS windows."""
    start = date.fromisoformat(since)
    end = date.fromisoformat(until)
    while start <= end:
        chunk_end = min(start + timedelta(days=CHUNK_DAYS - 1), end)
        yield start.isoformat(), chunk_end.isoformat()
        start = chunk_end + timedelta(days=1)


def run():
    since = last_successful_run(JOB_NAME) or "2023-02-01"  # start of 57th legislature
    today = date.today().isoformat()
    print(f"[{JOB_NAME}] Fetching votações from {since} to {today}")

    try:
        # Phase 1: fetch all votações in chunks
        votacoes = []
        for chunk_start, chunk_end in _date_chunks(since, today):
            print(f"[{JOB_NAME}]   chunk {chunk_start} to {chunk_end}", flush=True)
            chunk_params = {"dataInicio": chunk_start, "dataFim": chunk_end, "ordem": "ASC"}
            votacoes.extend(paginate("/votacoes", chunk_params))

        fetched = len(votacoes)
        inserted = updated = 0
        print(f"[{JOB_NAME}] {fetched} votações fetched", flush=True)

        # Phase 2: upsert all votações (committed immediately)
        with engine.begin() as conn:
            for v in votacoes:
                row = {
                    "source": "camara",
                    "external_id": str(v["id"]),
                    "description": v.get("descricao"),
                    "voted_at": v.get("dataHoraRegistro"),  # correct field name from API
                    "vote_type": None,  # set to 'nominal' later if individual votes exist
                    "result": v.get("aprovacao"),
                    "session_label": v.get("siglaOrgao"),
                }
                res = conn.execute(
                    text("""
                        INSERT INTO core.votacoes (source, external_id, description, voted_at, vote_type, result, session_label)
                        VALUES (:source, :external_id, :description, :voted_at, :vote_type, :result, :session_label)
                        ON CONFLICT (source, external_id) DO UPDATE
                            SET description = EXCLUDED.description,
                                voted_at = EXCLUDED.voted_at,
                                vote_type = EXCLUDED.vote_type,
                                result = EXCLUDED.result
                        RETURNING (xmax = 0) AS was_inserted
                    """),
                    row,
                )
                was_inserted = res.fetchone()[0]
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1

        # Phase 3: individual votes — only plenário votações have nominal votes
        plen_ids = [str(v["id"]) for v in votacoes if v.get("siglaOrgao") == "PLEN"]
        print(f"[{JOB_NAME}] Fetching individual votes for {len(plen_ids)} plenário votações...", flush=True)
        for i, vid in enumerate(plen_ids, 1):
            if i % 50 == 0 or i == 1:
                print(f"[{JOB_NAME}]   individual votes: {i}/{len(plen_ids)}", flush=True)
            with engine.begin() as conn:
                _upsert_individual_votes(conn, vid)

        log_run(JOB_NAME, "success", fetched, inserted, updated, params={"since": since})
        print(f"[{JOB_NAME}] Done — {fetched} fetched, {inserted} inserted, {updated} updated")

    except Exception as exc:
        log_run(JOB_NAME, "failed", error=str(exc))
        print(f"[{JOB_NAME}] FAILED: {exc}", file=sys.stderr)
        raise


def _upsert_proposicoes(conn, votacao_id: int, votacao_external_id: str):
    """Fetch votação detail and upsert linked bills into core.bills / core.votacao_bills."""
    try:
        detail = get(f"/votacoes/{votacao_external_id}").get("dados", {})
    except Exception:
        return

    # Also fix voted_at from detail if available
    voted_at = detail.get("dataHoraRegistro")
    if voted_at:
        conn.execute(
            text("UPDATE core.votacoes SET voted_at = :ts WHERE id = :id AND voted_at IS NULL"),
            {"ts": voted_at, "id": votacao_id},
        )

    props = detail.get("proposicoesAfetadas", [])
    for i, p in enumerate(props):
        ext_id = p.get("id")
        if not ext_id:
            continue
        tipo = p.get("siglaTipo", "")
        numero = p.get("numero")
        ano = p.get("ano")
        title = f"{tipo} {numero}/{ano}" if tipo and numero and ano else None
        row = conn.execute(
            text("""
                INSERT INTO core.bills (source, external_id, type, number, year, title, ementa, full_text_url)
                VALUES ('camara', :eid, :type, :number, :year, :title, :ementa, :uri)
                ON CONFLICT (source, external_id) DO UPDATE
                    SET ementa = EXCLUDED.ementa
                RETURNING id
            """),
            {
                "eid": ext_id,
                "type": tipo or None,
                "number": numero,
                "year": ano,
                "title": title,
                "ementa": p.get("ementa"),
                "uri": p.get("uri"),
            },
        ).fetchone()
        if row:
            conn.execute(
                text("""
                    INSERT INTO core.votacao_bills (votacao_id, bill_id, is_primary)
                    VALUES (:vid, :bid, :primary)
                    ON CONFLICT (votacao_id, bill_id) DO NOTHING
                """),
                {"vid": votacao_id, "bid": row[0], "primary": i == 0},
            )


def _upsert_individual_votes(conn, votacao_external_id: str):
    try:
        votos = get(f"/votacoes/{votacao_external_id}/votos").get("dados", [])
    except Exception:
        votos = []  # 404 or other error — treat as no individual vote data
    if not votos:
        # Mark as checked so reruns skip it
        conn.execute(
            text("UPDATE core.votacoes SET vote_type = 'none' WHERE source = 'camara' AND external_id = :eid AND vote_type IS NULL"),
            {"eid": str(votacao_external_id)},
        )
        return

    try:
        orientacoes = {
            o.get("siglaPartidoLider", ""): o.get("orientacao", "")
            for o in get(f"/votacoes/{votacao_external_id}/orientacoes").get("dados", [])
            if o.get("siglaPartidoLider")
        }
    except Exception:
        orientacoes = {}  # no party orientations for this vote

    votacao_id_row = conn.execute(
        text("SELECT id FROM core.votacoes WHERE source = 'camara' AND external_id = :eid"),
        {"eid": str(votacao_external_id)},
    ).fetchone()
    if not votacao_id_row:
        return
    votacao_id = votacao_id_row[0]

    # Mark as nominal and fetch linked proposições
    conn.execute(
        text("UPDATE core.votacoes SET vote_type = 'nominal' WHERE id = :id"),
        {"id": votacao_id},
    )
    _upsert_proposicoes(conn, votacao_id, votacao_external_id)

    for voto in votos:
        dep_external_id = voto.get("deputado_", {}).get("id")
        if not dep_external_id:
            continue
        politician = conn.execute(
            text("SELECT id FROM core.politicians WHERE source = 'camara' AND external_id = :eid"),
            {"eid": dep_external_id},
        ).fetchone()
        if not politician:
            continue

        party = voto.get("deputado_", {}).get("siglaPartido", "")
        orientation = orientacoes.get(party)
        vote_value = voto.get("tipoVoto", "")
        followed = (vote_value == orientation) if orientation else None

        conn.execute(
            text("""
                INSERT INTO core.individual_votes
                    (votacao_id, politician_id, vote, party_at_time, party_orientation, followed_orientation)
                VALUES (:vid, :pid, :vote, :party, :orientation, :followed)
                ON CONFLICT (votacao_id, politician_id) DO UPDATE
                    SET vote = EXCLUDED.vote,
                        party_orientation = EXCLUDED.party_orientation,
                        followed_orientation = EXCLUDED.followed_orientation
            """),
            {
                "vid": votacao_id,
                "pid": politician[0],
                "vote": vote_value,
                "party": party,
                "orientation": orientation,
                "followed": followed,
            },
        )


if __name__ == "__main__":
    run()
