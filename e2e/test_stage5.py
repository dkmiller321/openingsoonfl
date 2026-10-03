"""Stage 5: source health, schedule (E2E-25..30)."""

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import REPO_ROOT
from e2e.helpers import outbox, run, runs, set_clock

pytestmark = pytest.mark.stage5


def _source_row(page: Page, source: str):  # noqa: ANN202
    return page.locator(f'[data-testid="source-row"][data-source="{source}"]')


def test_e2e_25_failed_run_alerts(api: httpx.Client, admin: Page) -> None:
    set_clock(api, "2026-09-28T12:00:00Z")
    result = run(api, "import-weekly", "weekly_unavailable")
    assert result["status"] == "failed"
    assert "HTTP 503" in result["error"]
    (alert,) = outbox(api)
    assert alert["to"] == ["operator@example.com"]
    assert alert["subject"] == "[OpeningSoon FL] Source problem: dbpr_weekly - run failed"
    assert "HTTP 503" in alert["text"]
    admin.goto("/sources")
    expect(_source_row(admin, "dbpr_weekly")).to_have_attribute("data-status", "red")


def test_e2e_26_zero_rows_alerts(api: httpx.Client, admin: Page) -> None:
    set_clock(api, "2026-09-28T12:00:00Z")
    run(api, "import-weekly", "weekly_w1")
    set_clock(api, "2026-10-05T12:00:00Z")
    result = run(api, "import-weekly", "weekly_empty")
    assert result["status"] == "ok"
    assert result["rows_fetched"] == 0
    (alert,) = outbox(api)
    assert alert["subject"] == "[OpeningSoon FL] Source problem: dbpr_weekly - zero rows"
    admin.goto("/sources")
    expect(_source_row(admin, "dbpr_weekly")).to_have_attribute("data-status", "red")


def test_e2e_27_changed_columns_alert(api: httpx.Client) -> None:
    result = run(api, "import-weekly", "weekly_bad_columns")
    assert result["status"] == "failed"
    assert "CNTY_RENAMED" in result["error"]
    assert result["leads_created"] == 0
    (alert,) = outbox(api)
    assert alert["subject"] == "[OpeningSoon FL] Source problem: dbpr_weekly - columns changed"


def test_e2e_28_staleness_and_run_history(api: httpx.Client, admin: Page) -> None:
    set_clock(api, "2026-09-28T12:00:00Z")
    for _ in range(12):
        run(api, "import-weekly", "weekly_w1")
    set_clock(api, "2026-09-29T12:00:00Z")
    run(api, "import-plan-review", "plan_review_0901.csv")
    admin.goto("/sources")
    weekly = _source_row(admin, "dbpr_weekly")
    expect(weekly).to_have_attribute("data-status", "green")
    expect(weekly.get_by_test_id("run-row")).to_have_count(10)

    set_clock(api, "2026-10-06T12:00:00Z")
    result = run(api, "check-health")
    assert result["statuses"]["dbpr_weekly"] == "green"
    assert result["statuses"]["dbpr_plan_review"] == "amber"
    assert result["alerts_sent"] == 1
    assert outbox(api)[-1]["subject"] == (
        "[OpeningSoon FL] Source problem: dbpr_plan_review - stale"
    )

    set_clock(api, "2026-10-07T12:00:00Z")
    result = run(api, "check-health")
    assert result["statuses"]["dbpr_weekly"] == "amber"
    assert result["alerts_sent"] == 1
    assert run(api, "check-health")["alerts_sent"] == 0
    admin.reload()
    expect(_source_row(admin, "dbpr_weekly")).to_have_attribute("data-status", "amber")


def test_e2e_29_manual_upload(api: httpx.Client, admin: Page) -> None:
    admin.goto("/sources")
    admin.get_by_test_id("source-upload-file").set_input_files(
        str(REPO_ROOT / "fixtures" / "dbpr_weekly" / "weekly_w1" / "newfood.csv")
    )
    admin.get_by_test_id("source-upload-submit").click()
    expect(admin.get_by_test_id("upload-result")).to_have_text("5 rows, 3 new leads")
    latest = runs(api)[0]
    assert latest["source"] == "dbpr_weekly"
    assert latest["trigger"] == "manual"


def test_e2e_30_schedule_wiring(api: httpx.Client) -> None:
    set_clock(api, "2026-10-05T09:30:00Z")
    schedule = {row["job"]: row["next_run"] for row in api.get("/test/schedule").json()}
    assert schedule == {
        "import-weekly": "2026-10-05T10:00:00Z",
        "import-plan-review": "2026-10-06T09:00:00Z",
        "send-digests-daily": "2026-10-05T11:00:00Z",
        "send-digests-weekly": "2026-10-05T11:00:00Z",
        "check-health": "2026-10-05T10:15:00Z",
    }
    set_clock(api, "2026-10-06T12:00:00Z")
    schedule = {row["job"]: row["next_run"] for row in api.get("/test/schedule").json()}
    assert schedule["send-digests-weekly"] == "2026-10-12T11:00:00Z"
