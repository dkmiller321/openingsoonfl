"""Stage 3: admin console (E2E-12..18)."""

import re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import ADMIN_PASSWORD
from e2e.helpers import (
    CSV_HEADER,
    create_vendor,
    csv_rows,
    lead_named,
    open_lead,
    run,
    seed_plus_w2,
    seed_standard,
    set_clock,
)

pytestmark = pytest.mark.stage3


def test_e2e_12_login(page: Page) -> None:
    page.goto("/leads")
    expect(page).to_have_url(re.compile(r"/login"))
    page.get_by_test_id("login-password").fill("wrong")
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("login-error")).to_have_text("Wrong password")
    page.get_by_test_id("login-password").fill(ADMIN_PASSWORD)
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("stat-new-this-week")).to_be_visible()
    page.get_by_test_id("logout").click()
    page.goto("/leads")
    expect(page).to_have_url(re.compile(r"/login"))


def test_e2e_13_dashboard(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    admin.goto("/")
    expect(admin.get_by_test_id("stat-new-this-week")).to_have_text("4")
    expect(admin.get_by_test_id("stat-applied")).to_have_text("3")
    expect(admin.get_by_test_id("stat-active-vendors")).to_have_text("0")
    weekly = admin.locator('[data-testid="source-last-run"][data-source="dbpr_weekly"]')
    plan = admin.locator('[data-testid="source-last-run"][data-source="dbpr_plan_review"]')
    expect(weekly).to_have_attribute("data-status", "green")
    expect(plan).to_have_attribute("data-status", "amber")


def test_e2e_14_leads_table_filters_search(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    admin.get_by_test_id("nav-leads").click()
    expect(admin.get_by_test_id("leads-count")).to_have_text("7 leads")
    rows = admin.get_by_test_id("lead-row")
    expect(rows).to_have_count(7)
    expect(rows.first.get_by_test_id("lead-name")).to_contain_text("SPACECOAST WAFFLES")

    admin.get_by_test_id("filter-stage").select_option("Applied")
    admin.get_by_test_id("filter-apply").click()
    expect(rows).to_have_count(3)
    for name in ("Banana River Bagels", "Indian River Pho", "Viera Noodle Bar"):
        expect(rows.filter(has_text=name)).to_have_count(1)
    for i in range(3):
        expect(rows.nth(i).get_by_test_id("lead-days-ahead")).to_have_text("—")

    admin.reload()
    expect(admin.get_by_test_id("filter-stage")).to_have_value("Applied")
    expect(rows).to_have_count(3)

    admin.get_by_test_id("filter-stage").select_option("All")
    admin.get_by_test_id("filter-type").select_option(label="Ownership change")
    admin.get_by_test_id("filter-apply").click()
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("THE ROCKET DINER")

    admin.get_by_test_id("filter-type").select_option(label="All")
    admin.get_by_test_id("filter-search").fill("bagel")
    admin.get_by_test_id("filter-apply").click()
    expect(rows).to_have_count(1)

    admin.get_by_test_id("filter-search").fill("zzz")
    admin.get_by_test_id("filter-apply").click()
    expect(admin.get_by_test_id("leads-empty")).to_be_visible()


def test_e2e_15_lead_detail_and_timeline(api: httpx.Client, admin: Page) -> None:
    seed_plus_w2(api)
    open_lead(admin, "Indian River Pho")
    expect(admin.get_by_test_id("lead-detail-stage")).to_have_text("Licensed")
    expect(admin.get_by_test_id("lead-detail-days-ahead")).to_have_text("28 days ahead")
    events = admin.get_by_test_id("timeline-event")
    expect(events).to_have_count(2)
    expect(events.nth(0)).to_have_attribute("data-stage", "Applied")
    expect(events.nth(0)).to_have_attribute("data-date", "2026-09-01")
    expect(events.nth(1)).to_have_attribute("data-stage", "Licensed")
    expect(events.nth(1)).to_have_attribute("data-date", "2026-09-29")
    records = admin.get_by_test_id("raw-record")
    expect(records).to_have_count(2)
    plan = admin.locator('[data-testid="raw-record"][data-source="dbpr_plan_review"]')
    expect(admin.locator('[data-testid="raw-record"][data-source="dbpr_weekly"]')).to_have_count(1)
    expect(plan).to_contain_text("2235 N. Courtenay Parkway")
    expect(admin.get_by_test_id("lead-detail-phone")).to_have_text("321-555-0201")
    expect(admin.get_by_test_id("lead-detail-email")).to_have_text("owner@indianriverpho.example")
    expect(admin.get_by_test_id("lead-detail-licensee")).to_have_text("INDIAN RIVER PHO LLC")


def test_e2e_16_vendor_management(admin: Page) -> None:
    admin.get_by_test_id("nav-vendors").click()
    admin.get_by_test_id("vendor-new").click()
    options = admin.get_by_test_id("vendor-category").locator("option").all_inner_texts()
    assert [o.strip() for o in options] == [
        "POS", "Equipment", "Insurance", "Payroll", "Pest control", "Food supply", "Other",
    ]
    admin.get_by_test_id("vendor-name").fill("Bad Email Co")
    admin.get_by_test_id("vendor-emails").fill("not-an-email")
    admin.get_by_test_id("vendor-category").select_option(label="POS")
    admin.get_by_test_id("vendor-county-brevard").check()
    admin.get_by_test_id("vendor-save").click()
    expect(admin.get_by_test_id("vendor-error")).to_have_text("Enter valid email addresses")
    admin.goto("/vendors")
    expect(admin.get_by_test_id("vendor-row")).to_have_count(0)

    create_vendor(admin, "Space Coast POS", "pos@example.com", "POS")
    row = admin.get_by_test_id("vendor-row").filter(has_text="Space Coast POS")
    expect(row.get_by_test_id("vendor-status")).to_have_text("Active")

    row.get_by_role("link", name="Edit").click()
    admin.get_by_test_id("vendor-cadence").select_option("daily")
    admin.get_by_test_id("vendor-save").click()
    expect(admin.get_by_test_id("vendor-row")).to_have_count(1)
    admin.reload()
    admin.get_by_test_id("vendor-row").filter(has_text="Space Coast POS").get_by_role(
        "link", name="Edit"
    ).click()
    expect(admin.get_by_test_id("vendor-cadence")).to_have_value("daily")

    admin.get_by_test_id("vendor-active").uncheck()
    admin.get_by_test_id("vendor-save").click()
    row = admin.get_by_test_id("vendor-row").filter(has_text="Space Coast POS")
    expect(row.get_by_test_id("vendor-status")).to_have_text("Inactive")
    admin.get_by_test_id("nav-dashboard").click()
    expect(admin.get_by_test_id("stat-active-vendors")).to_have_text("0")


def test_e2e_17_web_csv_export(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    admin.goto("/leads")
    admin.get_by_test_id("filter-stage").select_option("Applied")
    admin.get_by_test_id("filter-apply").click()
    with admin.expect_download() as info:
        admin.get_by_test_id("export-csv").click()
    download = info.value
    assert download.suggested_filename == "leads-2026-09-28.csv"
    text = Path(download.path()).read_text(encoding="utf-8-sig")
    assert text.splitlines()[0] == CSV_HEADER
    rows = csv_rows(text)
    assert len(rows) == 3
    assert all(r["stage"] == "Applied" and r["days_ahead"] == "" for r in rows)


def test_e2e_18_hide_rename_note(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    open_lead(admin, "Viera Noodle Bar")
    admin.get_by_test_id("lead-edit-name").fill("Viera Noodle Bar & Grill")
    admin.get_by_test_id("lead-note-input").fill("Owner is Sam, opening Nov")
    admin.get_by_test_id("lead-save").click()
    admin.reload()
    expect(admin.get_by_test_id("lead-edit-name")).to_have_value("Viera Noodle Bar & Grill")
    expect(admin.get_by_test_id("lead-note-input")).to_have_value("Owner is Sam, opening Nov")
    expect(admin.get_by_test_id("lead-detail-name")).to_have_text("Viera Noodle Bar & Grill")

    admin.get_by_test_id("lead-hide").click()
    admin.goto("/leads")
    expect(admin.get_by_test_id("leads-count")).to_have_text("6 leads")
    admin.get_by_test_id("filter-hidden").check()
    admin.get_by_test_id("filter-apply").click()
    expect(admin.get_by_test_id("lead-row")).to_have_count(7)

    set_clock(api, "2026-09-02T12:00:00Z")
    run(api, "import-plan-review", "plan_review_0901.csv")
    viera = lead_named(api, "Viera Noodle Bar & Grill")
    assert viera["hidden"] is True
    assert viera["note"] == "Owner is Sam, opening Nov"
