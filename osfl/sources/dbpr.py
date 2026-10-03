"""DBPR sources: which files each source fetches, and pure parsers from bytes to records.

Real URLs and headers: docs/DECISIONS.md D1. Headers are checked against fixtures/headers/ so
a renamed or added column fails the run with a 'columns changed' alert (H2).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from osfl.formatting import format_phone
from osfl.leads.classify import PLAN_REVIEW_FILE, classify
from osfl.leads.normalise import licence_digits

HEADERS_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "headers"

WEEKLY = "dbpr_weekly"
PLAN_REVIEW = "dbpr_plan_review"
SOURCE_FILES = {
    WEEKLY: ("newfood.csv", "chgownr_food.csv"),
    PLAN_REVIEW: (PLAN_REVIEW_FILE,),
}
STAGE_FOR_SOURCE = {WEEKLY: "Licensed", PLAN_REVIEW: "Applied"}
PLAN_NAME_COLUMN = "Business (Does Business As – DBA) Name"


class HeaderMismatch(Exception):
    """The file's columns differ from the captured header."""


@dataclass
class Record:
    source: str
    file: str
    payload: dict[str, str]
    county: str
    business_name: str
    address: str
    city: str
    zip: str
    licensee: str
    phone: str
    email: str
    licence_number: str | None
    lead_type: str
    stage: str
    event_date: date | None
    source_record_id: str
    content_hash: str = field(init=False)

    def __post_init__(self) -> None:
        canonical = json.dumps([self.source, self.file, self.payload], sort_keys=True)
        self.content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def fields(self) -> dict[str, str | None]:
        """What a lead takes from this record when it is the most recent one."""
        return {
            "business_name": self.business_name,
            "address": self.address,
            "city": self.city,
            "zip": self.zip,
            "county": self.county,
            "licensee": self.licensee,
            "phone": self.phone,
            "email": self.email,
            "licence_number": self.licence_number,
            "lead_type": self.lead_type,
        }


@lru_cache(maxsize=8)
def expected_header(filename: str) -> tuple[str, ...]:
    raw = (HEADERS_DIR / filename).read_text(encoding="utf-8-sig")
    return tuple(next(csv.reader(io.StringIO(raw))))


def _read(data: bytes, filename: str) -> list[dict[str, str]]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        raise HeaderMismatch(f"{filename}: empty file")
    expected = expected_header(filename)
    if tuple(header) != expected:
        added = [c for c in header if c not in expected]
        missing = [c for c in expected if c not in header]
        raise HeaderMismatch(
            f"{filename}: unexpected columns; new: {', '.join(added) or '-'}; "
            f"missing: {', '.join(missing) or '-'}"
        )
    rows = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue
        padded = values + [""] * (len(header) - len(values))
        rows.append({col: padded[i].strip() for i, col in enumerate(header)})
    return rows


def _date(value: str) -> date | None:
    """DBPR dates are MM/DD/YYYY; a blank or malformed one means 'use the run date'."""
    try:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def _name(*candidates: str) -> str:
    """First real name; the plan-review file uses `NONE` for a missing DBA."""
    for name in candidates:
        if name and name.strip().upper() not in {"NONE", "N/A", "NA", "TBD"}:
            return name.strip()
    return ""


def _join(*parts: str) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def best_phone(*candidates: str) -> str:
    """First value that looks like a phone (10+ digits).

    Some chgownr_food.csv rows have the phone and county-code columns swapped
    ("Primary Phone Number" = "62"), so short numbers are skipped.
    """
    for value in candidates:
        if value and len(re.sub(r"\D", "", value)) >= 10:
            return format_phone(value)
    return ""


def licence_record(row: dict[str, str], filename: str) -> Record:
    return Record(
        source=WEEKLY,
        file=filename,
        payload=row,
        county=row["Location County"].strip().lower(),
        business_name=_name(row["Business Name"], row["Licensee Name"]),
        address=_join(row["Location Street Address"], row["Location Address Line 2"]),
        city=row["Location City"],
        zip=row["Location Zip Code"][:5],
        licensee=row["Licensee Name"],
        phone=best_phone(
            row["Primary Phone Number"], row["Secondary Phone Number"], row["Mailing County Code"]
        ),
        email="",
        licence_number=licence_digits(row["License Number"]),
        lead_type=classify(filename, rank=row["Rank Code"]),
        stage="Licensed",
        event_date=_date(row["Application Approval Date "]),
        source_record_id=row["Application Number"],
    )


def plan_review_record(row: dict[str, str]) -> Record:
    email = row["Facility Email Address"] or row["Contact Email Address"]
    return Record(
        source=PLAN_REVIEW,
        file=PLAN_REVIEW_FILE,
        payload=row,
        county=row["County"].strip().lower(),
        business_name=_name(row[PLAN_NAME_COLUMN], row["Mailing Name"]),
        address=row["Facility Location Address"],
        city=row["Facility Location City"],
        zip=row["Facility Location Zip Code"][:5],
        licensee=row["Mailing Name"],
        phone=best_phone(row["Facility Phone Number"], row["Contact Phone Number"],
                         row["Alternate Phone Number"]),
        email=email.lower(),
        licence_number=licence_digits(row["License Number "]),
        lead_type=classify(
            PLAN_REVIEW_FILE,
            transaction=row["Transaction"],
            facility=row["Type of Facility (Rank)"],
        ),
        stage="Applied",
        event_date=_date(row["Review Application Date"]),
        source_record_id=row["Application Number"],
    )


def record_from_row(source: str, filename: str, row: dict[str, str]) -> Record:
    """Re-derive a record from a stored raw row (used by `osfl rebuild-leads`)."""
    if source == PLAN_REVIEW:
        return plan_review_record(row)
    return licence_record(row, filename)


def parse_licence_file(data: bytes, filename: str) -> list[Record]:
    """newfood.csv / chgownr_food.csv -> Licensed records."""
    return [licence_record(row, filename) for row in _read(data, filename)]


def parse_plan_review_file(data: bytes, filename: str = PLAN_REVIEW_FILE) -> list[Record]:
    """HR_plan_review.csv -> Applied records."""
    return [plan_review_record(row) for row in _read(data, PLAN_REVIEW_FILE)]


def parse(source: str, filename: str, data: bytes) -> list[Record]:
    if source == PLAN_REVIEW:
        return parse_plan_review_file(data, filename)
    return parse_licence_file(data, filename)
