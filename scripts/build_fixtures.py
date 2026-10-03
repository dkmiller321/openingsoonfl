"""Build every DBPR fixture (docs/E2E_TESTS.md section 1.4) from the real captured headers.

Canonical fixtures are written from the tables below. The real samples are trimmed from the
spike downloads in logs/spike/ (git-ignored); they are committed, so this script only needs
those downloads when re-trimming. Run: uv run python scripts/build_fixtures.py
"""

from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures"
HEADERS = FIX / "headers"
WEEKLY = FIX / "dbpr_weekly"
PLAN = FIX / "dbpr_plan_review"
SPIKE = ROOT / "logs" / "spike"

COUNTY_CODES = {"Brevard": ("15", "D4"), "Orange": ("58", "D4")}
APP_TYPES = {
    "SEAT": "Plan Review and Initial (COMBO SEAT)",
    "NOST": "Plan Review and Initial (COMBO NO SEAT)",
    "MFDV": "Plan Review and Initial (COMBO MFDV)",
    "VEND": "Issue Initial License",
    "CATR": "Issue Initial License",
}


def header(name: str) -> list[str]:
    raw = (HEADERS / f"{name}.csv").read_text(encoding="utf-8-sig")
    return next(csv.reader(io.StringIO(raw)))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    """Write like DBPR does: every field quoted, CRLF line endings, UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(col, "") for col in columns])
    path.write_bytes(buf.getvalue().encode("utf-8"))


# --- licence rows (newfood.csv / chgownr_food.csv share one header) -------------------------

def licence_row(
    n: int, business: str, licensee: str, street: str, city: str, zip_: str, county: str,
    rank: str, lic: str, approved: str, phone: str, change_owner: bool = False,
) -> dict[str, str]:
    code, district = COUNTY_CODES[county]
    return {
        "Application Number": f"{9000000 + n}",
        "Application Type": "Approve Change Owner Request" if change_owner else APP_TYPES[rank],
        "Application Approval Date ": approved,
        "Board Code": "200",
        "License Type Code": "2010",
        "Licensee Name": licensee,
        "Rank Code": rank,
        "Mailing Name": licensee,
        "Mailing Street Address": street,
        "Mailing City": city,
        "Mailing State Code": "FL",
        "Mailing Zip Code": zip_,
        "Primary Phone Number": phone,
        "Mailing County Code": code,
        "Business Name": business,
        "Filler": " ",
        "Location Street Address": street,
        "Location City": city,
        "Location State Code": "FL",
        "Location Zip Code": zip_,
        "Location County Code": code,
        "Location County": county,
        "District": district,
        "License Number": lic,
        "Primary Status Code": "20",
        "Secondary Status Code": "20",
        "Number of Seats": "40" if rank == "SEAT" else "0",
    }


W1_1 = licence_row(1, "SALT & SMOKE BBQ", "SALT & SMOKE BBQ LLC", "1450 N HARBOR CITY BLVD",
                   "MELBOURNE", "32935", "Brevard", "SEAT", "SEA1590001", "09/22/2026",
                   "321-555-0101")
W1_2 = licence_row(2, "COASTAL TACOS", "COASTAL TACOS INC", "210 W COCOA BEACH CSWY",
                   "COCOA BEACH", "32931", "Brevard", "NOST", "NOS1590002", "09/23/2026",
                   "321-555-0102")
W1_3 = licence_row(3, "THE ROCKET DINER", "ROCKET DINER HOLDINGS LLC", "3500 S WASHINGTON AVE",
                   "TITUSVILLE", "32780", "Brevard", "SEAT", "SEA1590003", "09/24/2026",
                   "321-555-0103", change_owner=True)
W1_4 = licence_row(4, "SPACECOAST WAFFLES", "SPACECOAST WAFFLES LLC", "1100 MALABAR RD SE",
                   "PALM BAY", "32907", "Brevard", "MFDV", "MFD1590004", "09/25/2026",
                   "321-555-0104")
W1_5 = licence_row(5, "HARBOR VENDING CO", "HARBOR VENDING CO", "100 E NEW HAVEN AVE",
                   "MELBOURNE", "32901", "Brevard", "VEND", "VEN1590005", "09/21/2026", "")
W1_6 = licence_row(6, "LAKE EOLA RAMEN", "LAKE EOLA RAMEN LLC", "50 E CENTRAL BLVD",
                   "ORLANDO", "32801", "Orange", "SEAT", "SEA5890006", "09/22/2026",
                   "407-555-0106")
W2_1 = licence_row(7, "INDIAN RIVER PHO", "INDIAN RIVER PHO LLC", "2235 N COURTENAY PKWY",
                   "MERRITT ISLAND", "32953", "Brevard", "SEAT", "SEA1590007", "09/29/2026",
                   "321-555-0201")
W2_2 = licence_row(8, "COCOA VILLAGE CREPERIE", "COCOA VILLAGE CREPERIE LLC", "401 DELANNOY AVE",
                   "COCOA", "32922", "Brevard", "NOST", "NOS1590008", "09/30/2026",
                   "321-555-0202")
W2_3 = licence_row(9, "SPACE COAST CATERING", "SPACE COAST CATERING LLC", "77 CLEARLAKE RD",
                   "COCOA", "32922", "Brevard", "CATR", "CAT1590009", "09/28/2026", "")
SALTY_BAGEL = licence_row(10, "SALTY BAGEL", "EMERALD HALLI LLC", "223 W HIBISCUSS BLVD",
                          "MELBOURNE", "32901", "Brevard", "SEAT", "SEA1590010", "09/15/2026",
                          "321-555-0110")


# --- plan-review rows ----------------------------------------------------------------------

def plan_row(
    n: int, dba: str, street: str, city: str, zip_: str, applied: str, transaction: str,
    phone: str, email: str, mailing: str, licence: str = "", status: str = "In process",
) -> dict[str, str]:
    return {
        "Region (District)": "D4",
        "County": "Brevard",
        "Business (Does Business As – DBA) Name": dba,
        "Facility Location Address": street,
        "Facility Location City": city,
        "Facility Location Zip Code": zip_,
        "Facility Phone Number": phone,
        "Facility Email Address": email,
        "Plan Review Status Plan": status,
        "Review Application Date": applied,
        "File Number": f"{80000 + n}",
        "Application Number": f"{1990000 + n}",
        "License Number ": licence,
        "Transaction": transaction,
        "Variance": "n/a",
        "Mailing Name": mailing,
        "Mailing Address": street,
        "Mailing City": city,
        "Mailing State": "FL",
        "Mailing Zip Code": zip_,
        "Mailing Country": "US",
    }


P_1 = plan_row(1, "Indian River Pho LLC", "2235 N. Courtenay Parkway", "MERRITT ISLAND", "32953",
               "09/01/2026", "1034/Plan Review and Initial (COMBO SEAT)", "321-555-0301",
               "owner@indianriverpho.example", "INDIAN RIVER PHO LLC")
P_2 = plan_row(2, "BANANA RIVER BAGELS", "1980 N Atlantic Ave Suite 101", "COCOA BEACH", "32931",
               "09/01/2026", "1031/Initial Plan Review (NOST)", "321-555-0302",
               "bagels@example.com", "BANANA RIVER BAGELS LLC")
P_3 = plan_row(3, "VIERA NOODLE BAR", "7720 N WICKHAM RD", "MELBOURNE", "32940", "09/01/2026",
               "1030/Initial Plan Review (SEAT)", "321-555-0303", "", "VIERA NOODLE BAR INC")
P_1_RESUBMITTED = {**P_1, "Review Application Date": "10/06/2026", "Application Number": "1990011"}
SALTY_BAGEL_PLAN = plan_row(10, "SALTY BAGEL CAFE", "223 W HIBISCUS BLVD", "MELBOURNE", "32901",
                            "08/01/2026", "1034/Plan Review and Initial (COMBO SEAT)",
                            "321-555-0310", "saltybagel@example.com", "EMERALD HALLI LLC",
                            licence="1590010", status="Approved with Provisos")

ERRORS = {
    "weekly_partial_error": {"chgownr_food.csv": "chgownr_food.csv: HTTP 500"},
    "weekly_unavailable": {"newfood.csv": "newfood.csv: HTTP 503"},
}


def weekly(name: str, newfood: list[dict[str, str]], chgownr: list[dict[str, str]],
           newfood_columns: list[str] | None = None) -> None:
    cols = header("newfood")
    folder = WEEKLY / name
    if folder.exists():
        shutil.rmtree(folder)
    write_csv(folder / "newfood.csv", newfood_columns or cols, newfood)
    write_csv(folder / "chgownr_food.csv", header("chgownr_food"), chgownr)


def plan(name: str, rows: list[dict[str, str]]) -> None:
    write_csv(PLAN / name, header("HR_plan_review"), rows)


def build_canonical() -> None:
    weekly("weekly_w1", [W1_1, W1_2, W1_4, W1_5, W1_6], [W1_3])
    weekly("weekly_w2", [W2_1, W2_2, W2_3], [])
    weekly("weekly_partial_error", [W1_1, W1_2, W1_4, W1_5, W1_6], [])
    weekly("weekly_licence_match", [SALTY_BAGEL], [])
    weekly("weekly_empty", [], [])
    renamed = [("CNTY_RENAMED" if c == "Location County" else c) for c in header("newfood")]
    w1_renamed = [{("CNTY_RENAMED" if k == "Location County" else k): v for k, v in r.items()}
                  for r in (W1_1, W1_2, W1_4, W1_5, W1_6)]
    weekly("weekly_bad_columns", w1_renamed, [W1_3], newfood_columns=renamed)
    unavailable = WEEKLY / "weekly_unavailable"
    if unavailable.exists():
        shutil.rmtree(unavailable)
    unavailable.mkdir(parents=True)
    (unavailable / "README.txt").write_text(
        "Fetching newfood.csv raises FetchError (see fixtures/errors.json).\n", encoding="utf-8"
    )
    plan("plan_review_0901.csv", [P_1, P_2, P_3])
    plan("plan_review_1006.csv", [P_1_RESUBMITTED])
    plan("plan_review_with_licence.csv", [SALTY_BAGEL_PLAN])
    (FIX / "errors.json").write_text(json.dumps(ERRORS, indent=2) + "\n", encoding="utf-8")


def _real_rows(path: Path, county_col: str) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def trim(
    path: Path, county_col: str, extra_orange: int = 10
) -> tuple[list[str], list[dict[str, str]]]:
    cols, rows = _real_rows(path, county_col)
    brevard = [r for r in rows if (r.get(county_col) or "").strip() == "Brevard"]
    orange = [r for r in rows if (r.get(county_col) or "").strip() == "Orange"][:extra_orange]
    return cols, brevard + orange


def build_real_samples() -> None:
    if not (SPIKE / "newfood.csv").exists():
        print("logs/spike/ not found; keeping the committed real samples")
        return
    folder = WEEKLY / "weekly_real_sample"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("newfood", "chgownr_food"):
        cols, rows = trim(SPIKE / f"{name}.csv", "Location County")
        clean = [{k: (v or "") for k, v in r.items()} for r in rows]
        write_csv(folder / f"{name}.csv", cols, clean)
    cols, rows = trim(SPIKE / "HR_plan_review.csv", "County")
    write_csv(PLAN / "plan_review_real_sample.csv", cols,
              [{k: (v or "") for k, v in r.items()} for r in rows])


if __name__ == "__main__":
    build_canonical()
    build_real_samples()
    print("fixtures written")
