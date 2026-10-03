"""Pure normalisation for matching records to leads (PRD: Rules that are easy to get wrong)."""

import re

_NAME_SUFFIXES = {"LLC", "INC", "CORP", "CORPORATION", "INCORPORATED", "LTD", "PLLC", "LLP"}

_ADDRESS_WORDS = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
    "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD", "PARKWAY": "PKWY",
    "CAUSEWAY": "CSWY", "ROAD": "RD", "DRIVE": "DR", "LANE": "LN", "COURT": "CT",
    "PLACE": "PL", "HIGHWAY": "HWY", "CIRCLE": "CIR", "TERRACE": "TER", "TRAIL": "TRL",
    "SQUARE": "SQ", "EXPRESSWAY": "EXPY", "SUITE": "STE", "APARTMENT": "APT", "BUILDING": "BLDG",
}


def _collapse(text: str) -> str:
    return " ".join(text.split())


def normalise_name(name: str) -> str:
    """`Salt & Smoke BBQ, L.L.C.` -> `SALT AND SMOKE BBQ`."""
    text = name.upper().replace("&", " AND ").replace(".", "").replace("'", "")
    text = _collapse(re.sub(r"[^A-Z0-9 ]", " ", text))
    words = text.split()
    while words and words[-1] in _NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def normalise_address(address: str) -> str:
    """`1980 N Atlantic Ave Suite 101` -> `1980 N ATLANTIC AVE STE 101`."""
    text = address.upper().replace(".", "").replace("#", " STE ")
    text = _collapse(re.sub(r"[^A-Z0-9 ]", " ", text))
    return " ".join(_ADDRESS_WORDS.get(word, word) for word in text.split())


def normalise_zip(zip_code: str) -> str:
    return re.sub(r"\D", "", zip_code)[:5]


def lead_key(name: str, address: str, zip_code: str) -> str:
    return f"{normalise_name(name)}|{normalise_address(address)}|{normalise_zip(zip_code)}"


def licence_digits(licence: str | None) -> str | None:
    """`SEA1590010` -> `1590010`; the plan-review file carries the digits only."""
    if not licence:
        return None
    digits = re.sub(r"\D", "", licence)
    return digits or None
