"""
One-time backfill: fetch proposições for all nominal votações already in the DB.
Also fixes voted_at (which was NULL due to the list endpoint not returning it).

NOTE: core.proposicoes has been migrated to core.bills (migration 004). This script
now writes directly to core.bills via _upsert_proposicoes in votes_daily.py.

Usage:
    python -m camara.proposicoes_backfill
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from db import engine
from camara.votes_daily import _upsert_proposicoes

with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT id, external_id FROM core.votacoes WHERE vote_type = 'nominal' ORDER BY id")
    ).fetchall()

total = len(rows)
print(f"Backfilling bills for {total} nominal votacoes...")

for i, (vid, ext_id) in enumerate(rows, 1):
    if i % 50 == 0 or i == 1:
        with engine.connect() as c:
            nb = c.execute(text("SELECT COUNT(*) FROM core.bills WHERE source='camara'")).scalar()
            nv = c.execute(text("SELECT COUNT(*) FROM core.votacao_bills")).scalar()
            nts = c.execute(text("SELECT COUNT(*) FROM core.votacoes WHERE voted_at IS NOT NULL AND vote_type='nominal'")).scalar()
        print(f"  {i}/{total} | bills={nb} | links={nv} | voted_at fixed={nts}", flush=True)
    with engine.begin() as conn:
        _upsert_proposicoes(conn, vid, ext_id)

with engine.connect() as conn:
    nb = conn.execute(text("SELECT COUNT(*) FROM core.bills WHERE source='camara'")).scalar()
    nv = conn.execute(text("SELECT COUNT(*) FROM core.votacao_bills")).scalar()
    nts = conn.execute(text("SELECT COUNT(*) FROM core.votacoes WHERE voted_at IS NOT NULL AND vote_type='nominal'")).scalar()

print(f"Done! bills={nb} | links={nv} | voted_at fixed={nts}/{total}")
