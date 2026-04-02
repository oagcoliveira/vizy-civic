"""
One-off load: TSE campaign donation data via Base dos Dados (BigQuery).

Queries br_tse_eleicoes.receitas_candidato for federal candidates (2018, 2022),
saves to CSV, then bulk-loads into tse.donors and tse.donations.

Prerequisites:
  - GCP project with billing enabled (BigQuery free tier: 1TB/month)
  - GOOGLE_APPLICATION_CREDENTIALS env var pointing to service account JSON
  - BIGQUERY_PROJECT_ID env var

Usage:
    python -m tse.donations_load
"""

import os
import sys

import pandas as pd
from sqlalchemy import text

from db import engine

BILLING_PROJECT = os.environ.get("BIGQUERY_PROJECT_ID", "vizy-bigquery")


def fetch_from_bigquery() -> pd.DataFrame:
    import basedosdados as bd

    print("[tse.donations_load] Querying Base dos Dados BigQuery...")
    df = bd.read_sql(
        """
        SELECT
            ano_eleicao,
            sigla_uf,
            cpf_candidato,
            nome_candidato,
            sigla_partido,
            cpf_cnpj_doador,
            nome_doador,
            valor_receita,
            fonte_receita,
            tipo_receita,
            data_receita,
            descricao_cargo
        FROM `basedosdados.br_tse_eleicoes.receitas_candidato`
        WHERE ano_eleicao IN (2022, 2018)
          AND descricao_cargo IN ('DEPUTADO FEDERAL', 'SENADOR')
        """,
        billing_project_id=BILLING_PROJECT,
    )
    print(f"[tse.donations_load] Fetched {len(df):,} rows from BigQuery")
    return df


def load_to_postgres(df: pd.DataFrame):
    print("[tse.donations_load] Loading into PostgreSQL...")
    inserted_donors = inserted_donations = 0

    with engine.begin() as conn:
        for _, row in df.iterrows():
            # Upsert donor (mask CPF/CNPJ for display)
            cpf_raw = str(row.get("cpf_cnpj_doador", ""))
            cpf_masked = _mask_cpf(cpf_raw)
            donor_type = "company" if len(cpf_raw.replace(".", "").replace("-", "").replace("/", "")) == 14 else "individual"

            donor = conn.execute(
                text("""
                    INSERT INTO tse.donors (cpf_cnpj_masked, name, donor_type, state)
                    VALUES (:masked, :name, :type, :state)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """),
                {"masked": cpf_masked, "name": row.get("nome_doador", ""), "type": donor_type, "state": row.get("sigla_uf")},
            ).fetchone()
            if donor:
                donor_id = donor[0]
                inserted_donors += 1
            else:
                donor_id = conn.execute(
                    text("SELECT id FROM tse.donors WHERE cpf_cnpj_masked = :m AND name = :n"),
                    {"m": cpf_masked, "n": row.get("nome_doador", "")},
                ).fetchone()[0]

            # Link to politician via CPF
            politician = conn.execute(
                text("SELECT id FROM core.politicians WHERE cpf = :cpf"),
                {"cpf": str(row.get("cpf_candidato", ""))},
            ).fetchone()
            if not politician:
                continue

            conn.execute(
                text("""
                    INSERT INTO tse.donations
                        (donor_id, politician_id, election_year, amount_brl,
                         receipt_date, source_type, office_sought, state)
                    VALUES
                        (:donor_id, :politician_id, :year, :amount,
                         :date, :source_type, :office, :state)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "donor_id": donor_id,
                    "politician_id": politician[0],
                    "year": int(row["ano_eleicao"]),
                    "amount": float(row.get("valor_receita", 0)),
                    "date": row.get("data_receita"),
                    "source_type": row.get("fonte_receita"),
                    "office": row.get("descricao_cargo"),
                    "state": row.get("sigla_uf"),
                },
            )
            inserted_donations += 1

    print(f"[tse.donations_load] Done — {inserted_donors} donors, {inserted_donations} donations inserted")


def _mask_cpf(cpf: str) -> str:
    digits = cpf.replace(".", "").replace("-", "").replace("/", "")
    if len(digits) == 11:
        return f"***.***.***-{digits[-2:]}"
    if len(digits) == 14:
        return f"**.***.***/****-{digits[-2:]}"
    return "***"


if __name__ == "__main__":
    df = fetch_from_bigquery()
    df.to_csv("donations_raw.csv", index=False)
    print("[tse.donations_load] Saved to donations_raw.csv")
    load_to_postgres(df)
