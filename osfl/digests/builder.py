"""Build and send vendor digests (E1-E8). A lead reaches a vendor at most once (E3)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from osfl import clock
from osfl.db import session_scope
from osfl.digests.period import digest_period, week_start
from osfl.digests.sender import send_email
from osfl.formatting import lead_type_label, long_date, plural
from osfl.leads.export import display_name, leads_csv
from osfl.models import Delivery, Digest, Lead, Vendor
from osfl.settings import get_settings

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass
class DigestEmail:
    subject: str
    html: str
    text: str
    attachments: list[dict[str, Any]]


def counties_label(counties: list[str]) -> str:
    names = [c.title() for c in counties]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def pending_leads(session: Session, vendor: Vendor) -> list[Lead]:
    delivered = select(Delivery.lead_id).where(Delivery.vendor_id == vendor.id)
    return list(
        session.scalars(
            select(Lead)
            .where(
                Lead.county.in_(vendor.counties),
                Lead.hidden.is_(False),
                Lead.id.not_in(delivered),
            )
            .order_by(Lead.first_seen.desc(), Lead.business_name, Lead.id)
        )
    )


def stage_label(lead: Lead) -> str:
    if lead.stage == "Licensed":
        return f"Licensed {long_date(lead.licensed_on)}"
    return "Application in progress"


def render_digest(vendor: Vendor, leads: list[Lead], now: datetime, cadence: str) -> DigestEmail:
    settings = get_settings()
    today = now.astimezone(clock.ET).date()
    when = f"week of {long_date(week_start(now))}" if cadence == "weekly" else long_date(today)
    where = counties_label(vendor.counties)
    subject = f"{plural(len(leads), 'new restaurant')} in {where} - {when}"
    items = [
        {
            "name": display_name(lead),
            "type": lead_type_label(lead.lead_type),
            "stage": stage_label(lead),
            "address": f"{lead.address}, {lead.city}, FL {lead.zip}",
            "phone": lead.phone,
            "email": lead.email,
            "first_seen": long_date(lead.first_seen),
        }
        for lead in leads
    ]
    context = {
        "vendor": vendor,
        "leads": items,
        "empty_line": "No new restaurants this week" if cadence == "weekly"
        else "No new restaurants today",
        "when": when,
        "counties": counties_label(vendor.counties),
        "unsubscribe_url": f"{settings.app_base_url.rstrip('/')}/unsubscribe/"
        f"{vendor.unsubscribe_token}",
        "postal_address": settings.operator_postal_address,
    }
    csv_text = leads_csv(leads)
    attachment = {
        "filename": f"leads-{today.isoformat()}.csv",
        "content_type": "text/csv",
        "content_b64": base64.b64encode(csv_text.encode("utf-8")).decode("ascii"),
    }
    return DigestEmail(
        subject=subject,
        html=_env.get_template("digest.html").render(**context),
        text=_env.get_template("digest.txt").render(**context),
        attachments=[attachment],
    )


def preview(session: Session, vendor: Vendor) -> DigestEmail:
    return render_digest(vendor, pending_leads(session, vendor), clock.now(), vendor.cadence)


def send_test(session: Session, vendor: Vendor) -> str:
    """E5: the vendor's next digest, to the operator, marked [TEST]; marks nothing delivered."""
    settings = get_settings()
    email = preview(session, vendor)
    email_id = send_email(
        [settings.operator_email], f"[TEST] {email.subject}", email.html, email.text,
        email.attachments,
    )
    session.add(Digest(vendor_id=vendor.id, kind="test", period_key=None, sent_at=clock.now(),
                       lead_count=0, email_id=email_id))
    return settings.operator_email


def send_scheduled_digests(cadence: str) -> dict[str, int]:
    """Send each active vendor of this cadence its digest for the current period, once."""
    now = clock.now()
    period = digest_period(now, cadence)
    with session_scope() as session:
        vendor_ids = list(
            session.scalars(
                select(Vendor.id)
                .where(Vendor.active.is_(True), Vendor.cadence == cadence)
                .order_by(Vendor.id)
            )
        )
    sent = 0
    for vendor_id in vendor_ids:
        if _send_one(vendor_id, cadence, period, now):
            sent += 1
    return {"emails_sent": sent}


def _send_one(vendor_id: int, cadence: str, period: str, now: datetime) -> bool:
    with session_scope() as session:
        already = session.scalar(
            select(Digest.id).where(
                Digest.vendor_id == vendor_id, Digest.kind == "scheduled",
                Digest.period_key == period,
            )
        )
        if already:
            return False
        vendor = session.get(Vendor, vendor_id)
        assert vendor is not None
        leads = pending_leads(session, vendor)
        digest = Digest(vendor_id=vendor.id, kind="scheduled", period_key=period, sent_at=now,
                        lead_count=len(leads))
        session.add(digest)
        session.flush()  # the unique (vendor, period) index stops a concurrent duplicate here
        for lead in leads:
            session.add(Delivery(vendor_id=vendor.id, lead_id=lead.id, digest_id=digest.id,
                                 delivered_at=now))
        session.flush()
        email = render_digest(vendor, leads, now, cadence)
        digest.email_id = send_email(vendor.emails, email.subject, email.html, email.text,
                                     email.attachments)
    return True
