"""Places each narration clip at its segment's timestamp and muxes it onto the recording.
   uv run python scripts/demo/mux.py   -> scripts/demo/out/openingsoon-demo.mp4"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow import NARRATION  # noqa: E402
from lib import AUDIO, OUT, tool  # noqa: E402


def main() -> None:
    timeline = json.loads((OUT / "timeline.json").read_text())
    starts = {s["id"]: s["start"] for s in timeline["segments"]}
    missing = [i for i in NARRATION if i not in starts]
    if missing:
        raise SystemExit(f"timeline has no segment(s) {missing}; re-record")
    offset = max(0.0, min(starts.values()) - 0.4)  # skip page-load frames
    length = timeline["end"] - offset
    inputs = ["-ss", f"{offset:.3f}", "-i", str(OUT / "raw.webm")]
    filters = []
    ids = list(NARRATION)
    for i, seg_id in enumerate(ids):
        inputs += ["-i", str(AUDIO / f"{seg_id}.mp3")]
        ms = round((starts[seg_id] - offset) * 1000)
        filters.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
    filters.append(
        "".join(f"[a{i}]" for i in range(len(ids)))
        + f"amix=inputs={len(ids)}:normalize=0:dropout_transition=0,apad[aout]"
    )
    filters.append(
        f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={length - 0.8:.3f}:d=0.8,format=yuv420p[vout]"
    )
    target = OUT / "openingsoon-demo.mp4"
    subprocess.run(
        [tool("ffmpeg"), "-y", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "25",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(target)],
        check=True,
    )
    print(f"mux: wrote {target} ({length:.1f}s)")


if __name__ == "__main__":
    main()
