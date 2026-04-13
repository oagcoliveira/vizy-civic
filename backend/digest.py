"""
Weekly email digest: sends a summary of the past 7 days of activity
for each user's followed politicians.

For each user with >0 followed politicians and digest_frequency = 'weekly':
  1. Find their followed politicians
  2. Fetch last 7 days of votes + speeches for those politicians
  3. Build an HTML email (max 5 politicians × 3 items each)
  4. Send via Resend API

Usage (from backend/):
    python digest.py            # dry run — print emails, don't send
    python digest.py --send     # send emails for real
    python digest.py --user 5   # only send for user ID 5 (testing)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv(override=True)

import httpx
from sqlalchemy import create_engine, text

from app.config import settings

engine = create_engine(settings.database_url)

RESEND_API_URL = "https://api.resend.com/emails"
MAX_POLITICIANS = 5
MAX_ITEMS_PER_POLITICIAN = 3
DAYS_LOOKBACK = 7


def fetch_users_for_digest(conn, user_id: Optional[int] = None) -> list[dict]:
    """Fetch users who should receive a weekly digest."""
    sql = """
        SELECT DISTINCT u.id, u.email, u.name
        FROM auth.users u
        JOIN auth.politician_follows pf ON pf.user_id = u.id
        WHERE (u.digest_frequency = 'weekly' OR u.digest_frequency IS NULL)
    """
    params: dict = {}
    if user_id:
        sql += " AND u.id = :uid"
        params["uid"] = user_id
    sql += " ORDER BY u.id"
    rows = conn.execute(text(sql), params).fetchall()
    return [dict(r._mapping) for r in rows]


def fetch_followed_politicians(conn, user_id: int) -> list[dict]:
    """Fetch politicians followed by a user with their party/state info."""
    rows = conn.execute(text("""
        SELECT pf.politician_id, p.short_name, p.state, pa.acronym AS party, p.photo_url
        FROM auth.politician_follows pf
        JOIN core.politicians p ON p.id = pf.politician_id
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE pf.user_id = :uid
        ORDER BY p.short_name
        LIMIT :limit
    """), {"uid": user_id, "limit": MAX_POLITICIANS}).fetchall()
    return [dict(r._mapping) for r in rows]


def fetch_recent_activity(conn, politician_id: int, since: datetime) -> list[dict]:
    """Fetch up to MAX_ITEMS votes + speeches for a politician in the past N days."""
    rows = conn.execute(text("""
        SELECT 'vote' AS event_type, v.voted_at AS occurred_at,
               COALESCE(b.short_title, b.ementa, b.title) AS title,
               iv.vote AS detail,
               v.id AS ref_id
        FROM core.individual_votes iv
        JOIN core.votacoes v ON v.id = iv.votacao_id
        LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
        LEFT JOIN core.bills b ON b.id = vb.bill_id
        WHERE iv.politician_id = :pid AND v.voted_at >= :since

        UNION ALL

        SELECT 'speech' AS event_type, s.delivered_at AS occurred_at,
               s.summary AS title,
               s.phase AS detail,
               s.id AS ref_id
        FROM core.speeches s
        WHERE s.politician_id = :pid AND s.delivered_at >= :since

        ORDER BY occurred_at DESC
        LIMIT :limit
    """), {"pid": politician_id, "since": since, "limit": MAX_ITEMS_PER_POLITICIAN}).fetchall()
    return [dict(r._mapping) for r in rows]


def build_html_email(user_name: str, politicians_activity: list[dict]) -> str:
    """Build a plain but readable HTML email for the digest."""
    name_first = user_name.split()[0] if user_name else "Olá"
    sections = []

    for pol in politicians_activity:
        pol_name = pol["short_name"]
        party_state = f"{pol['party']}-{pol['state']}" if pol.get("party") and pol.get("state") else ""
        items_html = ""
        for item in pol["activity"]:
            label = "Votou" if item["event_type"] == "vote" else "Discursou"
            detail = item.get("detail") or ""
            title = item.get("title") or ""
            date_str = ""
            if item.get("occurred_at"):
                try:
                    date_str = item["occurred_at"].strftime("%d/%m/%Y") if hasattr(item["occurred_at"], "strftime") else str(item["occurred_at"])[:10]
                except Exception:
                    date_str = str(item["occurred_at"])[:10]

            if item["event_type"] == "vote":
                items_html += f"""
                <li style="margin-bottom:8px;">
                  <span style="font-weight:600;color:#4f46e5;">{label} {detail}</span>
                  {f'<span style="color:#6b7280;"> — {title}</span>' if title else ""}
                  <span style="color:#9ca3af;font-size:12px;"> · {date_str}</span>
                </li>"""
            else:
                items_html += f"""
                <li style="margin-bottom:8px;">
                  <span style="font-weight:600;color:#059669;">{label}</span>
                  {f'<span style="color:#6b7280;"> — {title or detail}</span>' if (title or detail) else ""}
                  <span style="color:#9ca3af;font-size:12px;"> · {date_str}</span>
                </li>"""

        sections.append(f"""
        <div style="margin-bottom:24px;padding:16px;border:1px solid #e5e7eb;border-radius:8px;">
          <p style="margin:0 0 8px 0;font-weight:700;font-size:15px;">{pol_name}
            {f'<span style="font-weight:400;color:#6b7280;font-size:13px;"> · {party_state}</span>' if party_state else ""}
          </p>
          <ul style="margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.6;">
            {items_html or '<li style="color:#9ca3af;">Nenhuma atividade registrada esta semana.</li>'}
          </ul>
        </div>""")

    sections_html = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8" /><title>Resumo semanal — Vizy</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:32px 16px;">
    <div style="margin-bottom:24px;">
      <a href="https://vizy.com.br" style="font-weight:800;font-size:22px;color:#4f46e5;text-decoration:none;">Vizy</a>
    </div>
    <h1 style="font-size:20px;font-weight:700;color:#111827;margin:0 0 4px 0;">Seu resumo semanal</h1>
    <p style="color:#6b7280;font-size:14px;margin:0 0 24px 0;">Olá, {name_first}! Aqui está o que aconteceu com os deputados que você acompanha nos últimos 7 dias.</p>
    {sections_html}
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;" />
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin:0;">
      Você recebe este e-mail porque segue deputados no <a href="https://vizy.com.br" style="color:#4f46e5;">Vizy</a>.
    </p>
  </div>
</body>
</html>"""


def send_email(to_email: str, subject: str, html: str, dry_run: bool = True) -> bool:
    """Send email via Resend API. Returns True on success."""
    if dry_run:
        print(f"  [DRY RUN] Would send to {to_email}: {subject}")
        return True

    if not settings.resend_api_key:
        print(f"  ERROR: RESEND_API_KEY not set — cannot send email to {to_email}", file=sys.stderr)
        return False

    try:
        resp = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.email_from,
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return True
        else:
            print(f"  ERROR: Resend returned {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  ERROR: Failed to send to {to_email}: {e}", file=sys.stderr)
        return False


def run(send: bool = False, user_id: Optional[int] = None):
    since = datetime.now(timezone.utc) - timedelta(days=DAYS_LOOKBACK)
    dry_run = not send

    print(f"Weekly digest {'(DRY RUN)' if dry_run else '(SENDING)'} — activity since {since.date()}")

    with engine.connect() as conn:
        users = fetch_users_for_digest(conn, user_id=user_id)

    print(f"Found {len(users)} user(s) to notify.")
    sent = failed = 0

    for user in users:
        print(f"\nUser {user['id']} ({user['email']}):")
        with engine.connect() as conn:
            politicians = fetch_followed_politicians(conn, user["id"])

        if not politicians:
            print("  No followed politicians — skipping.")
            continue

        politicians_activity = []
        for pol in politicians:
            with engine.connect() as conn:
                activity = fetch_recent_activity(conn, pol["politician_id"], since)
            politicians_activity.append({**pol, "activity": activity})
            print(f"  {pol['short_name']}: {len(activity)} event(s)")

        html = build_html_email(user["name"], politicians_activity)
        subject = "Seu resumo semanal no Vizy"

        ok = send_email(user["email"], subject, html, dry_run=dry_run)
        if ok:
            sent += 1
        else:
            failed += 1

    print(f"\nDone — {sent} sent, {failed} failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Actually send emails (default: dry run)")
    parser.add_argument("--user", type=int, default=None, help="Only send for this user ID")
    args = parser.parse_args()
    run(send=args.send, user_id=args.user)
