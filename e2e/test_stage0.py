"""Stage 0: skeleton (E2E-00..02)."""

import os
import subprocess
import time

import httpx
import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import db_url_for_tests, make_test_env, start_app, stop_process, wait_healthy

pytestmark = pytest.mark.stage0


def test_e2e_00_app_boots(api: httpx.Client, page: Page) -> None:
    health = api.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "db": "ok"}
    reset = api.post("/test/reset")
    assert reset.status_code == 200
    assert reset.json() == {"ok": True}
    page.goto("/login")
    expect(page.get_by_test_id("login-password")).to_be_visible()


@pytest.mark.no_reset
@pytest.mark.skipif(bool(os.environ.get("BASE_URL")), reason="needs a local throwaway server")
def test_e2e_01_env_validation() -> None:
    env = make_test_env(8011, db_url_for_tests())
    env.pop("ADMIN_PASSWORD")
    proc = start_app(env, 8011, "e2e-01.log")
    try:
        code = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        stop_process(proc)
        pytest.fail("server kept running without ADMIN_PASSWORD")
    time.sleep(0.2)
    output = (os.path.join("logs", "e2e-01.log"))
    with open(output, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    assert code != 0
    assert "ADMIN_PASSWORD" in text


@pytest.mark.no_reset
@pytest.mark.skipif(bool(os.environ.get("BASE_URL")), reason="needs a local throwaway server")
def test_e2e_02_test_routes_gated() -> None:
    env = make_test_env(8012, db_url_for_tests())
    env["TEST_ROUTES"] = "0"
    proc = start_app(env, 8012, "e2e-02.log")
    try:
        wait_healthy("http://127.0.0.1:8012", proc)
        assert httpx.post("http://127.0.0.1:8012/test/reset").status_code == 404
        assert httpx.get("http://127.0.0.1:8012/health").status_code == 200
    finally:
        stop_process(proc)
