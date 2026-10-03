"""Stage 2: plan review import + merge (E2E-07..11)."""

import httpx
import pytest

from e2e.helpers import lead_named, leads, matching, run, runs, seed_plus_w2, set_clock, state

pytestmark = pytest.mark.stage2


def test_e2e_07_plan_reviews_become_applied_leads(api: httpx.Client) -> None:
    set_clock(api, "2026-09-01T12:00:00Z")
    result = run(api, "import-plan-review", "plan_review_0901.csv")
    assert result["leads_created"] == 3
    all_leads = leads(api)
    assert len(all_leads) == 3
    for name in ("banana river bagels", "indian river pho", "viera noodle bar"):
        (lead,) = matching(all_leads, name)
        assert lead["stage"] == "Applied"
        assert lead["first_seen"] == "2026-09-01"
        assert lead["days_ahead"] is None
        assert len(lead["events"]) == 1
        assert lead["events"][0]["source"] == "dbpr_plan_review"
    (bagels,) = matching(all_leads, "banana river bagels")
    assert bagels["phone"] == "321-555-0302"
    assert bagels["email"] == "bagels@example.com"
    (viera,) = matching(all_leads, "viera noodle bar")
    assert viera["email"] == ""


def test_e2e_08_plan_review_and_licence_merge(api: httpx.Client) -> None:
    seed_plus_w2(api)
    all_leads = leads(api)
    assert len(all_leads) == 8
    found = matching(all_leads, "indian river pho")
    assert len(found) == 1
    pho = found[0]
    assert pho["stage"] == "Licensed"
    assert pho["first_seen"] == "2026-09-01"
    assert pho["licensed_on"] == "2026-09-29"
    assert pho["days_ahead"] == 28
    assert pho["phone"] == "321-555-0201"
    assert pho["email"] == "owner@indianriverpho.example"
    assert pho["events"] == [
        {"stage": "Applied", "date": "2026-09-01", "source": "dbpr_plan_review"},
        {"stage": "Licensed", "date": "2026-09-29", "source": "dbpr_weekly"},
    ]


def test_e2e_09_stage_never_regresses(api: httpx.Client) -> None:
    set_clock(api, "2026-10-05T10:00:00Z")
    run(api, "import-weekly", "weekly_w2")
    set_clock(api, "2026-10-06T12:00:00Z")
    run(api, "import-plan-review", "plan_review_1006.csv")
    pho = lead_named(api, "indian river pho")
    assert pho["stage"] == "Licensed"
    assert pho["first_seen"] == "2026-09-29"
    assert pho["days_ahead"] == 0
    assert len(pho["events"]) == 2
    assert pho["events"][1]["stage"] == "Applied"
    assert pho["events"][1]["date"] == "2026-10-06"
    assert len(leads(api)) == 2


def test_e2e_09b_licence_number_match(api: httpx.Client) -> None:
    set_clock(api, "2026-08-01T12:00:00Z")
    run(api, "import-plan-review", "plan_review_with_licence.csv")
    set_clock(api, "2026-09-16T12:00:00Z")
    run(api, "import-weekly", "weekly_licence_match")
    all_leads = leads(api)
    assert len(all_leads) == 1
    lead = all_leads[0]
    assert len(lead["events"]) == 2
    assert lead["stage"] == "Licensed"
    assert lead["first_seen"] == "2026-08-01"
    assert lead["licensed_on"] == "2026-09-15"
    assert lead["days_ahead"] == 45


def test_e2e_10_failed_run_is_atomic(api: httpx.Client) -> None:
    set_clock(api, "2026-09-28T12:00:00Z")
    result = run(api, "import-weekly", "weekly_partial_error")
    assert result["status"] == "failed"
    assert result["leads_created"] == 0
    assert "chgownr_food.csv" in result["error"]
    counts = state(api)
    assert counts["leads"] == 0
    assert counts["raw_records"] == 0
    assert runs(api)[0]["status"] == "failed"


def test_e2e_11_real_plan_review_sample_parses(api: httpx.Client) -> None:
    result = run(api, "import-plan-review", "plan_review_real_sample.csv")
    assert result["status"] == "ok"
    assert result["error"] is None
    all_leads = leads(api)
    assert len(all_leads) >= 50
    for lead in all_leads:
        assert lead["county"] == "Brevard"
        assert lead["stage"] == "Applied"
        assert lead["business_name"].strip()
        assert lead["address"].strip()
        assert lead["zip"].strip()
    with_contact = [lead for lead in all_leads if lead["phone"] or lead["email"]]
    assert len(with_contact) / len(all_leads) >= 0.8
