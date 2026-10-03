"""Lead list queries shared by the admin pages, the CSV exports and the digests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, or_, select

from osfl.models import Lead

LEAD_TYPE_FILTERS = {"New": "new", "Ownership change": "ownership_change", "Food truck": "mobile"}


@dataclass
class LeadFilter:
    stage: str = "All"
    lead_type: str = "All"
    county: str = "All"
    since: date | None = None
    until: date | None = None
    q: str = ""
    include_hidden: bool = False


def lead_query(f: LeadFilter) -> Select[tuple[Lead]]:
    query = select(Lead)
    if f.stage in ("Applied", "Licensed"):
        query = query.where(Lead.stage == f.stage)
    if f.lead_type in LEAD_TYPE_FILTERS:
        query = query.where(Lead.lead_type == LEAD_TYPE_FILTERS[f.lead_type])
    if f.county and f.county != "All":
        query = query.where(Lead.county == f.county.lower())
    if f.since:
        query = query.where(Lead.first_seen >= f.since)
    if f.until:
        query = query.where(Lead.first_seen <= f.until)
    if f.q.strip():
        like = f"%{f.q.strip()}%"
        query = query.where(
            or_(
                Lead.business_name.ilike(like),
                Lead.display_name.ilike(like),
                Lead.address.ilike(like),
                Lead.city.ilike(like),
            )
        )
    if not f.include_hidden:
        query = query.where(Lead.hidden.is_(False))
    return query.order_by(Lead.first_seen.desc(), func.coalesce(Lead.display_name,
                                                                 Lead.business_name), Lead.id)
