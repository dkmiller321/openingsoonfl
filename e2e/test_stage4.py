"""Stage 4: digests (E2E-19..24). E2E-19 is the most important test in the suite."""

import re

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import POSTAL_ADDRESS
from e2e.helpers import (
    CSV_HEADER,
    attachment_text,
    create_vendor,
    csv_rows,
    lead_named,
    open_lead,
    outbox,
    run,
    seed_standard,
    set_clock,
    state,
    text_of,
)

pytestmark = pytest.mark.stage4


def _core_promise_first_digest(api: httpx.Client, admin: Page) -> None:
    """E2E-19 steps 1-3."""
    set_clock(api, "2026-09-01T12:00:00Z")
    run(api, "import-plan-review", "plan_review_0901.csv")
    create_vendor(admin, "Space Coast POS", "pos@example.com", "POS")
    set_clock(api, "2026-09-07T11:00:00Z")
    assert run(api, "send-digests-weekly")["emails_sent"] == 1


def test_e2e_19_core_promise_early_and_never_twice(api: httpx.Client, admin: Page) -> None:
    _core_promise_first_digest(api, admin)

    (first,) = outbox(api)
    assert first["to"] == ["pos@example.com"]
    assert first["subject"] == "3 new restaurants in Brevard - week of Sep 7, 2026"
    body = text_of(first)
    for name in ("banana river bagels", "indian river pho", "viera noodle bar"):
        assert name in body
    assert body.count("application in progress") == 3
    assert "phone: 321-555-0302" in body
    assert "email: bagels@example.com" in body
    assert len(first["attachments"]) == 1
    filename, csv_text = attachment_text(first)
    assert filename == "leads-2026-09-07.csv"
    assert csv_text.splitlines()[0] == CSV_HEADER
    rows = csv_rows(csv_text)
    assert len(rows) == 3
    assert all(r["stage"] == "Applied" for r in rows)

    set_clock(api, "2026-09-28T12:00:00Z")
    run(api, "import-weekly", "weekly_w1")
    set_clock(api, "2026-10-05T10:00:00Z")
    run(api, "import-weekly", "weekly_w2")

    set_clock(api, "2026-10-05T11:00:00Z")
    assert run(api, "send-digests-weekly")["emails_sent"] == 1
    emails = outbox(api)
    assert len(emails) == 2
    second = emails[1]
    assert second["subject"] == "5 new restaurants in Brevard - week of Oct 5, 2026"
    body = text_of(second)
    for name in (
        "salt & smoke bbq", "coastal tacos", "the rocket diner", "spacecoast waffles",
        "cocoa village creperie",
    ):
        assert name in body
    assert "ownership change" in body
    assert "food truck" in body
    assert "indian river pho" not in body

    deliveries = api.get("/test/deliveries").json()
    (pho_delivery,) = [d for d in deliveries if "indian river pho" in d["business_name"].lower()]
    assert pho_delivery["vendor_name"] == "Space Coast POS"
    assert pho_delivery["delivered_on"] == "2026-09-07"
    pho = lead_named(api, "indian river pho")
    assert pho["licensed_on"] == "2026-09-29"
    assert pho["days_ahead"] == 28


def test_e2e_20_one_digest_per_period(api: httpx.Client, admin: Page) -> None:
    _core_promise_first_digest(api, admin)
    assert run(api, "send-digests-weekly")["emails_sent"] == 0
    counts = state(api)
    assert counts["outbox"] == 1
    assert counts["deliveries"] == 3


def test_e2e_21_cadence_region_inactive_hidden_empty(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    open_lead(admin, "The Rocket Diner")
    admin.get_by_test_id("lead-hide").click()
    create_vendor(admin, "Space Coast POS", "pos@example.com", "POS")
    create_vendor(admin, "Brevard Pest Pros", "pest@example.com", "Pest control", cadence="daily")
    create_vendor(admin, "Orlando Insurance Group", "ins@example.com", "Insurance",
                  counties=("orange",))
    create_vendor(admin, "Idle Equipment Co", "idle@example.com", "Equipment", active=False)

    set_clock(api, "2026-09-29T11:00:00Z")
    assert run(api, "send-digests-daily")["emails_sent"] == 1
    (daily,) = outbox(api)
    assert daily["to"] == ["pest@example.com"]
    assert daily["subject"] == "6 new restaurants in Brevard - Sep 29, 2026"
    assert "rocket diner" not in text_of(daily)

    set_clock(api, "2026-10-05T11:00:00Z")
    assert run(api, "send-digests-weekly")["emails_sent"] == 2
    emails = outbox(api)[1:]
    by_to = {tuple(e["to"]): e for e in emails}
    assert by_to[("pos@example.com",)]["subject"] == (
        "6 new restaurants in Brevard - week of Oct 5, 2026"
    )
    ins = by_to[("ins@example.com",)]
    assert ins["subject"] == "0 new restaurants in Orange - week of Oct 5, 2026"
    assert "no new restaurants this week" in text_of(ins)
    assert ("idle@example.com",) not in by_to


def test_e2e_22_preview_and_test_send(api: httpx.Client, admin: Page) -> None:
    seed_standard(api)
    create_vendor(admin, "Space Coast POS", "pos@example.com", "POS")
    row = admin.get_by_test_id("vendor-row").filter(has_text="Space Coast POS")
    row.get_by_test_id("digest-preview-link").click()
    preview = admin.get_by_test_id("digest-preview")
    for name in (
        "Banana River Bagels", "Indian River Pho", "Viera Noodle Bar", "Salt & Smoke BBQ",
        "Coastal Tacos", "The Rocket Diner", "Spacecoast Waffles",
    ):
        expect(preview).to_contain_text(name, ignore_case=True)
    admin.get_by_test_id("digest-send-test").click()
    expect(admin.get_by_test_id("digest-test-sent")).to_have_text(
        "Test sent to operator@example.com"
    )
    (test_email,) = outbox(api)
    assert test_email["to"] == ["operator@example.com"]
    assert test_email["subject"] == "[TEST] 7 new restaurants in Brevard - week of Sep 28, 2026"
    assert state(api)["deliveries"] == 0

    assert run(api, "send-digests-weekly")["emails_sent"] == 1
    real = outbox(api)[1]
    assert real["to"] == ["pos@example.com"]
    assert real["subject"].startswith("7 new restaurants")


def test_e2e_23_unsubscribe_and_postal_address(api: httpx.Client, admin: Page) -> None:
    _core_promise_first_digest(api, admin)
    (email,) = outbox(api)
    assert POSTAL_ADDRESS in email["html"]
    match = re.search(r"http://127\.0\.0\.1:8001/unsubscribe/[A-Za-z0-9_-]{16,}", email["html"])
    if match is None:  # BASE_URL runs use that server's APP_BASE_URL
        match = re.search(r"https?://[^\"' <>]+/unsubscribe/[A-Za-z0-9_-]{16,}", email["html"])
    assert match, "no unsubscribe link in the digest"
    link = match.group(0)

    admin.goto(link)
    expect(admin.get_by_test_id("unsubscribe-confirm")).to_have_text(
        "You're unsubscribed from OpeningSoon FL digests."
    )
    admin.goto("/vendors")
    row = admin.get_by_test_id("vendor-row").filter(has_text="Space Coast POS")
    expect(row.get_by_test_id("vendor-status")).to_have_text("Inactive")

    set_clock(api, "2026-09-14T11:00:00Z")
    assert run(api, "send-digests-weekly")["emails_sent"] == 0
    admin.goto(link)
    expect(admin.get_by_test_id("unsubscribe-confirm")).to_have_text(
        "You're unsubscribed from OpeningSoon FL digests."
    )


def test_e2e_24_category_cap_warning(admin: Page) -> None:
    create_vendor(admin, "POS One", "one@example.com", "POS")
    expect(admin.get_by_test_id("vendor-cap-warning")).to_have_count(0)
    create_vendor(admin, "POS Two", "two@example.com", "POS")
    expect(admin.get_by_test_id("vendor-cap-warning")).to_have_count(0)
    create_vendor(admin, "POS Three", "three@example.com", "POS")
    row = admin.get_by_test_id("vendor-row").filter(has_text="POS Three")
    expect(row.get_by_test_id("vendor-status")).to_have_text("Active")
    expect(admin.get_by_test_id("vendor-cap-warning")).to_have_text(
        "POS already has 2 active vendors in Brevard"
    )
