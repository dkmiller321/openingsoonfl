"""Required unit tests (E2E_TESTS.md section 4)."""

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from osfl.digests.period import digest_period
from osfl.health import RunInfo, health_status
from osfl.leads.classify import classify
from osfl.leads.matcher import days_ahead
from osfl.leads.normalise import lead_key, licence_digits, normalise_address, normalise_name
from osfl.sources.fetch import FetchError, LiveFetcher


# UT-01
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Indian River Pho LLC", "INDIAN RIVER PHO"),
        ("Salt & Smoke BBQ, L.L.C.", "SALT AND SMOKE BBQ"),
        ("Coastal Tacos Inc", "COASTAL TACOS"),
    ],
)
def test_ut01_normalise_name(raw: str, expected: str) -> None:
    assert normalise_name(raw) == expected


# UT-02
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2235 N. Courtenay Parkway", "2235 N COURTENAY PKWY"),
        ("1980 N Atlantic Ave Suite 101", "1980 N ATLANTIC AVE STE 101"),
        ("210 West Cocoa Beach Causeway", "210 W COCOA BEACH CSWY"),
    ],
)
def test_ut02_normalise_address(raw: str, expected: str) -> None:
    assert normalise_address(raw) == expected


# UT-03
def test_ut03_lead_key() -> None:
    p1 = lead_key("Indian River Pho LLC", "2235 N. Courtenay Parkway", "32953")
    w2_1 = lead_key("INDIAN RIVER PHO", "2235 N COURTENAY PKWY", "32953")
    assert p1 == w2_1
    w1_1 = lead_key("SALT & SMOKE BBQ", "1450 N HARBOR CITY BLVD", "32935")
    other_zip = lead_key("SALT & SMOKE BBQ", "1450 N HARBOR CITY BLVD", "32901")
    assert w1_1 != other_zip


# UT-09
def test_ut09_licence_digits() -> None:
    assert licence_digits("SEA1590010") == "1590010"
    assert licence_digits("1590010") == "1590010"
    assert licence_digits("") is None
    assert licence_digits(None) is None


# UT-04
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"file": "newfood.csv", "rank": "SEAT"}, "new"),
        ({"file": "newfood.csv", "rank": "NOST"}, "new"),
        ({"file": "chgownr_food.csv", "rank": "SEAT"}, "ownership_change"),
        ({"file": "newfood.csv", "rank": "MFDV"}, "mobile"),
        ({"file": "newfood.csv", "rank": "VEND"}, "ignored"),
        ({"file": "newfood.csv", "rank": "SEAT"}, "new"),
        ({"file": "newfood.csv", "rank": "CATR"}, "ignored"),
        ({"file": "chgownr_food.csv", "rank": "MFDV"}, "ownership_change"),
        ({"file": "chgownr_food.csv", "rank": "CATR"}, "ignored"),
        ({"file": "newfood.csv", "rank": "HTDG"}, "mobile"),
        ({"file": "HR_plan_review.csv",
          "transaction": "1034/Plan Review and Initial (COMBO SEAT)"}, "new"),
        ({"file": "HR_plan_review.csv",
          "transaction": "1034/Plan Review and Initial (COMBO)"}, "new"),
        ({"file": "HR_plan_review.csv", "transaction": "1030/Initial Plan Review"}, "new"),
        ({"file": "HR_plan_review.csv",
          "transaction": "1036/Plan Review and Initial (COMBO MFDV)"}, "mobile"),
        ({"file": "HR_plan_review.csv", "transaction": "1030/Initial Hot Dog Plan Review"},
         "mobile"),
        ({"file": "HR_plan_review.csv", "transaction": "3021/Request to Change Owner (MFDV)"},
         "ownership_change"),
        ({"file": "HR_plan_review.csv", "transaction": "3027/Request Plan Review"}, "ignored"),
        ({"file": "HR_plan_review.csv", "transaction": "1030/Initial Plan Review (SEAT)",
          "facility": "Catering"}, "ignored"),
    ],
)
def test_ut04_classify(kwargs: dict[str, str], expected: str) -> None:
    assert classify(**kwargs) == expected


# UT-05
class FakeSleep:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_ut05_fetcher_politeness() -> None:
    seen: list[tuple[float, str]] = []
    fake = FakeSleep()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((fake.now, request.headers["user-agent"]))
        return httpx.Response(200, content=b"ok")

    fetcher = LiveFetcher(
        user_agent="OpeningSoonFL/test", min_interval_s=2.0,
        transport=httpx.MockTransport(handler), sleep=fake.sleep, monotonic=fake.monotonic,
    )
    fetcher.fetch("a.csv", "https://example.invalid/a.csv")
    fetcher.fetch("b.csv", "https://example.invalid/b.csv")
    fetcher.fetch("c.csv", "https://example.invalid/c.csv")
    times = [t for t, _ in seen]
    assert all(b - a >= 2.0 for a, b in zip(times, times[1:], strict=False))
    assert {ua for _, ua in seen} == {"OpeningSoonFL/test"}


def test_ut05_fetcher_retries_then_raises() -> None:
    fake = FakeSleep()
    calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(fake.now)
        return httpx.Response(500)

    fetcher = LiveFetcher(
        user_agent="ua", min_interval_s=2.0, transport=httpx.MockTransport(handler),
        sleep=fake.sleep, monotonic=fake.monotonic,
    )
    with pytest.raises(FetchError, match=r"x\.csv: HTTP 500"):
        fetcher.fetch("x.csv", "https://example.invalid/x.csv")
    assert len(calls) == 4  # first try + 3 retries
    gaps = [b - a for a, b in zip(calls, calls[1:], strict=False)]
    assert gaps == sorted(gaps) and gaps[0] < gaps[-1]


# UT-06
def test_ut06_digest_period() -> None:
    assert digest_period(datetime(2026, 9, 7, 11, 0, tzinfo=UTC), "weekly") == "2026-W37"
    sunday_late = datetime(2026, 9, 13, 23, 59, tzinfo=UTC) + timedelta(hours=4)
    assert digest_period(sunday_late, "weekly") == "2026-W37"
    assert digest_period(datetime(2026, 9, 29, 3, 59, tzinfo=UTC), "daily") == "2026-09-28"


# UT-07
def _run(days_ago: float, status: str = "ok", problem: str | None = None,
         now: datetime = datetime(2026, 10, 6, 12, tzinfo=UTC)) -> RunInfo:
    return RunInfo(finished_at=now - timedelta(days=days_ago), status=status, problem=problem)


def test_ut07_health_status() -> None:
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    assert health_status("dbpr_weekly", [], now) == "amber"
    assert health_status("dbpr_weekly", [_run(8)], now) == "green"
    assert health_status("dbpr_weekly", [_run(8.01)], now) == "amber"
    assert health_status("dbpr_plan_review", [_run(1.4)], now) == "green"
    assert health_status("dbpr_plan_review", [_run(1.6)], now) == "amber"
    assert health_status("dbpr_weekly", [_run(0.1, "failed", "run failed")], now) == "red"
    assert health_status("dbpr_weekly", [_run(0.1, "ok", "zero rows")], now) == "red"
    assert health_status("dbpr_weekly", [_run(0.1, "failed", "columns changed")], now) == "red"
    # newest run first: a good run after a failure is green again
    recovered = [_run(0.1), _run(1, "failed", "run failed")]
    assert health_status("dbpr_weekly", recovered, now) == "green"


# UT-08
def test_ut08_days_ahead() -> None:
    assert days_ahead([("Applied", date(2026, 9, 1)), ("Licensed", date(2026, 9, 29))]) == 28
    assert days_ahead([("Licensed", date(2026, 9, 29))]) == 0
    assert days_ahead([("Applied", date(2026, 9, 1))]) is None
