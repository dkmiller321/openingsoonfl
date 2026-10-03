"""Display formats shared by the UI, the CSVs and the digests (E2E_TESTS.md section 1.5)."""

import re
from datetime import date

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
LEAD_TYPE_LABELS = {"new": "New", "ownership_change": "Ownership change", "mobile": "Food truck"}


def long_date(value: date | None) -> str:
    """`Sep 7, 2026`."""
    if value is None:
        return ""
    return f"{MONTHS[value.month - 1]} {value.day}, {value.year}"


def lead_type_label(lead_type: str) -> str:
    return LEAD_TYPE_LABELS.get(lead_type, lead_type)


def days_ahead_label(days: int | None) -> str:
    if days is None:
        return "—"
    return f"{plural(days, 'day')} ahead"


def format_phone(raw: str | None) -> str:
    """Ten-digit US numbers become `321-555-0101`; anything else is kept as written."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return raw.strip()


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"
