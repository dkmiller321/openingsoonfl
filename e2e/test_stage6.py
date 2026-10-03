"""Stage 6: map and pipeline board (E2E-31..36)."""

import re

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import ADMIN_PASSWORD
from e2e.helpers import lead_named, leads, open_lead, seed_standard

pytestmark = pytest.mark.stage6


def _ids(api: httpx.Client, *names: str) -> str:
    return ",".join(str(i) for i in sorted(lead_named(api, n)["id"] for n in names))


def test_e2e_31_geocoding_on_import(api: httpx.Client) -> None:
    seed_standard(api)
    for lead in leads(api):
        if "viera" in lead["business_name"].lower():
            assert lead["geo_status"] == "unmatched"
            assert lead["lat"] is None
        else:
            assert lead["geo_status"] == "matched"
            assert lead["lat"] is not None and lead["lng"] is not None
    tacos = lead_named(api, "coastal tacos")
    assert tacos["lat"] == pytest.approx(28.356)
    assert tacos["lng"] == pytest.approx(-80.61)


def test_e2e_32_map_pins_and_cuisine(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    admin.get_by_test_id("nav-map").click()
    expect(admin.get_by_test_id("map-count")).to_have_text("6 leads on the map")
    expect(admin.get_by_test_id("map-unplaced")).to_have_text("1 not placed")
    items = admin.get_by_test_id("map-list-item")
    expect(items).to_have_count(6)
    expected = {
        "SALT & SMOKE BBQ": "bbq",
        "COASTAL TACOS": "mexican",
        "BANANA RIVER BAGELS": "bakery",
        "Indian River Pho": "asian",
        "SPACECOAST WAFFLES": "breakfast",
    }
    for name, cuisine in expected.items():
        expect(items.filter(has_text=name)).to_have_attribute("data-cuisine", cuisine)
    items.filter(has_text="COASTAL TACOS").click()
    popup = admin.get_by_test_id("map-popup")
    expect(popup).to_contain_text("COASTAL TACOS")
    expect(popup).to_contain_text("Licensed")
    tacos_id = lead_named(api, "coastal tacos")["id"]
    admin.get_by_test_id("map-popup-link").click()
    expect(admin).to_have_url(re.compile(rf"/leads/{tacos_id}$"))


def test_e2e_33_time_slider(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    admin.goto("/map")
    expect(admin.get_by_test_id("map-slider-label")).to_have_text("Through Sep 28, 2026")
    admin.get_by_test_id("map-slider").fill("18")
    expect(admin.get_by_test_id("map-slider-label")).to_have_text("Through Sep 10, 2026")
    expect(admin.get_by_test_id("map-count")).to_have_text("2 leads on the map")
    expect(admin.get_by_test_id("map-canvas")).to_have_attribute(
        "data-visible-ids", _ids(api, "banana river bagels", "indian river pho")
    )
    admin.get_by_test_id("map-slider").fill("0")
    expect(admin.get_by_test_id("map-count")).to_have_text("6 leads on the map")


def test_e2e_34_radius_filter(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    admin.goto("/map")
    count = admin.get_by_test_id("map-count")
    admin.get_by_test_id("map-center").select_option(label="Cocoa Beach")
    admin.get_by_test_id("map-radius").select_option("5")
    expect(count).to_have_text("2 leads on the map")
    expect(admin.get_by_test_id("map-canvas")).to_have_attribute(
        "data-visible-ids", _ids(api, "coastal tacos", "banana river bagels")
    )
    admin.get_by_test_id("map-radius").select_option("10")
    expect(count).to_have_text("3 leads on the map")
    admin.get_by_test_id("map-radius").select_option("25")
    expect(count).to_have_text("6 leads on the map")
    admin.get_by_test_id("map-radius").select_option("Off")
    expect(count).to_have_text("6 leads on the map")
    admin.get_by_test_id("map-radius").select_option("5")
    admin.get_by_test_id("map-slider").fill("18")
    expect(count).to_have_text("1 lead on the map")


def test_e2e_35_pipeline_board(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    admin.get_by_test_id("nav-board").click()
    expect(admin.get_by_test_id("board-count-applied")).to_have_text("3")
    expect(admin.get_by_test_id("board-count-licensed")).to_have_text("4")
    applied = admin.get_by_test_id("board-col-applied")
    for name in ("Banana River Bagels", "Indian River Pho", "Viera Noodle Bar"):
        expect(applied.get_by_test_id("board-card").filter(has_text=name)).to_have_count(1)
    waffles = admin.get_by_test_id("board-card").filter(has_text="SPACECOAST WAFFLES")
    expect(waffles.get_by_test_id("board-card-icon")).to_have_text("\U0001f9c7")
    waffles.get_by_role("link").first.click()
    expect(admin.get_by_test_id("lead-detail-name")).to_have_text("SPACECOAST WAFFLES")

    open_lead(admin, "The Rocket Diner")
    admin.get_by_test_id("lead-hide").click()
    admin.goto("/board")
    expect(admin.get_by_test_id("board-count-licensed")).to_have_text("3")


def test_e2e_36_map_data_respects_filters(api: httpx.Client, live_server: str) -> None:
    seed_standard(api)
    with httpx.Client(base_url=live_server, timeout=30) as client:
        anonymous = client.get("/map/data.json?stage=Applied", follow_redirects=False)
        assert anonymous.status_code in (302, 303, 307)
        assert anonymous.headers["location"].endswith("/login")
        client.post("/login", data={"password": ADMIN_PASSWORD})
        data = client.get("/map/data.json?stage=Applied").json()
    assert data["unplaced"] == 1
    assert len(data["leads"]) == 2
    keys = {"id", "name", "lat", "lng", "stage", "lead_type", "cuisine", "icon", "first_seen",
            "days_ahead", "city", "phone"}
    for lead in data["leads"]:
        assert keys <= set(lead)
        assert lead["stage"] == "Applied"
