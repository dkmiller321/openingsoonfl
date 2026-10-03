"""Send an email: into the outbox table (EMAIL_MODE=outbox) or through Resend (E8)."""

from __future__ import annotations

from typing import Any

import httpx

from osfl import clock
from osfl.db import session_scope
from osfl.models import OutboxEmail
from osfl.settings import get_settings

RESEND_URL = "https://api.resend.com/emails"


def send_email(
    to: list[str],
    subject: str,
    html: str,
    text: str,
    attachments: list[dict[str, Any]],
    mode: str | None = None,
) -> str:
    """Return an id: the outbox row id, or Resend's message id.

    `attachments` items are `{filename, content_type, content_b64}`.
    """
    settings = get_settings()
    mode = mode or settings.email_mode
    if mode == "resend":
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.email_from,
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
                "attachments": [
                    {"filename": a["filename"], "content": a["content_b64"]} for a in attachments
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        return str(response.json()["id"])
    with session_scope() as session:
        row = OutboxEmail(
            to=to, subject=subject, html=html, text=text, attachments=attachments,
            created_at=clock.now(),
        )
        session.add(row)
        session.flush()
        return str(row.id)
