"""Which records are leads, and of what type (E2E_TESTS.md section 1.4, Classification)."""

LICENCE_NEW = {"SEAT", "NOST"}
LICENCE_MOBILE = {"MFDV", "HTDG"}
CHANGE_OWNER_FILE = "chgownr_food.csv"
PLAN_REVIEW_FILE = "HR_plan_review.csv"


def classify(file: str, rank: str = "", transaction: str = "", facility: str = "") -> str:
    """Return `new`, `ownership_change`, `mobile` or `ignored`."""
    if file == PLAN_REVIEW_FILE:
        return _classify_plan_review(transaction, facility)
    rank = rank.strip().upper()
    if rank not in LICENCE_NEW | LICENCE_MOBILE:
        return "ignored"
    if file == CHANGE_OWNER_FILE:
        return "ownership_change"
    return "new" if rank in LICENCE_NEW else "mobile"


def _classify_plan_review(transaction: str, facility: str) -> str:
    t = transaction.strip()
    if facility.strip().lower() == "catering" or "Request Plan Review" in t:
        return "ignored"
    if "Change Owner" in t:
        return "ownership_change"
    if "MFDV" in t or "Hot Dog" in t:
        return "mobile"
    if "SEAT" in t or "NOST" in t or "COMBO)" in t or t.endswith("Initial Plan Review"):
        return "new"
    return "ignored"
