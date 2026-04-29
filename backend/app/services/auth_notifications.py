"""Admin notifications for authentication events.

This module sends best-effort email alerts for notable authentication events.
Failures are logged and intentionally do not block user signup or login.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import logging
from typing import Literal

import resend

from app.config import settings

logger = logging.getLogger(__name__)

AuthEventType = Literal["signup", "login"]


def send_auth_alert(
    *,
    event_type: AuthEventType,
    user_email: str,
    user_name: str | None = None,
    user_id: int | None = None,
) -> None:
    """Send an admin email alert for a successful auth event.

    The function is deliberately best-effort. Missing configuration or Resend
    delivery failures are logged and never raised to the caller, so a temporary
    email provider issue cannot prevent users from signing up or logging in.
    """
    if event_type == "signup" and not settings.auth_alert_signup_enabled:
        return
    if event_type == "login" and not settings.auth_alert_login_enabled:
        return
    if not settings.resend_api_key:
        logger.info("Skipping auth alert because RESEND_API_KEY is not configured")
        return
    if not settings.auth_alert_email:
        logger.info("Skipping auth alert because AUTH_ALERT_EMAIL is not configured")
        return

    resend.api_key = settings.resend_api_key

    event_label = "New user signup" if event_type == "signup" else "User login"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sender = settings.auth_alert_from or settings.email_from

    safe_email = escape(user_email)
    safe_name = escape(user_name or "Unknown")
    safe_user_id = escape(str(user_id or "Unknown"))
    safe_timestamp = escape(timestamp)

    html = f"""
    <h2>{event_label}</h2>
    <table cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
      <tr><td><strong>User ID</strong></td><td>{safe_user_id}</td></tr>
      <tr><td><strong>Email</strong></td><td>{safe_email}</td></tr>
      <tr><td><strong>Name</strong></td><td>{safe_name}</td></tr>
      <tr><td><strong>Time (UTC)</strong></td><td>{safe_timestamp}</td></tr>
    </table>
    """

    try:
        resend.Emails.send(
            {
                "from": sender,
                "to": settings.auth_alert_email,
                "subject": f"Vizy alert: {event_label} — {user_email}",
                "html": html,
            }
        )
    except Exception:
        logger.exception("Failed to send %s auth alert for user_id=%s", event_type, user_id)
