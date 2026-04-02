"""
Weekly email digest service.

Queries activity for each user's followed politicians over the past 7 days,
builds a digest email, and sends via Resend.
"""

from datetime import datetime, timedelta

import resend

from app.config import settings

resend.api_key = settings.resend_api_key


def build_digest_html(user_name: str, items: list[dict], week_label: str) -> str:
    lines = [
        f"<h2>Sua semana no Congresso — {week_label}</h2>",
        f"<p>Olá, {user_name}! Veja o que aconteceu com os parlamentares que você acompanha.</p>",
        "<hr>",
    ]
    for politician_name, events in _group_by_politician(items):
        lines.append(f"<h3>{politician_name}</h3><ul>")
        for event in events[:3]:
            lines.append(f"<li>{event['text']}</li>")
        lines.append("</ul>")
    lines.append("<hr><p><a href='https://vizy.com.br/configuracoes'>Gerenciar inscrições</a></p>")
    return "\n".join(lines)


def send_digest(to_email: str, user_name: str, items: list[dict]) -> None:
    if not items:
        return
    week_label = _week_label()
    html = build_digest_html(user_name, items, week_label)
    resend.Emails.send({
        "from": settings.email_from,
        "to": to_email,
        "subject": f"Sua semana no Congresso — {week_label}",
        "html": html,
    })


def _week_label() -> str:
    today = datetime.today()
    start = today - timedelta(days=7)
    return f"{start.strftime('%d/%m')} a {today.strftime('%d/%m/%Y')}"


def _group_by_politician(items: list[dict]):
    seen = {}
    for item in items:
        name = item["politician_name"]
        seen.setdefault(name, []).append(item)
    return seen.items()
