"""Pure rules for turning a lead's events into its current state (PRD L2-L4, L7)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from osfl.leads.normalise import lead_key

STAGE_ORDER = {"Applied": 1, "Licensed": 2}


@dataclass
class EventView:
    """One event, ordered by (event_date, raw_record_id)."""

    stage: str
    event_date: date
    order: int
    fields: dict[str, Any]


def keys_for(fields: dict[str, Any]) -> list[str]:
    """Identities to look a record up by: licence digits first, then name|address|zip."""
    keys = []
    if fields.get("licence_number"):
        keys.append(f"LIC:{fields['licence_number']}")
    keys.append("K:" + lead_key(fields["business_name"], fields["address"], fields["zip"]))
    return keys


def days_ahead(events: Sequence[tuple[str, date]]) -> int | None:
    """Licence date minus the earliest event date; None until licensed."""
    if not events:
        return None
    licensed = [d for stage, d in events if stage == "Licensed"]
    if not licensed:
        return None
    return (min(licensed) - min(d for _, d in events)).days


def summarise(events: Sequence[EventView]) -> dict[str, Any]:
    """The lead's columns, from all of its events.

    Stage = most advanced; first_seen = earliest event; text fields = most recent non-empty.
    """
    ordered = sorted(events, key=lambda e: (e.event_date, e.order))
    latest = ordered[-1].fields

    def newest(name: str) -> str | None:
        for event in reversed(ordered):
            value = event.fields.get(name)
            if value:
                return value
        return None

    licensed = [e.event_date for e in ordered if e.stage == "Licensed"]
    first_seen = min(e.event_date for e in ordered)
    return {
        "business_name": newest("business_name") or "",
        "address": latest.get("address") or newest("address") or "",
        "city": latest.get("city") or newest("city") or "",
        "zip": latest.get("zip") or newest("zip") or "",
        "county": latest.get("county") or newest("county") or "",
        "licensee": newest("licensee"),
        "phone": newest("phone"),
        "email": newest("email"),
        "licence_number": newest("licence_number"),
        "lead_type": latest.get("lead_type") or "new",
        "stage": max((e.stage for e in ordered), key=lambda s: STAGE_ORDER.get(s, 0)),
        "first_seen": first_seen,
        "licensed_on": min(licensed) if licensed else None,
        "days_ahead": days_ahead([(e.stage, e.event_date) for e in ordered]),
    }
