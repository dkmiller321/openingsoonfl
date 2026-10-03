"""Shared paths, tools and the demo server for the narrated demo video (ported from Loom)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

DEMO_DIR = Path(__file__).resolve().parent
ROOT = DEMO_DIR.parent.parent
OUT = DEMO_DIR / "out"
AUDIO = OUT / "audio"
PORT = 8004
BASE_URL = os.environ.get("DEMO_BASE_URL", f"http://127.0.0.1:{PORT}")
DEMO_DB = "osfl_demo"
ADMIN_PASSWORD = "demo-admin-pw"

# Same premade voice and model as the Loom demo videos.
VOICE = {"voice_id": "XrExE9yKIg1WjnnlVkGX", "model_id": "eleven_multilingual_v2"}

WINGET_FFMPEG_BIN = Path(
    r"C:\Users\dkmil\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin"
)


def dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def tool(name: str) -> str:
    """ffmpeg / ffprobe from PATH, else the winget install."""
    found = shutil.which(name)
    if found:
        return found
    fallback = WINGET_FFMPEG_BIN / f"{name}.exe"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError(f"{name} not found on PATH or at {fallback}")


def duration_seconds(path: Path) -> float:
    out = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _answers(url: str) -> bool:
    try:
        return httpx.get(url, timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def clone_real_db() -> str:
    """Copy the local real-data database (osfl) into osfl_demo, so the demo never touches it."""
    env = dotenv()
    user = env.get("POSTGRES_USER", "osfl")
    script = (
        f"dropdb --if-exists -U {user} {DEMO_DB} && createdb -U {user} {DEMO_DB} && "
        f"pg_dump -U {user} {env.get('POSTGRES_DB', 'osfl')} | psql -q -U {user} {DEMO_DB}"
    )
    subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "sh", "-c", script],
        cwd=ROOT, check=True, capture_output=True,
    )
    host_port = env.get("POSTGRES_HOST_PORT", "55433")
    password = env.get("POSTGRES_PASSWORD", "change-me")
    return f"postgresql+psycopg://{user}:{password}@127.0.0.1:{host_port}/{DEMO_DB}"


def start_demo_server(db_url: str) -> subprocess.Popen[bytes]:
    if _port_in_use(PORT):
        raise RuntimeError(f"port {PORT} is busy; stop the old demo server first")
    env_file = dotenv()
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSFL_")}
    env.update({
        "OSFL_ENV_FILE": "",
        "DATABASE_URL": db_url,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        "SESSION_SECRET": "demo-session-secret-0123456789",
        "SCHEDULER_ENABLED": "0",
        "TEST_ROUTES": "0",
        "EMAIL_MODE": "outbox",
        "SOURCE_MODE": "fixture",
        "GEOCODER_MODE": "off",
        "MAPBOX_TOKEN": env_file.get("MAPBOX_TOKEN", ""),
        "OPERATOR_EMAIL": "you@openingsoonfl.com",
        "OPERATOR_POSTAL_ADDRESS": "OpeningSoon FL, PO Box 1000, Melbourne, FL 32901",
        "APP_BASE_URL": BASE_URL,
        "MAX_VENDORS_PER_CATEGORY": "3",
        "PYTHONIOENCODING": "utf-8",
    })
    OUT.mkdir(parents=True, exist_ok=True)
    log = (OUT / "demo-server.log").open("wb")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "osfl.main:app", "--host", "127.0.0.1",
         "--port", str(PORT)],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 60
    while not _answers(f"{BASE_URL}/health"):
        if proc.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError("demo server did not start; see scripts/demo/out/demo-server.log")
        time.sleep(0.5)
    return proc


def stop(proc: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
