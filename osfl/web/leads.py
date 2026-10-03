"""Dashboard, leads table, lead detail and CSV export (A2-A4, L5, E4)."""

from datetime import date, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from osfl import clock
from osfl.db import DbSession
from osfl.health import SOURCE_LABELS, SOURCES, recent_runs, statuses
from osfl.leads.export import display_name, leads_csv
from osfl.leads.queries import LEAD_TYPE_FILTERS, LeadFilter, lead_query
from osfl.models import Lead, LeadEvent, RawRecord, Vendor
from osfl.settings import SUPPORTED_COUNTIES
from osfl.sources.dbpr import expected_header
from osfl.web.common import render, require_login

router = APIRouter(dependencies=[Depends(require_login)])


@router.get("/")
def dashboard(request: Request, session: DbSession):
    week_ago = clock.today_et() - timedelta(days=7)
    visible = Lead.hidden.is_(False)
    new_this_week = session.scalar(
        select(func.count()).select_from(Lead).where(visible, Lead.first_seen > week_ago)
    )
    applied = session.scalar(
        select(func.count()).select_from(Lead).where(visible, Lead.stage == "Applied")
    )
    active_vendors = session.scalar(
        select(func.count()).select_from(Vendor).where(Vendor.active.is_(True))
    )
    current = statuses(session)
    sources = []
    for source in SOURCES:
        runs = recent_runs(session, source, limit=1)
        sources.append(
            {"key": source, "label": SOURCE_LABELS[source], "status": current[source],
             "last": runs[0] if runs else None}
        )
    return render(
        request, "dashboard.html", active="dashboard", new_this_week=new_this_week,
        applied=applied, active_vendors=active_vendors, sources=sources,
    )


def _filter_from(request: Request) -> LeadFilter:
    p = request.query_params

    def parse_date(value: str | None) -> date | None:
        try:
            return date.fromisoformat(value) if value else None
        except ValueError:
            return None

    return LeadFilter(
        stage=p.get("stage", "All"),
        lead_type=p.get("type", "All"),
        county=p.get("county", "All"),
        since=parse_date(p.get("from")),
        until=parse_date(p.get("to")),
        q=p.get("q", ""),
        include_hidden=p.get("hidden") == "1",
    )


@router.get("/leads")
def leads_page(request: Request, session: DbSession):
    f = _filter_from(request)
    rows = list(session.scalars(lead_query(f)))
    return render(
        request, "leads.html", active="leads", leads=rows, f=f,
        stage_options=("All", "Applied", "Licensed"),
        type_options=("All", *LEAD_TYPE_FILTERS),
        county_options=SUPPORTED_COUNTIES,
        export_query=urlencode({k: v for k, v in request.query_params.items()}),
        display_name=display_name,
    )


@router.get("/leads.csv")
def leads_export(request: Request, session: DbSession) -> Response:
    rows = list(session.scalars(lead_query(_filter_from(request))))
    filename = f"leads-{clock.today_et().isoformat()}.csv"
    return Response(
        leads_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: int, request: Request, session: DbSession):
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    events = session.execute(
        select(LeadEvent, RawRecord)
        .join(RawRecord, RawRecord.id == LeadEvent.raw_record_id)
        .where(LeadEvent.lead_id == lead_id)
        .order_by(LeadEvent.event_date, LeadEvent.raw_record_id)
    ).all()
    records = [
        (event, raw, [(col, raw.payload.get(col, "")) for col in expected_header(raw.file)])
        for event, raw in events
    ]
    return render(
        request, "lead_detail.html", active="leads", lead=lead, events=records,
        name=display_name(lead),
    )


@router.post("/leads/{lead_id}")
def lead_save(
    lead_id: int,
    session: DbSession,
    display: str = Form("", alias="display_name"),
    note: str = Form(""),
):
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    display = display.strip()
    lead.display_name = display if display and display != lead.business_name else None
    lead.note = note.strip() or None
    return RedirectResponse(f"/leads/{lead_id}", status_code=303)


@router.post("/leads/{lead_id}/hide")
def lead_hide(lead_id: int, session: DbSession):
    return _set_hidden(session, lead_id, True)


@router.post("/leads/{lead_id}/unhide")
def lead_unhide(lead_id: int, session: DbSession):
    return _set_hidden(session, lead_id, False)


def _set_hidden(session: Session, lead_id: int, hidden: bool) -> RedirectResponse:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    lead.hidden = hidden
    return RedirectResponse(f"/leads/{lead_id}", status_code=303)
