"""Test-only routes (E2E_TESTS.md section 1.3). Mounted only when TEST_ROUTES=1."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text

from osfl import clock
from osfl.db import DbSession, session_scope
from osfl.models import (
    ALL_TABLES,
    Delivery,
    Digest,
    Lead,
    LeadEvent,
    OutboxEmail,
    RawRecord,
    SourceRun,
    Vendor,
)
from osfl.seed import ensure_categories

router = APIRouter(prefix="/test")


class ClockBody(BaseModel):
    now: datetime | None


class RunBody(BaseModel):
    fixture: str | None = None


@router.post("/reset")
def reset() -> dict[str, bool]:
    with session_scope() as session:
        tables = ", ".join(f'"{t}"' for t in ALL_TABLES)
        session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        ensure_categories(session)
    clock.reset()
    return {"ok": True}


@router.post("/clock")
def set_clock(body: ClockBody) -> dict[str, str | None]:
    clock.freeze(body.now)
    return {"now": clock.now().isoformat() if body.now is not None else None}


@router.post("/run/{job}")
def run(job: str, body: RunBody | None = None) -> dict[str, Any]:
    from osfl.jobs import JOBS, run_job

    if job not in JOBS:
        raise HTTPException(404, f"unknown job {job!r}")
    return run_job(job, fixture=body.fixture if body else None, trigger="test")


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("/leads")
def leads(session: DbSession) -> list[dict[str, Any]]:
    out = []
    for lead in session.scalars(select(Lead).order_by(Lead.business_name, Lead.id)):
        events = session.scalars(
            select(LeadEvent)
            .where(LeadEvent.lead_id == lead.id)
            .order_by(LeadEvent.event_date, LeadEvent.raw_record_id)
        )
        out.append(
            {
                "id": lead.id,
                "business_name": lead.display_name or lead.business_name,
                "address": lead.address,
                "city": lead.city,
                "zip": lead.zip,
                "county": lead.county.title(),
                "lead_type": lead.lead_type,
                "stage": lead.stage,
                "first_seen": _iso(lead.first_seen),
                "licensed_on": _iso(lead.licensed_on),
                "days_ahead": lead.days_ahead,
                "licensee": lead.licensee,
                "phone": lead.phone or "",
                "email": lead.email or "",
                "hidden": lead.hidden,
                "lat": lead.lat,
                "lng": lead.lng,
                "geo_status": lead.geo_status,
                "note": lead.note,
                "events": [
                    {"stage": e.stage, "date": _iso(e.event_date), "source": e.source}
                    for e in events
                ],
            }
        )
    return out


@router.get("/state")
def state(session: DbSession) -> dict[str, int]:
    def count(model: type) -> int:
        return session.scalar(select(func.count()).select_from(model)) or 0

    return {
        "leads": count(Lead),
        "raw_records": count(RawRecord),
        "source_runs": count(SourceRun),
        "outbox": count(OutboxEmail),
        "deliveries": count(Delivery),
        "digests": count(Digest),
    }


@router.get("/outbox")
def outbox(session: DbSession) -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "to": m.to,
            "subject": m.subject,
            "html": m.html,
            "text": m.text,
            "attachments": m.attachments,
            "created_at": _iso(m.created_at),
        }
        for m in session.scalars(select(OutboxEmail).order_by(OutboxEmail.id))
    ]


@router.get("/deliveries")
def deliveries(session: DbSession) -> list[dict[str, Any]]:
    rows = session.execute(
        select(Vendor.name, Lead, Delivery.delivered_at)
        .join(Vendor, Vendor.id == Delivery.vendor_id)
        .join(Lead, Lead.id == Delivery.lead_id)
        .order_by(Delivery.id)
    )
    return [
        {
            "vendor_name": vendor_name,
            "business_name": lead.display_name or lead.business_name,
            "delivered_on": delivered_at.astimezone(clock.ET).date().isoformat(),
        }
        for vendor_name, lead, delivered_at in rows
    ]


@router.get("/runs")
def runs(session: DbSession) -> list[dict[str, Any]]:
    return [
        {
            "id": r.id,
            "source": r.source,
            "trigger": r.trigger,
            "status": r.status,
            "rows_fetched": r.rows_fetched,
            "rows_new": r.rows_new,
            "problem": r.problem,
            "error": r.error,
        }
        for r in session.scalars(select(SourceRun).order_by(SourceRun.id.desc()))
    ]


@router.get("/schedule")
def schedule() -> list[dict[str, str]]:
    from osfl.scheduler import next_runs

    return [{"job": job, "next_run": when} for job, when in next_runs(clock.now())]
