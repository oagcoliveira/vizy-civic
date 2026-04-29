"""
Committees sync ETL: fetches committee memberships for all active deputies.

For each active politician in core.politicians (source = 'camara'):
  1. Calls GET /deputados/{external_id}/orgaos
  2. Upserts committees into core.committees
  3. Upserts memberships into core.committee_memberships

Usage:
    python -m camara.commissions_sync              # full sync
    python -m camara.commissions_sync --limit 20   # test run
"""

import argparse
from datetime import datetime, timezone

from sqlalchemy import text

from db import engine, log_run
from camara.client import get

JOB_NAME = "camara_commissions_sync"

_COMMISSION_NAME_OVERRIDES = {
    "CAPADR": "Agricultura",
    "CCJC": "Constituição e Justiça",
    "CCTI": "Ciência, Tecnologia e Inovação",
    "CCOM": "Comunicação",
    "CDC": "Defesa do Consumidor",
    "CDE": "Desenvolvimento Econômico",
    "CDU": "Desenvolvimento Urbano",
    "CE": "Educação",
    "CESPO": "Esporte",
    "CFT": "Finanças e Tributação",
    "CFFC": "Fiscalização e Controle",
    "CMADS": "Meio Ambiente",
    "CME": "Minas e Energia",
    "CREDN": "Relações Exteriores e Defesa",
    "CSPCCO": "Segurança Pública",
    "CSSF": "Saúde",
    "CTASP": "Trabalho e Serviço Público",
    "CVT": "Viação e Transportes",
    "CLP": "Legislação Participativa",
    "CPD": "Pessoas com Deficiência",
    "CMULHER": "Direitos da Mulher",
    "CIDOSO": "Pessoa Idosa",
    "CPOVOS": "Amazônia e Povos Originários",
    "CINDRE": "Integração Nacional",
    "CCULT": "Cultura",
}

_SMALL_WORDS = {"a", "à", "ao", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "para"}

_VERBOSE_REPLACEMENTS = (
    ("Agricultura, Pecuária, Abastecimento e Desenvolvimento Rural", "Agricultura"),
    ("Fiscalização Financeira e Controle", "Fiscalização e Controle"),
    ("Segurança Pública e Combate ao Crime Organizado", "Segurança Pública"),
    ("Relações Exteriores e de Defesa Nacional", "Relações Exteriores e Defesa"),
    ("Trabalho, de Administração e Serviço Público", "Trabalho e Serviço Público"),
    ("Defesa dos Direitos das Pessoas com Deficiência", "Pessoas com Deficiência"),
    ("Defesa dos Direitos da Mulher", "Direitos da Mulher"),
    ("Defesa dos Direitos da Pessoa Idosa", "Pessoa Idosa"),
    ("Amazônia e dos Povos Originários e Tradicionais", "Amazônia e Povos Originários"),
    ("Integração Nacional e Desenvolvimento Regional", "Integração Nacional"),
)


def clean_committee_name(raw_name: str | None, acronym: str | None) -> str | None:
    """Return a concise, consistently capitalized committee label."""
    acronym_key = (acronym or "").strip().upper()
    if acronym_key in _COMMISSION_NAME_OVERRIDES:
        return _COMMISSION_NAME_OVERRIDES[acronym_key]

    if not raw_name:
        return None

    label = " ".join(raw_name.split())
    for prefix in (
        "Comissão Permanente ",
        "Comissão de ",
        "Comissão da ",
        "Comissão do ",
        "Comissão das ",
        "Comissão dos ",
        "Comissão ",
    ):
        if label.lower().startswith(prefix.lower()):
            label = label[len(prefix):]
            break

    special_prefixes = (
        "Especial destinada a ",
        "Especial destinada ao ",
        "Especial destinada à ",
    )
    for prefix in special_prefixes:
        if label.lower().startswith(prefix.lower()):
            label = "Especial: " + label[len(prefix):]
            break

    for old, new in _VERBOSE_REPLACEMENTS:
        label = label.replace(old, new)

    words = label.lower().split()
    label = " ".join(
        word if i > 0 and word in _SMALL_WORDS else word[:1].upper() + word[1:]
        for i, word in enumerate(words)
    )

    return (label[:87].rstrip() + "...") if len(label) > 90 else (label or None)


def run(limit: int | None = None):
    started_at = datetime.now(timezone.utc)

    # Fetch all active deputies and detect whether the clean-name migration is present.
    with engine.connect() as conn:
        query = "SELECT id, external_id FROM core.politicians WHERE source = 'camara' AND is_active = TRUE ORDER BY id"
        if limit:
            query += f" LIMIT {limit}"
        politicians = conn.execute(text(query)).fetchall()
        has_clean_name = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'core'
                  AND table_name = 'committees'
                  AND column_name = 'clean_name'
            )
        """)).scalar()

    total = len(politicians)
    print(f"Syncing committees for {total} active deputies{'  (test run)' if limit else ''}...", flush=True)

    committees_upserted = 0
    memberships_upserted = 0

    for i, (politician_id, external_id) in enumerate(politicians, 1):
        if i % 50 == 0 or i == 1:
            print(f"  {i}/{total} (politician_id={politician_id})", flush=True)

        try:
            orgaos = get(f"/deputados/{external_id}/orgaos", {"itens": 100}).get("dados", [])
        except Exception as e:
            print(f"    WARNING: could not fetch orgaos for {external_id}: {e}", flush=True)
            continue

        for orgao in orgaos:
            committee_external_id = str(orgao.get("idOrgao", ""))
            if not committee_external_id:
                continue

            acronym = (orgao.get("siglaOrgao") or "")[:50] or None
            name = (orgao.get("nomePublicacao") or orgao.get("nomeOrgao") or "")[:500] or None
            clean_name = clean_committee_name(name, acronym)
            role = (orgao.get("titulo") or "")[:100] or None

            # Parse dates
            started_at_str = orgao.get("dataInicio")
            ended_at_str = orgao.get("dataFim")
            started_at_val = started_at_str[:10] if started_at_str else None
            ended_at_val = ended_at_str[:10] if ended_at_str else None

            with engine.begin() as conn:
                # Upsert committee. Use clean_name only after the migration exists.
                if has_clean_name:
                    committee_row = conn.execute(text("""
                        INSERT INTO core.committees (source, external_id, acronym, name, clean_name, is_active)
                        VALUES ('camara', :eid, :acronym, :name, :clean_name, TRUE)
                        ON CONFLICT (source, external_id) DO UPDATE
                            SET acronym = EXCLUDED.acronym,
                                name = EXCLUDED.name,
                                clean_name = EXCLUDED.clean_name
                        RETURNING id
                    """), {
                        "eid": committee_external_id,
                        "acronym": acronym,
                        "name": name,
                        "clean_name": clean_name,
                    }).fetchone()
                else:
                    committee_row = conn.execute(text("""
                        INSERT INTO core.committees (source, external_id, acronym, name, is_active)
                        VALUES ('camara', :eid, :acronym, :name, TRUE)
                        ON CONFLICT (source, external_id) DO UPDATE
                            SET acronym = EXCLUDED.acronym,
                                name = EXCLUDED.name
                        RETURNING id
                    """), {
                        "eid": committee_external_id,
                        "acronym": acronym,
                        "name": name,
                    }).fetchone()

                if not committee_row:
                    continue

                committee_id = committee_row[0]
                committees_upserted += 1

                # Upsert membership
                conn.execute(text("""
                    INSERT INTO core.committee_memberships
                        (politician_id, committee_id, role, started_at, ended_at)
                    VALUES (:pid, :cid, :role, :started, :ended)
                    ON CONFLICT (politician_id, committee_id) DO UPDATE
                        SET role = EXCLUDED.role,
                            started_at = EXCLUDED.started_at,
                            ended_at = EXCLUDED.ended_at
                """), {
                    "pid": politician_id,
                    "cid": committee_id,
                    "role": role,
                    "started": started_at_val,
                    "ended": ended_at_val,
                })
                memberships_upserted += 1

    finished_at = datetime.now(timezone.utc)
    log_run(JOB_NAME, "success", committees_upserted, memberships_upserted, 0,
            params={"limit": limit})

    print(f"Done! {committees_upserted} committee rows, {memberships_upserted} memberships.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process this many deputies")
    args = parser.parse_args()
    run(limit=args.limit)
