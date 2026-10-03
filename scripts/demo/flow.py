"""The full feature tour: narration (one line per segment) and the browser steps for each.

Numbers in the narration come from the local real-data database (Brevard, 2026-10-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from record import Helper

NARRATION: dict[str, str] = {
    "intro": (
        "This is OpeningSoon FL. It finds new restaurants in Brevard County weeks before they "
        "open, and turns them into sales leads for the vendors who serve them."
    ),
    "sources": (
        "Every morning it downloads three free files from the state of Florida: plan reviews, "
        "new licences, and ownership changes. Plan reviews are the early signal. They're filed "
        "before construction even starts."
    ),
    "leads": (
        "Each restaurant becomes one lead, no matter how many records mention it. Right now "
        "there are two hundred and fifty one in Brevard."
    ),
    "filter": (
        "Filtering to plan review shows the restaurants that haven't opened yet. These are the "
        "ones vendors want to hear about first."
    ),
    "export": "Any list can be searched, and downloaded as a spreadsheet for a sales team.",
    "detail": (
        "Here's a single lead. The plan review was filed on August twenty fifth, and the licence "
        "came through on September twenty eighth. We saw it thirty four days early."
    ),
    "contacts": (
        "The plan review includes the owner's phone number and email, so a vendor can reach the "
        "decision maker directly. And every fact links back to the original state record."
    ),
    "map": (
        "The map puts every lead in context. Each icon is a guess at the cuisine, based on the "
        "name. Amber means still in plan review, and green means licensed."
    ),
    "play": (
        "Press play, and watch the last ninety days unfold, as new restaurants appear week by "
        "week."
    ),
    "radius": (
        "Most vendors cover a service area. Pick a town and a radius, and you only see what's "
        "nearby."
    ),
    "popup": "Click any restaurant to see its stage, its address, and how to reach the owner.",
    "basemap": "The map style can switch between light, streets, outdoors, and satellite views.",
    "board": (
        "The pipeline board shows the same leads in two columns: still in plan review, and "
        "licensed."
    ),
    "vendors": (
        "Vendors subscribe by category and county, and choose a weekly or a daily email. They "
        "never need to log in."
    ),
    "digest": (
        "This is what a vendor receives: every new restaurant they haven't seen yet, with phone "
        "and email, and a spreadsheet attached. Each lead reaches a vendor only once."
    ),
    "test_send": "One click sends me a test copy, so I can check it before it goes out.",
    "health": (
        "The sources page tracks every import. If a file fails, comes back empty, or changes "
        "its columns, I get an email about it."
    ),
    "appearance": (
        "It's built for daily use, with light and dark themes, and six color palettes, "
        "including one that's color blind safe."
    ),
    "outro": "OpeningSoon FL. Brevard's new restaurants, weeks before they open.",
}


def run(h: Helper) -> None:
    page, by = h.page, h.by

    h.segment("intro", lambda: (
        h.move_to(by("stat-new-this-week")), h.pause(900),
        h.move_to(by("stat-applied")), h.pause(900),
        h.move_to(by("stat-active-vendors")),
    ))

    h.segment("sources", lambda: (
        h.move_to(page.locator('[data-testid="source-last-run"][data-source="dbpr_plan_review"]')),
        h.pause(1200),
        h.move_to(page.locator('[data-testid="source-last-run"][data-source="dbpr_weekly"]')),
    ))

    def leads() -> None:
        h.click(by("nav-leads"))
        by("leads-table").wait_for()
        h.pause(800)
        h.move_to(by("leads-count"))
        h.pause(800)
        h.scroll(500)
        h.pause(600)
        h.scroll(-500)
    h.segment("leads", leads)

    def filter_applied() -> None:
        h.click(by("filter-stage"))
        by("filter-stage").select_option("Applied")
        h.pause(500)
        h.click(by("filter-apply"))
        by("leads-table").wait_for()
        h.pause(700)
        h.move_to(by("lead-row").nth(0))
        h.pause(500)
        h.move_to(by("lead-row").nth(2))
    h.segment("filter", filter_applied)

    def export() -> None:
        h.type(by("filter-search"), "bbq")
        h.click(by("filter-apply"))
        by("leads-table").wait_for()
        h.pause(900)
        h.move_to(by("export-csv"))
        h.pause(500)
        with page.expect_download():
            by("export-csv").click()
    h.segment("export", export)

    def detail() -> None:
        page.goto(f"{h.base_url}/leads?q=pops")
        h.click(by("lead-name").first)
        by("lead-detail-name").wait_for()
        h.pause(600)
        h.move_to(by("lead-detail-days-ahead"))
        h.pause(800)
        h.move_to(by("timeline-event").nth(0))
        h.pause(900)
        h.move_to(by("timeline-event").nth(1))
    h.segment("detail", detail)

    def contacts() -> None:
        h.move_to(by("lead-detail-phone"))
        h.pause(800)
        h.move_to(by("lead-detail-email"))
        h.pause(800)
        h.move_to(by("raw-record").first, y=40)
        h.scroll(380)
    h.segment("contacts", contacts)

    def map_view() -> None:
        h.click(by("nav-map"))
        by("map-list-item").first.wait_for()
        page.wait_for_load_state("networkidle")
        h.pause(1200)
        h.move_to(page.locator(".cluster").first)
        h.pause(800)
        h.move_to(by("map-list-item").nth(1))
        h.pause(600)
        h.move_to(page.locator(".legend"))
    h.segment("map", map_view)

    def play() -> None:
        h.click(by("map-play"))
        page.wait_for_function(
            "document.querySelector('[data-testid=map-slider]').value === '0' && "
            "!document.querySelector('[data-testid=map-play]').textContent.includes('Pause')",
            timeout=30_000,
        )
    h.segment("play", play)

    def radius() -> None:
        h.click(by("map-center"))
        by("map-center").select_option(label="Melbourne")
        h.pause(400)
        h.click(by("map-radius"))
        by("map-radius").select_option("5")
        h.pause(900)
        page.locator("#map").evaluate("el => el.scrollIntoView({block: 'center'})")
        h.move_to(page.locator(".leaflet-interactive").first)
    h.segment("radius", radius)

    def popup() -> None:
        h.click(by("map-list-item").nth(1))
        by("map-popup").wait_for()
        page.wait_for_load_state("networkidle")
        h.pause(800)
        h.move_to(by("map-popup-link"))
    h.segment("popup", popup)

    def basemap() -> None:
        for style in ("streets", "outdoors", "satellite"):
            h.click(by("map-basemap"))
            by("map-basemap").select_option(style)
            page.wait_for_load_state("networkidle")
            h.pause(1100)
        by("map-basemap").select_option("auto")
    h.segment("basemap", basemap)

    def board() -> None:
        h.click(by("nav-board"))
        by("board-col-applied").wait_for()
        h.pause(700)
        h.move_to(by("board-count-applied"))
        h.pause(700)
        h.move_to(by("board-count-licensed"))
        h.pause(500)
        h.scroll(400)
    h.segment("board", board)

    def vendors() -> None:
        h.click(by("nav-vendors"))
        by("vendor-row").first.wait_for()
        h.pause(600)
        h.move_to(by("vendor-row").nth(0))
        h.pause(700)
        h.move_to(by("vendor-row").nth(1))
    h.segment("vendors", vendors)

    def digest() -> None:
        h.click(by("vendor-row").filter(has_text="Space Coast POS").get_by_test_id(
            "digest-preview-link"))
        by("digest-preview").wait_for()
        h.pause(1200)
        h.scroll(450)
        h.pause(1200)
        h.scroll(450)
    h.segment("digest", digest)

    def test_send() -> None:
        h.scroll(-2000)
        h.pause(300)
        h.click(by("digest-send-test"))
        by("digest-test-sent").wait_for()
        h.move_to(by("digest-test-sent"))
    h.segment("test_send", test_send)

    def health() -> None:
        h.click(by("nav-sources"))
        by("source-row").first.wait_for()
        h.pause(700)
        h.move_to(by("source-row").nth(0), y=30)
        h.pause(900)
        h.move_to(by("source-row").nth(1), y=30)
    h.segment("health", health)

    def appearance() -> None:
        h.click(by("nav-map"))
        by("map-list-item").first.wait_for()
        h.pause(500)
        h.click(by("appearance-toggle"))
        h.pause(400)
        h.click(by("theme-dark"))
        page.wait_for_load_state("networkidle")
        h.pause(800)
        h.click(by("palette-ocean"))
        h.pause(800)
        h.click(by("palette-sunset"))
        h.pause(800)
        h.click(by("palette-cb"))
        h.pause(600)
        h.click(by("palette-ocean"))
    h.segment("appearance", appearance)

    def outro() -> None:
        page.keyboard.press("Escape")
        page.mouse.move(640, 700, steps=20)
        h.pause(400)
    h.segment("outro", outro)
