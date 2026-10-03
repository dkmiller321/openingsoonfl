"""Smoke suite: live DBPR and Resend (E2E_TESTS.md section 3). Manual only: RUN_SMOKE=1."""

import csv
import io
import os
import subprocess
import sys

import httpx
import pytest
from sqlalchemy import create_engine, text

from e2e.conftest import REPO_ROOT

pytestmark = pytest.mark.smoke

FILES = {
    "newfood": "https://www2.myfloridalicense.com/sto/file_download/extracts/newfood.csv",
    "chgownr_food": "https://www2.myfloridalicense.com/sto/file_download/extracts/chgownr_food.csv",
    "HR_plan_review": (
        "https://www2.myfloridalicense.com/sto/file_download/extracts/HR_plan_review.csv"
    ),
}


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["SOURCE_MODE"] = "live"
    return env


def _osfl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "osfl.cli", *args], cwd=REPO_ROOT, env=_env(),
        capture_output=True, text=True, timeout=600,
    )


def _db():  # noqa: ANN202
    from osfl.settings import load_settings

    return create_engine(load_settings().database_url)


def test_smoke_1_live_licence_import() -> None:
    result = _osfl("import-weekly", "--county", "brevard")
    assert result.returncode == 0, result.stdout + result.stderr
    with _db().connect() as conn:
        status, fetched = conn.execute(text(
            "SELECT status, rows_fetched FROM source_runs WHERE source='dbpr_weekly' "
            "ORDER BY id DESC LIMIT 1"
        )).one()
        brevard = conn.execute(text(
            "SELECT count(*) FROM raw_records WHERE source='dbpr_weekly'"
        )).scalar_one()
    assert status == "ok"
    assert fetched > 0
    assert brevard >= 1
    print(f"live licence rows fetched: {fetched}, Brevard raw records: {brevard}")


def test_smoke_2_live_headers_unchanged() -> None:
    from osfl.settings import load_settings

    agent = load_settings().fetch_user_agent
    for name, url in FILES.items():
        expected = (REPO_ROOT / "fixtures" / "headers" / f"{name}.csv").read_text("utf-8-sig")
        with httpx.stream("GET", url, headers={"User-Agent": agent}, timeout=60) as response:
            first = next(response.iter_lines())
        assert next(csv.reader(io.StringIO(first.lstrip("﻿")))) == next(
            csv.reader(io.StringIO(expected))
        ), name


def test_smoke_3_live_plan_review_import() -> None:
    result = _osfl("import-plan-review", "--county", "brevard")
    assert result.returncode == 0, result.stdout + result.stderr
    with _db().connect() as conn:
        status = conn.execute(text(
            "SELECT status FROM source_runs WHERE source='dbpr_plan_review' "
            "ORDER BY id DESC LIMIT 1"
        )).scalar_one()
        applied = conn.execute(text(
            "SELECT count(*) FROM leads WHERE county='brevard' AND stage='Applied'"
        )).scalar_one()
    assert status == "ok"
    assert applied >= 1
    print(f"Brevard leads in plan review (Applied): {applied}")


@pytest.mark.skipif(
    not (os.environ.get("RESEND_API_KEY") and os.environ.get("EMAIL_FROM")),
    reason="needs RESEND_API_KEY and EMAIL_FROM",
)
def test_smoke_4_real_email() -> None:
    from osfl.digests.sender import send_email

    from osfl.settings import load_settings

    settings = load_settings()
    message_id = send_email(
        to=[settings.operator_email],
        subject="[TEST] OpeningSoon FL smoke test",
        html="<p>Smoke test from OpeningSoon FL.</p>",
        text="Smoke test from OpeningSoon FL.",
        attachments=[],
        mode="resend",
    )
    assert message_id
