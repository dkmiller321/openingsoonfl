"""One command for the narrated demo video:
   uv run python scripts/demo/run.py [--skip-rehearse]
Clones the local real-data DB into osfl_demo, starts a demo server on :8004 (Mapbox basemaps,
no scheduler, outbox email), then TTS -> rehearse -> record -> mux ->
scripts/demo/out/openingsoon-demo.mp4. Stops the server it started."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mux  # noqa: E402
import record  # noqa: E402
import tts  # noqa: E402
from lib import clone_real_db, start_demo_server, stop  # noqa: E402


def main() -> None:
    tts.main()
    db_url = clone_real_db()
    server = start_demo_server(db_url)
    try:
        record.setup(db_url)
        if "--skip-rehearse" not in sys.argv:
            record.main(rehearse=True)
        record.main()
    finally:
        stop(server)
    mux.main()


if __name__ == "__main__":
    main()
