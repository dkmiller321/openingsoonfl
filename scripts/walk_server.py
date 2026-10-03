"""Start/stop the playwright-headless walkthrough server (E2E_TESTS.md section 5).

Port 8002, database osfl_walk, the e2e test env otherwise. Never run it while pytest runs.
Usage: uv run python scripts/walk_server.py start|stop
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from e2e.conftest import (  # noqa: E402
    _dotenv,
    ensure_database,
    make_test_env,
    start_app,
    wait_healthy,
)

PORT = 8002
PID_FILE = ROOT / "logs" / "walk.pid"
DEFAULT_WALK_DB = "postgresql+psycopg://osfl:change-me@127.0.0.1:55433/osfl_walk"


def start() -> None:
    import subprocess

    db_url = (
        os.environ.get("WALK_DATABASE_URL") or _dotenv().get("WALK_DATABASE_URL")
        or DEFAULT_WALK_DB
    )
    ensure_database(db_url)
    env = make_test_env(PORT, db_url)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env,
                   check=True, capture_output=True)
    proc = start_app(env, PORT, "walk.log")
    wait_healthy(f"http://127.0.0.1:{PORT}", proc)
    PID_FILE.write_text(str(proc.pid))
    print(f"walkthrough server on http://127.0.0.1:{PORT} (pid {proc.pid})")


def stop() -> None:
    import subprocess

    if not PID_FILE.exists():
        print("no walkthrough server running")
        return
    pid = int(PID_FILE.read_text())
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        os.kill(pid, 15)
    PID_FILE.unlink()
    print(f"stopped walkthrough server (pid {pid})")


if __name__ == "__main__":
    {"start": start, "stop": stop}[sys.argv[1]]()
