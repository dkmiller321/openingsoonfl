"""Stage 1: weekly licence import + lead sheet (E2E-03..06)."""

import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from e2e.conftest import REPO_ROOT, db_url_for_tests, make_test_env
from e2e.helpers import CSV_HEADER, csv_rows, leads, matching, run, runs, set_clock, state

pytestmark = pytest.mark.stage1


def test_e2e_03_weekly_import_creates_leads(api: httpx.Client) -> None:
    set_clock(api, "2026-09-28T12:00:00Z")
    result = run(api, "import-weekly", "weekly_w1")
    assert result["status"] == "ok"
    assert result["rows_fetched"] == 6
    assert result["rows_new"] == 5
    assert result["leads_created"] == 4

    all_leads = leads(api)
    assert len(all_leads) == 4
    expected = {
        "salt & smoke bbq": ("new", "321-555-0101"),
        "coastal tacos": ("new", "321-555-0102"),
        "the rocket diner": ("ownership_change", "321-555-0103"),
        "spacecoast waffles": ("mobile", "321-555-0104"),
    }
    for name, (lead_type, phone) in expected.items():
        (lead,) = matching(all_leads, name)
        assert lead["lead_type"] == lead_type
        assert lead["stage"] == "Licensed"
        assert lead["days_ahead"] == 0
        assert lead["county"] == "Brevard"
        assert lead["phone"] == phone
    assert matching(all_leads, "harbor vending") == []
    assert matching(all_leads, "lake eola") == []
    assert state(api)["raw_records"] == 5
    latest = runs(api)[0]
    assert latest["source"] == "dbpr_weekly"
    assert latest["status"] == "ok"


def test_e2e_04_import_is_idempotent(api: httpx.Client) -> None:
    set_clock(api, "2026-09-28T12:00:00Z")
    run(api, "import-weekly", "weekly_w1")
    second = run(api, "import-weekly", "weekly_w1")
    assert second["rows_new"] == 0
    assert second["leads_created"] == 0
    counts = state(api)
    assert counts["leads"] == 4
    assert counts["raw_records"] == 5
    assert counts["source_runs"] == 2


@pytest.mark.skipif(bool(os.environ.get("BASE_URL")), reason="CLI runs against the local test DB")
def test_e2e_05_cli_lead_sheet(api: httpx.Client, tmp_path: Path) -> None:
    env = make_test_env(8001, db_url_for_tests())
    env["FAKE_NOW"] = "2026-09-28T12:00:00Z"
    osfl = [sys.executable, "-m", "osfl.cli"]
    imported = subprocess.run(
        [*osfl, "import-weekly", "--county", "brevard", "--dir", "fixtures/dbpr_weekly/weekly_w1"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
    )
    assert imported.returncode == 0, imported.stdout + imported.stderr

    out = tmp_path / "leads.csv"
    exported = subprocess.run(
        [*osfl, "export-csv", "--county", "brevard", "--since", "2026-09-01", "--out", str(out)],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
    )
    assert exported.returncode == 0, exported.stdout + exported.stderr
    assert exported.stdout.strip() == f"Exported 4 leads to {out}"

    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0] == CSV_HEADER
    rows = csv_rows(text)
    assert len(rows) == 4
    assert rows[0]["business_name"] == "SPACECOAST WAFFLES"
    (salt,) = [r for r in rows if r["business_name"] == "SALT & SMOKE BBQ"]
    assert salt["lead_type"] == "new"
    assert salt["stage"] == "Licensed"
    assert salt["first_seen"] == "2026-09-22"
    assert salt["licensed_on"] == "2026-09-22"
    assert salt["days_ahead"] == "0"
    assert salt["licensee"] == "SALT & SMOKE BBQ LLC"
    assert salt["phone"] == "321-555-0101"
    assert salt["email"] == ""


def test_e2e_06_real_sample_parses(api: httpx.Client) -> None:
    result = run(api, "import-weekly", "weekly_real_sample")
    assert result["status"] == "ok"
    assert result["rows_fetched"] >= 20
    assert result["error"] is None
    all_leads = leads(api)
    assert all_leads
    for lead in all_leads:
        assert lead["county"] == "Brevard"
        assert lead["business_name"].strip()
        assert lead["address"].strip()
    types = {lead["lead_type"] for lead in all_leads}
    assert {"new", "ownership_change", "mobile"} <= types
