"""Map view (M2-M5) and pipeline board (M6)."""

from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from osfl import clock
from osfl.db import DbSession
from osfl.formatting import days_ahead_label, lead_type_label, long_date
from osfl.geo import BREVARD_CENTER, TOWNS
from osfl.leads.cuisine import cuisine_icon, guess_cuisine
from osfl.leads.export import display_name
from osfl.leads.queries import LEAD_TYPE_FILTERS, lead_query
from osfl.models import Lead
from osfl.settings import SUPPORTED_COUNTIES, get_settings
from osfl.web.basemap import ATTRIBUTION as MAPBOX_ATTRIBUTION
from osfl.web.basemap import basemaps
from osfl.web.common import render, require_login
from osfl.web.leads import _filter_from

router = APIRouter(dependencies=[Depends(require_login)])


def lead_view(lead: Lead) -> dict:
    name = display_name(lead)
    cuisine = guess_cuisine(name)
    return {
        "id": lead.id,
        "name": name,
        "lat": lead.lat,
        "lng": lead.lng,
        "stage": lead.stage,
        "lead_type": lead.lead_type,
        "type_label": lead_type_label(lead.lead_type),
        "cuisine": cuisine or "",
        "icon": cuisine_icon(cuisine, lead.lead_type),
        "first_seen": lead.first_seen.isoformat(),
        "first_seen_label": long_date(lead.first_seen),
        "days_ahead": lead.days_ahead,
        "days_ahead_label": days_ahead_label(lead.days_ahead),
        "licensed_on": lead.licensed_on.isoformat() if lead.licensed_on else None,
        "address": lead.address,
        "city": lead.city,
        "phone": lead.phone or "",
        "email": lead.email or "",
    }


@router.get("/map/data.json")
def map_data(request: Request, session: DbSession) -> JSONResponse:
    rows = list(session.scalars(lead_query(_filter_from(request))))
    placed = [lead_view(r) for r in rows if r.lat is not None and r.lng is not None]
    unplaced = [
        {"id": r.id, "stage": r.stage, "lead_type": r.lead_type,
         "first_seen": r.first_seen.isoformat()}
        for r in rows if r.lat is None or r.lng is None
    ]
    return JSONResponse(
        {"leads": placed, "unplaced": len(unplaced), "unplaced_leads": unplaced}
    )


@router.get("/map")
def map_page(request: Request, session: DbSession):
    settings = get_settings()
    pending = session.scalar(
        select(func.count()).select_from(Lead).where(Lead.geo_status.is_(None))
    )
    return render(
        request, "map.html", active="map",
        today=clock.today_et().isoformat(),
        towns=TOWNS, center=BREVARD_CENTER,
        tile_url=settings.map_tile_url, tile_attribution=settings.map_tile_attribution,
        basemaps=basemaps(settings.mapbox_token), mapbox_attribution=MAPBOX_ATTRIBUTION,
        pending=pending,
    )


@router.get("/board")
def board_page(request: Request, session: DbSession):
    f = _filter_from(request)
    if f.since is None and "from" not in request.query_params:
        f.since = clock.today_et() - timedelta(days=180)
    f.stage = "All"
    rows = [lead_view(r) for r in session.scalars(lead_query(f))]
    applied = [r for r in rows if r["stage"] == "Applied"]
    licensed = [r for r in rows if r["stage"] == "Licensed"]
    return render(
        request, "board.html", active="board", applied=applied, licensed=licensed, f=f,
        type_options=("All", *LEAD_TYPE_FILTERS), county_options=SUPPORTED_COUNTIES,
        query=urlencode(dict(request.query_params)),
    )
