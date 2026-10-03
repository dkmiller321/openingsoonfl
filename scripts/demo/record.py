"""Replays the tour in Chromium at 1280x720, records it, and logs when each segment starts.
Each segment is held at least as long as its voice clip, so narration never overlaps.
   uv run python scripts/demo/record.py [--rehearse]  -> out/raw.webm + out/timeline.json"""

from __future__ import annotations

import json
import shutil
import sys
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import psycopg
from playwright.sync_api import Locator, Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow  # noqa: E402
from lib import ADMIN_PASSWORD, AUDIO, BASE_URL, OUT  # noqa: E402

SIZE = {"width": 1280, "height": 720}
GAP_S = 0.6

# Visible cursor + click squeeze: Playwright's video doesn't draw the pointer.
CURSOR_SCRIPT = """
(() => {
  const install = () => {
    if (document.getElementById('__demo-cursor')) return;
    const c = document.createElement('div');
    c.id = '__demo-cursor';
    c.style.cssText = 'position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;' +
      'border-radius:50%;background:rgba(0,0,0,.55);border:2px solid #fff;' +
      'box-shadow:0 1px 4px rgba(0,0,0,.35);pointer-events:none;z-index:2147483647;' +
      'transition:transform .12s ease;transform:translate(-100px,-100px)';
    document.documentElement.appendChild(c);
    let x = -100, y = -100;
    addEventListener('mousemove', e => { x = e.clientX; y = e.clientY;
      c.style.transform = `translate(${x}px,${y}px)`; }, true);
    addEventListener('mousedown', () => {
      c.style.transform = `translate(${x}px,${y}px) scale(.7)`; }, true);
    addEventListener('mouseup', () => { c.style.transform = `translate(${x}px,${y}px)`; }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', install);
  else install();
})();
"""


class Helper:
    def __init__(self, page: Page, rehearse: bool, durations: dict[str, Any]) -> None:
        self.page = page
        self.rehearse = rehearse
        self.durations = durations
        self.base_url = BASE_URL
        self.t0 = time.monotonic()
        self.timeline: list[dict[str, Any]] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def by(self, testid: str) -> Locator:
        return self.page.get_by_test_id(testid)

    def pause(self, ms: int) -> None:
        if not self.rehearse:
            self.page.wait_for_timeout(ms)

    def segment(self, seg_id: str, actions: Callable[[], Any]) -> None:
        if seg_id not in flow.NARRATION:
            raise RuntimeError(f"segment {seg_id!r} has no narration")
        start = self.now()
        self.timeline.append({"id": seg_id, "start": start})
        print(f"record: {seg_id} @ {start:.2f}s")
        actions()
        if self.rehearse:
            return
        hold = start + self.durations[seg_id]["duration"] + GAP_S - self.now()
        if hold > 0:
            self.page.wait_for_timeout(hold * 1000)

    def move_to(self, locator: Locator, x: float | None = None, y: float | None = None) -> None:
        locator.wait_for(state="visible")
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if box is None:
            raise RuntimeError("element has no box")
        self.page.mouse.move(
            box["x"] + (x if x is not None else box["width"] / 2),
            box["y"] + (y if y is not None else box["height"] / 2),
            steps=1 if self.rehearse else 25,
        )
        self.pause(150)

    def click(self, locator: Locator) -> None:
        self.move_to(locator)
        locator.click()

    def type(self, locator: Locator, text: str, delay: int = 60) -> None:
        self.click(locator)
        locator.fill("")
        locator.press_sequentially(text, delay=0 if self.rehearse else delay)

    def scroll(self, dy: int) -> None:
        steps = 1 if self.rehearse else 12
        for _ in range(steps):
            self.page.mouse.wheel(0, dy / steps)
            self.pause(25)


def setup(db_url: str) -> None:
    """Three demo vendors; older leads count as already delivered to Space Coast POS,
    so its next digest shows only the last ten days, as a real subscriber's would."""
    api = httpx.Client(base_url=BASE_URL, timeout=30)
    api.post("/login", data={"password": ADMIN_PASSWORD})
    plain = db_url.replace("+psycopg", "")
    with psycopg.connect(plain) as conn:
        cats = dict(conn.execute("select name, id from categories").fetchall())
    for name, emails, cat, cadence in (
        ("Space Coast POS", "sales@spacecoastpos.example", "POS", "weekly"),
        ("Brevard Pest Pros", "hello@brevardpest.example", "Pest control", "daily"),
        ("Harbor Restaurant Supply", "orders@harborsupply.example", "Equipment", "weekly"),
    ):
        response = api.post("/vendors/new", data={
            "name": name, "emails": emails, "category_id": str(cats[cat]),
            "counties": "brevard", "cadence": cadence, "active": "1",
        })
        if response.status_code >= 400:
            raise RuntimeError(f"vendor {name}: HTTP {response.status_code}")
    with psycopg.connect(plain) as conn:
        vendor_id, today = conn.execute(
            "select id, now()::date from vendors where name = 'Space Coast POS'"
        ).fetchone()
        digest_id = conn.execute(
            "insert into digests (vendor_id, kind, period_key, sent_at, lead_count) "
            "values (%s, 'scheduled', 'demo-history', now(), 0) returning id", (vendor_id,)
        ).fetchone()[0]
        conn.execute(
            "insert into deliveries (vendor_id, lead_id, digest_id, delivered_at) "
            "select %s, id, %s, now() from leads where first_seen < %s",
            (vendor_id, digest_id, today - timedelta(days=10)),
        )


def main(rehearse: bool = False) -> None:
    durations: dict[str, Any] = {}
    if not rehearse:
        durations = json.loads((AUDIO / "manifest.json").read_text())
        missing = [i for i in flow.NARRATION if i not in durations]
        if missing:
            raise SystemExit(f"no audio for {missing}; run tts.py first")
    OUT.mkdir(parents=True, exist_ok=True)
    video_dir = OUT / "video-tmp"
    shutil.rmtree(video_dir, ignore_errors=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport=SIZE, device_scale_factor=1, color_scheme="light", accept_downloads=True,
            **({} if rehearse else {"record_video_dir": str(video_dir), "record_video_size": SIZE}),
        )
        context.add_init_script(CURSOR_SCRIPT)
        context.add_cookies([{"name": "osfl_appearance", "value": "light:classic",
                              "url": BASE_URL}])
        page = context.new_page()  # the video starts here, so the timeline clock does too
        h = Helper(page, rehearse, durations)
        page.set_default_timeout(30_000)
        page.context.request.post(f"{BASE_URL}/login", form={"password": ADMIN_PASSWORD})
        try:
            page.goto(f"{BASE_URL}/")
            h.by("stat-new-this-week").wait_for()
            page.wait_for_load_state("networkidle")
            h.pause(600)
            flow.run(h)
            h.pause(1500)
        except Exception:
            page.screenshot(path=str(OUT / "failure.png"))
            print("record: failed, screenshot at scripts/demo/out/failure.png")
            raise
        finally:
            end = h.now()
            video = page.video
            context.close()
            browser.close()
            if not rehearse and video:
                shutil.copyfile(video.path(), OUT / "raw.webm")
                shutil.rmtree(video_dir, ignore_errors=True)
                (OUT / "timeline.json").write_text(
                    json.dumps({"end": end, "segments": h.timeline}, indent=2))
    print(f"record: done ({end:.1f}s)")
