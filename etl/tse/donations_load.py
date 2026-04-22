"""
Load TSE donation data from Manus-produced CSVs into PostgreSQL.

Imports ALL donations regardless of whether the candidate has a politician
record in core.politicians. politician_id is set where a CPF match exists
and left NULL otherwise (historical candidates not in current legislature).

Expects:
  vizy_donors_all_years.csv    — deduplicated donors
  vizy_donations_all_years.csv — all donation records with cpf_candidato

Usage:
    cd etl
    python -m tse.donations_load \
        --donors   ../manus/vizy_donors_all_years.csv \
        --donations ../manus/vizy_donations_all_years.csv

Prerequisites:
  - Migrations 005 and 006 applied
  - politicians_weekly run (to populate core.politicians.cpf for matching)
"""

import argparse
import re
import sys

import pandas as pd
from sqlalchemy import text

from db import engine

CHUNK = 5000  # rows per bulk insert


def load_donors(donors_csv: str) -> dict[str, int]:
    """Bulk-upsert donors. Returns {cpf_cnpj_raw: donor_id} map."""
    df = pd.read_csv(donors_csv, dtype=str)
    df = df.where(pd.notna(df), None)
    total = len(df)
    print(f"[donations_load] Loading {total:,} donors from {donors_csv}")

    cpf_to_id: dict[str, int] = {}

    with engine.begin() as conn:
        for start in range(0, total, CHUNK):
            chunk = df.iloc[start:start + CHUNK]
            for _, row in chunk.iterrows():
                cpf_raw = row.get("cpf_cnpj_raw")
                result = conn.execute(
                    text("""
                        INSERT INTO tse.donors
                            (cpf_cnpj_raw, cpf_cnpj_masked, name, donor_type, state)
                        VALUES (:raw, :masked, :name, :dtype, :state)
                        ON CONFLICT (cpf_cnpj_raw) WHERE cpf_cnpj_raw IS NOT NULL DO UPDATE
                            SET name = EXCLUDED.name
                        RETURNING id
                    """),
                    {
                        "raw":    cpf_raw,
                        "masked": row.get("cpf_cnpj_masked"),
                        "name":   row.get("name") or "Desconhecido",
                        "dtype":  row.get("donor_type", "individual"),
                        "state":  row.get("state"),
                    },
                ).fetchone()
                if result and cpf_raw:
                    cpf_to_id[cpf_raw] = result[0]

            pct = min(start + CHUNK, total)
            print(f"  donors {pct:,}/{total:,}", end="\r", flush=True)

    print(f"\n[donations_load] Donors done — {len(cpf_to_id):,} mapped")
    return cpf_to_id


def load_donations(donations_csv: str, cpf_to_donor_id: dict[str, int]):
    """Bulk-insert all donations. Matches politician by CPF where possible."""
    df = pd.read_csv(donations_csv, dtype=str)
    df = df.where(pd.notna(df), None)
    total = len(df)
    print(f"[donations_load] Loading {total:,} donations from {donations_csv}")

    with engine.begin() as conn:
        # Build CPF → politician_id map (digits-only keys for format-agnostic matching)
        # Câmara API stores CPF as raw digits; TSE data stores formatted (XXX.XXX.XXX-XX)
        rows = conn.execute(
            text("SELECT cpf, id FROM core.politicians WHERE cpf IS NOT NULL")
        ).fetchall()
        cpf_to_politician = {r[0]: r[1] for r in rows}  # digits-only keys
        print(f"[donations_load] Politicians with CPF: {len(cpf_to_politician):,}")

    inserted = matched = no_donor = 0

    with engine.begin() as conn:
        for start in range(0, total, CHUNK):
            chunk = df.iloc[start:start + CHUNK]
            params = []
            for _, row in chunk.iterrows():
                cpf_donor = row.get("cpf_cnpj_raw_donor")
                cpf_cand  = row.get("cpf_candidato") or None

                donor_id = cpf_to_donor_id.get(cpf_donor)
                if not donor_id:
                    no_donor += 1
                    continue

                # Normalize CPF to digits-only for matching (TSE uses formatted, Câmara uses raw digits)
                cpf_cand_digits = re.sub(r"\D", "", cpf_cand) if cpf_cand else None
                politician_id = cpf_to_politician.get(cpf_cand_digits) if cpf_cand_digits else None
                if politician_id:
                    matched += 1

                try:
                    amount = float(row.get("amount_brl") or 0)
                except (ValueError, TypeError):
                    amount = 0.0

                params.append({
                    "donor_id":       donor_id,
                    "politician_id":  politician_id,   # NULL if no match — that's OK
                    "cpf_candidato":  cpf_cand,
                    "election_year":  int(row["election_year"]),
                    "amount_brl":     amount,
                    "date":           row.get("receipt_date") or None,
                    "source_type":    row.get("source_type"),
                    "office":         row.get("office_sought"),
                    "state":          row.get("state"),
                })

            if params:
                conn.execute(
                    text("""
                        INSERT INTO tse.donations
                            (donor_id, politician_id, cpf_candidato, election_year,
                             amount_brl, receipt_date, source_type, office_sought, state)
                        VALUES
                            (:donor_id, :politician_id, :cpf_candidato, :election_year,
                             :amount_brl, :date, :source_type, :office, :state)
                        ON CONFLICT DO NOTHING
                    """),
                    params,
                )
                inserted += len(params)

            pct = min(start + CHUNK, total)
            print(f"  donations {pct:,}/{total:,} | matched={matched:,} | no_donor={no_donor:,}",
                  end="\r", flush=True)

    print(f"\n[donations_load] Done — {inserted:,} inserted, "
          f"{matched:,} matched to a politician, "
          f"{no_donor:,} skipped (donor not in donors file)")


def run(donors_csv: str, donations_csv: str):
    cpf_to_donor_id = load_donors(donors_csv)
    load_donations(donations_csv, cpf_to_donor_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--donors",    required=True)
    parser.add_argument("--donations", required=True)
    args = parser.parse_args()
    run(args.donors, args.donations)
