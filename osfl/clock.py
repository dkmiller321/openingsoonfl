"""The one clock. Every 'now' in the app goes through here so tests can freeze time."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from osfl.settings import get_settings

ET = ZoneInfo("America/New_York")

_frozen: datetime | None = None
_frozen_set = False


def freeze(value: datetime | None) -> None:
    """Set (or clear, with None) the frozen time. Used by POST /test/clock."""
    global _frozen, _frozen_set
    _frozen = value.astimezone(UTC) if value is not None else None
    _frozen_set = True


def reset() -> None:
    """Forget any /test/clock override; FAKE_NOW (if set) applies again."""
    global _frozen, _frozen_set
    _frozen = None
    _frozen_set = False


def now() -> datetime:
    if _frozen_set:
        if _frozen is not None:
            return _frozen
        return datetime.now(UTC)
    fake = get_settings().fake_now
    if fake is not None:
        return fake if fake.tzinfo else fake.replace(tzinfo=UTC)
    return datetime.now(UTC)


def now_et() -> datetime:
    return now().astimezone(ET)


def today_et() -> date:
    return now_et().date()
