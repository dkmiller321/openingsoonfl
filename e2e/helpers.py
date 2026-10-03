"""Small helpers shared by the specs: /test/* calls, seed datasets, CSV and email checks."""

from __future__ import annotations

import base64
import csv
import html
import io
from typing import Any

import httpx
from playwright.sync_api import Page, expect

CSV_HEADER = (
    "business_name,address,city,zip,county,lead_type,stage,first_seen,licensed_on,days_ahead,"
    "licensee,phone,email"
)


def set_clock(api: httpx.Client, iso: str | None) -> None:
    api.post("/test/clock", json={"now": iso}).raise_for_status()


def run(api: httpx.Client, job: str, fixture: str | None = None) -> dict[str, Any]:
    body = {"fixture": fixture} if fixture else {}
    response = api.post(f"/test/run/{job}", json=body)
    response.raise_for_status()
    return response.json()


def seed_standard(api: httpx.Client) -> None:
    set_clock(api, "2026-09-01T12:00:00Z")
    assert run(api, "import-plan-review", "plan_review_0901.csv")["status"] == "ok"
    set_clock(api, "2026-09-28T12:00:00Z")
    assert run(api, "import-weekly", "weekly_w1")["status"] == "ok"


def seed_plus_w2(api: httpx.Client) -> None:
    seed_standard(api)
    set_clock(api, "2026-10-05T10:00:00Z")
    assert run(api, "import-weekly", "weekly_w2")["status"] == "ok"


def leads(api: httpx.Client) -> list[dict[str, Any]]:
    response = api.get("/test/leads")
    response.raise_for_status()
    return response.json()


def matching(all_leads: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    needle = name.lower()
    return [lead for lead in all_leads if needle in lead["business_name"].lower()]


def lead_named(api: httpx.Client, name: str) -> dict[str, Any]:
    found = matching(leads(api), name)
    assert len(found) == 1, f"expected exactly one lead matching {name!r}, got {found}"
    return found[0]


def state(api: httpx.Client) -> dict[str, int]:
    return api.get("/test/state").json()


def outbox(api: httpx.Client) -> list[dict[str, Any]]:
    return api.get("/test/outbox").json()


def runs(api: httpx.Client) -> list[dict[str, Any]]:
    return api.get("/test/runs").json()


def text_of(email: dict[str, Any]) -> str:
    """The email HTML, unescaped and lower-cased, for name assertions."""
    return html.unescape(email["html"]).lower()


def csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def attachment_text(email: dict[str, Any], index: int = 0) -> tuple[str, str]:
    att = email["attachments"][index]
    return att["filename"], base64.b64decode(att["content_b64"]).decode("utf-8-sig")


def create_vendor(
    page: Page,
    name: str,
    emails: str,
    category: str,
    counties: tuple[str, ...] = ("brevard",),
    cadence: str = "weekly",
    active: bool = True,
) -> None:
    page.goto("/vendors")
    page.get_by_test_id("vendor-new").click()
    page.get_by_test_id("vendor-name").fill(name)
    page.get_by_test_id("vendor-emails").fill(emails)
    page.get_by_test_id("vendor-category").select_option(label=category)
    for county in ("brevard", "orange", "volusia"):
        box = page.get_by_test_id(f"vendor-county-{county}")
        if (county in counties) != box.is_checked():
            box.click()
    page.get_by_test_id("vendor-cadence").select_option(cadence)
    active_box = page.get_by_test_id("vendor-active")
    if active != active_box.is_checked():
        active_box.click()
    page.get_by_test_id("vendor-save").click()
    expect(page.get_by_test_id("vendor-row").filter(has_text=name)).to_have_count(1)


def lead_rows(page: Page):  # noqa: ANN201
    return page.get_by_test_id("lead-row")


def open_lead(page: Page, name: str) -> None:
    page.goto("/leads?hidden=1")
    row = page.get_by_test_id("lead-row").filter(has_text=name)
    row.get_by_test_id("lead-name").click()
    expect(page.get_by_test_id("lead-detail-name")).to_be_visible()
