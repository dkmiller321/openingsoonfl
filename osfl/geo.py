"""Geocoding (M1) and map geography (M5).

Live mode uses the US Census batch geocoder (free, no key, public-domain results): one POST of
up to 10,000 addresses. Fixture mode reads fixtures/geocode.json, keyed by
`normalise_address(address)|zip`.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Protocol

import httpx
from sqlalchemy import select

from osfl.db import session_scope
from osfl.leads.normalise import normalise_address, normalise_zip
from osfl.models import Lead
from osfl.settings import get_settings

log = logging.getLogger("osfl.geo")

# Town centres for the radius filter (lat, lng).
TOWNS: dict[str, tuple[float, float]] = {
    "Cocoa": (28.3861, -80.7420),
    "Cocoa Beach": (28.3200, -80.6076),
    "Melbourne": (28.0836, -80.6081),
    "Merritt Island": (28.3584, -80.6823),
    "Palm Bay": (28.0345, -80.5887),
    "Rockledge": (28.3508, -80.7253),
    "Titusville": (28.6122, -80.8076),
    "Viera": (28.2489, -80.7334),
}
BREVARD_CENTER = (28.26, -80.72)

Address = tuple[int, str, str, str]  # lead id, street, city, zip


class Geocoder(Protocol):
    def geocode(self, addresses: list[Address]) -> dict[int, tuple[float, float] | None]: ...


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 3958.8 * 2 * asin(sqrt(h))


_UNIT = re.compile(r"\s(?:STE|SUITE|UNIT|BLDG|BUILDING|APT|LOT|SPACE|VIN)\b.*$|\s*#.*$",
                   re.IGNORECASE)


def strip_unit(street: str) -> str:
    """`4590 BABCOCK ST NE STE 105, VIN# 3930` -> `4590 BABCOCK ST NE` (second-pass retry)."""
    return " ".join(_UNIT.sub("", street.split(",")[0]).split())


def address_key(street: str, zip_code: str) -> str:
    return f"{normalise_address(street)}|{normalise_zip(zip_code)}"


class FixtureGeocoder:
    def __init__(self, path: Path) -> None:
        self.table: dict[str, list[float]] = json.loads(path.read_text("utf-8"))

    def geocode(self, addresses: list[Address]) -> dict[int, tuple[float, float] | None]:
        out: dict[int, tuple[float, float] | None] = {}
        for lead_id, street, _city, zip_code in addresses:
            hit = self.table.get(address_key(street, zip_code))
            out[lead_id] = (hit[0], hit[1]) if hit else None
        return out


class CensusGeocoder:
    def __init__(self, url: str, user_agent: str, transport: httpx.BaseTransport | None = None):
        self.url = url
        self.client = httpx.Client(
            headers={"User-Agent": user_agent}, timeout=300, transport=transport
        )

    def geocode(self, addresses: list[Address]) -> dict[int, tuple[float, float] | None]:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        for lead_id, street, city, zip_code in addresses:
            writer.writerow([lead_id, street, city, "FL", normalise_zip(zip_code)])
        response = self.client.post(
            self.url,
            data={"benchmark": "Public_AR_Current"},
            files={"addressFile": ("addresses.csv", buf.getvalue().encode(), "text/csv")},
        )
        response.raise_for_status()
        return parse_census_response(response.text)


def parse_census_response(text: str) -> dict[int, tuple[float, float] | None]:
    """Rows: id, input, Match|No_Match|Tie, Exact|Non_Exact, matched address, "lon,lat", ..."""
    out: dict[int, tuple[float, float] | None] = {}
    for row in csv.reader(io.StringIO(text)):
        if not row or not row[0].strip().isdigit():
            continue
        lead_id = int(row[0])
        if len(row) >= 6 and row[2] == "Match" and "," in row[5]:
            lon, lat = (float(v) for v in row[5].split(","))
            out[lead_id] = (lat, lon)
        else:
            out[lead_id] = None
    return out


def default_geocoder() -> Geocoder | None:
    settings = get_settings()
    if settings.geocoder_mode == "off":
        return None
    if settings.geocoder_mode == "fixture":
        return FixtureGeocoder(settings.fixtures_dir / "geocode.json")
    return CensusGeocoder(settings.census_geocoder_url, settings.fetch_user_agent)


def geocode_pending(
    geocoder: Geocoder | None = None, limit: int = 5000, retry_unmatched: bool = False
) -> dict[str, int]:
    """Geocode leads that have no match status yet. Safe to call after every import."""
    geocoder = geocoder or default_geocoder()
    if geocoder is None:
        return {"matched": 0, "unmatched": 0}
    with session_scope() as session:
        if retry_unmatched:
            for lead in session.scalars(select(Lead).where(Lead.geo_status == "unmatched")):
                lead.geo_status = None
    with session_scope() as session:
        pending = [
            (lead.id, lead.address, lead.city, lead.zip)
            for lead in session.scalars(
                select(Lead).where(Lead.geo_status.is_(None)).order_by(Lead.id).limit(limit)
            )
        ]
    if not pending:
        return {"matched": 0, "unmatched": 0}
    results = geocoder.geocode(pending)
    retry = [
        (lead_id, strip_unit(street), city, zip_code)
        for lead_id, street, city, zip_code in pending
        if not results.get(lead_id) and strip_unit(street) != street.strip()
    ]
    if retry:
        results.update({k: v for k, v in geocoder.geocode(retry).items() if v})
    matched = 0
    with session_scope() as session:
        for lead_id, *_ in pending:
            lead = session.get(Lead, lead_id)
            if lead is None:
                continue
            point = results.get(lead_id)
            if point:
                lead.lat, lead.lng, lead.geo_status = point[0], point[1], "matched"
                matched += 1
            else:
                lead.lat, lead.lng, lead.geo_status = None, None, "unmatched"
    log.info("geocoded %d leads: %d matched", len(pending), matched)
    return {"matched": matched, "unmatched": len(pending) - matched}
