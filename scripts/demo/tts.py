"""One MP3 per narration segment with ElevenLabs. Cached by text + voice, so re-runs only pay
for segments whose text changed.   uv run python scripts/demo/tts.py"""

from __future__ import annotations

import hashlib
import json
import sys

import httpx

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from flow import NARRATION  # noqa: E402
from lib import AUDIO, VOICE, dotenv, duration_seconds  # noqa: E402


def main() -> None:
    key = dotenv().get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is missing from OpeningSoonFL/.env")
    AUDIO.mkdir(parents=True, exist_ok=True)
    manifest_path = AUDIO / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for seg_id, text in NARRATION.items():
        path = AUDIO / f"{seg_id}.mp3"
        digest = hashlib.sha256(
            f"{VOICE['voice_id']}|{VOICE['model_id']}|{text}".encode()
        ).hexdigest()
        if manifest.get(seg_id, {}).get("hash") != digest or not path.exists():
            response = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE['voice_id']}",
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": key, "accept": "audio/mpeg"},
                json={"text": text, "model_id": VOICE["model_id"],
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                timeout=120,
            )
            if response.status_code != 200:
                raise SystemExit(f"ElevenLabs {response.status_code} for {seg_id}: {response.text}")
            path.write_bytes(response.content)
            print(f"tts: generated {seg_id}")
        manifest[seg_id] = {"hash": digest, "duration": duration_seconds(path)}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    total = sum(m["duration"] for m in manifest.values() if m)
    print(f"tts: {len(NARRATION)} clips, {total:.1f}s of narration")


if __name__ == "__main__":
    main()
