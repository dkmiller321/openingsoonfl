"""Apply parsed records to the database inside one transaction (I2, I3, L1-L4, L7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from osfl.leads.matcher import EventView, keys_for, summarise
from osfl.models import Lead, LeadEvent, LeadKey, RawRecord
from osfl.sources.dbpr import Record


@dataclass
class IngestResult:
    rows_new: int = 0
    created: set[int] = field(default_factory=set)
    touched: set[int] = field(default_factory=set)

    @property
    def leads_created(self) -> int:
        return len(self.created)

    @property
    def leads_updated(self) -> int:
        return len(self.touched - self.created)


def ingest(
    session: Session, records: list[Record], run_id: int, fetched_at: datetime, today: date
) -> IngestResult:
    result = IngestResult()
    for record in records:
        raw_id = session.execute(
            insert(RawRecord)
            .values(
                source=record.source,
                file=record.file,
                source_record_id=record.source_record_id,
                content_hash=record.content_hash,
                payload=record.payload,
                fetched_at=fetched_at,
                run_id=run_id,
            )
            .on_conflict_do_nothing(constraint="uq_raw_source_hash")
            .returning(RawRecord.id)
        ).scalar_one_or_none()
        if raw_id is None:
            continue  # seen before: idempotent re-run
        result.rows_new += 1
        if record.lead_type == "ignored":
            continue

        fields = record.fields()
        lead_id = _find_or_create_lead(session, fields, record, today, result)
        session.add(
            LeadEvent(
                lead_id=lead_id,
                raw_record_id=raw_id,
                source=record.source,
                stage=record.stage,
                event_date=record.event_date or today,
                fields=fields,
            )
        )
        session.flush()
        result.touched.add(lead_id)

    for lead_id in result.touched:
        recompute_lead(session, lead_id)
    return result


def _find_or_create_lead(
    session: Session, fields: dict, record: Record, today: date, result: IngestResult
) -> int:
    keys = keys_for(fields)
    rows = session.execute(select(LeadKey.key, LeadKey.lead_id).where(LeadKey.key.in_(keys)))
    found = {key: lead for key, lead in rows}
    lead_id = next((found[k] for k in keys if k in found), None)
    if lead_id is None:
        lead = Lead(
            lead_key=keys[-1].removeprefix("K:"),
            business_name=fields["business_name"],
            address=fields["address"],
            city=fields["city"],
            zip=fields["zip"],
            county=fields["county"],
            lead_type=fields["lead_type"],
            stage=record.stage,
            first_seen=record.event_date or today,
            hidden=False,
        )
        session.add(lead)
        session.flush()
        lead_id = lead.id
        result.created.add(lead_id)
    for key in keys:
        if key not in found:
            session.execute(
                insert(LeadKey).values(key=key, lead_id=lead_id).on_conflict_do_nothing()
            )
    return lead_id


def recompute_lead(session: Session, lead_id: int) -> None:
    lead = session.get(Lead, lead_id)
    assert lead is not None
    events = [
        EventView(stage=e.stage, event_date=e.event_date, order=e.raw_record_id, fields=e.fields)
        for e in session.scalars(select(LeadEvent).where(LeadEvent.lead_id == lead_id))
    ]
    before = (lead.address, lead.zip)
    for column, value in summarise(events).items():
        setattr(lead, column, value)
    if (lead.address, lead.zip) != before:
        lead.geo_status, lead.lat, lead.lng = None, None, None


def rebuild_leads(session: Session) -> int:
    """Re-parse every lead event's raw row with the current parser, then recompute its lead.

    For parser fixes (e.g. the swapped phone column): content hashes are unchanged, so a
    re-import alone would skip these rows.
    """
    from osfl.sources.dbpr import record_from_row

    touched: set[int] = set()
    rows = session.execute(
        select(LeadEvent, RawRecord).join(RawRecord, RawRecord.id == LeadEvent.raw_record_id)
    ).all()
    for event, raw in rows:
        record = record_from_row(raw.source, raw.file, raw.payload)
        event.fields = record.fields()
        touched.add(event.lead_id)
    session.flush()
    for lead_id in touched:
        recompute_lead(session, lead_id)
    return len(touched)
