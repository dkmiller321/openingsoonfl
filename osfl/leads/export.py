"""The lead sheet CSV (E4): one format for the web export, the CLI and digest attachments."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from osfl.models import Lead

CSV_COLUMNS = (
    "business_name", "address", "city", "zip", "county", "lead_type", "stage", "first_seen",
    "licensed_on", "days_ahead", "licensee", "phone", "email",
)


def display_name(lead: Lead) -> str:
    return lead.display_name or lead.business_name


def leads_csv(leads: Iterable[Lead]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for lead in leads:
        writer.writerow(
            [
                display_name(lead),
                lead.address,
                lead.city,
                lead.zip,
                lead.county.title(),
                lead.lead_type,
                lead.stage,
                lead.first_seen.isoformat(),
                lead.licensed_on.isoformat() if lead.licensed_on else "",
                "" if lead.days_ahead is None else str(lead.days_ahead),
                lead.licensee or "",
                lead.phone or "",
                lead.email or "",
            ]
        )
    return buf.getvalue()
