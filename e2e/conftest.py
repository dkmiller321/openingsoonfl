"""Shared E2E fixtures: the server under test, DB reset, API client (E2E_TESTS.md section 1)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import psycopg
import pytest
from playwright.sync_api import Page, expect

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
DEFAULT_TEST_DB = "postgresql+psycopg://osfl:change-me@127.0.0.1:55433/osfl_test"
TEST_PORT = 8001
ADMIN_PASSWORD = "test-admin-pw"
OPERATOR_EMAIL = "operator@example.com"
POSTAL_ADDRESS = "OpeningSoon FL, PO Box 1000, Melbourne, FL 32901"


def _dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def db_url_for_tests() -> str:
    return (
        os.environ.get("TEST_DATABASE_URL") or _dotenv().get("TEST_DATABASE_URL") or DEFAULT_TEST_DB
    )


def ensure_database(url: str) -> None:
    plain = url.replace("+psycopg", "")
    base, _, db_name = plain.rpartition("/")
    db_name = db_name.split("?")[0]
    with psycopg.connect(f"{base}/postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{db_name}"')


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def stop_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def make_test_env(port: int, db_url: str) -> dict[str, str]:
    """The test env from E2E_TESTS.md section 1.2. OSFL_ENV_FILE='' ignores .env entirely."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OSFL_", "FAKE_NOW"))}
    env.update(
        {
            "OSFL_ENV_FILE": "",
            "DATABASE_URL": db_url,
            "TEST_ROUTES": "1",
            "SOURCE_MODE": "fixture",
            "EMAIL_MODE": "outbox",
            "SCHEDULER_ENABLED": "0",
            "ADMIN_PASSWORD": ADMIN_PASSWORD,
            "SESSION_SECRET": "test-session-secret",
            "OPERATOR_EMAIL": OPERATOR_EMAIL,
            "OPERATOR_POSTAL_ADDRESS": POSTAL_ADDRESS,
            "APP_BASE_URL": f"http://127.0.0.1:{port}",
            "MAX_VENDORS_PER_CATEGORY": "2",
            "COUNTIES": "brevard",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return env


def start_app(env: dict[str, str], port: int, log_name: str) -> subprocess.Popen[bytes]:
    """Launch uvicorn with this venv's Python (not `uv run`), so killing it stops the server."""
    if port_in_use(port):
        raise RuntimeError(f"port {port} is already in use; a stale server would be tested")
    LOG_DIR.mkdir(exist_ok=True)
    log = (LOG_DIR / log_name).open("wb")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "osfl.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def wait_healthy(url: str, proc: subprocess.Popen[bytes] | None, seconds: float = 30) -> None:
    deadline = time.monotonic() + seconds
    while True:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError("server exited early; see logs/")
        try:
            if httpx.get(f"{url}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(f"server did not become healthy within {seconds} s")
        time.sleep(0.3)


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    base_url = os.environ.get("BASE_URL")
    if base_url:
        yield base_url.rstrip("/")
        return
    db_url = db_url_for_tests()
    ensure_database(db_url)
    env = make_test_env(TEST_PORT, db_url)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT, env=env, check=True
    )
    proc = start_app(env, TEST_PORT, "test-server.log")
    url = f"http://127.0.0.1:{TEST_PORT}"
    try:
        wait_healthy(url, proc)
        yield url
    finally:
        stop_process(proc)


@pytest.fixture
def api(live_server: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=live_server, timeout=60) as client:
        yield client


@pytest.fixture(scope="session")
def base_url(live_server: str) -> str:
    """pytest-playwright reads this so page.goto('/...') resolves against the server."""
    return live_server


@pytest.fixture(autouse=True)
def _reset_db(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("smoke") or request.node.get_closest_marker("no_reset"):
        return
    live = request.getfixturevalue("live_server")
    httpx.post(f"{live}/test/reset", timeout=60).raise_for_status()


@pytest.fixture(autouse=True)
def _timeouts(request: pytest.FixtureRequest) -> None:
    timeout_ms = int(os.environ.get("PW_TIMEOUT_MS", "10000"))
    expect.set_options(timeout=timeout_ms)
    if "page" in request.fixturenames:
        request.getfixturevalue("page").set_default_timeout(timeout_ms)


@pytest.fixture
def admin(page: Page) -> Page:
    """A page logged in as the operator."""
    login(page)
    return page


def login(page: Page) -> None:
    page.goto("/login")
    page.get_by_test_id("login-password").fill(ADMIN_PASSWORD)
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("stat-new-this-week")).to_be_visible()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "no_reset: skip the automatic /test/reset")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_SMOKE") == "1":
        return
    skip = pytest.mark.skip(reason="smoke tests run only with RUN_SMOKE=1")
    for item in items:
        if item.get_closest_marker("smoke"):
            item.add_marker(skip)
