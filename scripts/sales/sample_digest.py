"""Sales-kit teaser: this week's real digest with owner contacts masked.
   uv run python scripts/sales/sample_digest.py [--days 14]
   -> exports/sales/sample-digest.html + sample-digest.png"""

from __future__ import annotations

import argparse
import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright
from sqlalchemy import select

from osfl import clock
from osfl.db import session_scope
from osfl.digests.builder import render_digest
from osfl.models import Lead

OUT = Path(__file__).resolve().parents[2] / "exports" / "sales"


def mask_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return f"{digits[:3]}-•••-••{digits[-2:]}" if len(digits) >= 10 else ""


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    user, domain = email.split("@", 1)
    return f"{user[0]}•••••@{domain}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()
    since = clock.today_et() - timedelta(days=args.days)
    with session_scope() as session:
        leads = [
            SimpleNamespace(
                display_name=lead.display_name, business_name=lead.business_name,
                lead_type=lead.lead_type, stage=lead.stage, licensed_on=lead.licensed_on,
                first_seen=lead.first_seen, days_ahead=lead.days_ahead, address=lead.address,
                city=lead.city, zip=lead.zip, county=lead.county, licensee=lead.licensee,
                phone=mask_phone(lead.phone), email=mask_email(lead.email),
            )
            for lead in session.scalars(
                select(Lead)
                .where(Lead.county == "brevard", Lead.hidden.is_(False), Lead.first_seen >= since)
                .order_by(Lead.first_seen.desc(), Lead.business_name)
            )
        ]
    vendor = SimpleNamespace(name="Your Company", counties=["brevard"], unsubscribe_token="sample")
    email = render_digest(vendor, leads, clock.now(), "weekly")
    html = email.html.replace(
        "New restaurants for Your Company",
        "Sample: this week's new Brevard restaurants (contacts masked)",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    html_path = OUT / "sample-digest.html"
    html_path.write_text(html, encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 720, "height": 900}, device_scale_factor=2)
        page.goto(html_path.as_uri())
        page.screenshot(path=str(OUT / "sample-digest.png"), full_page=True)
        browser.close()
    print(f"sample digest: {len(leads)} leads since {since} -> {html_path} (+ .png)")
    print(f"subject: {email.subject}")


if __name__ == "__main__":
    main()
