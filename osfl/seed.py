"""Reference data every database needs."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from osfl.models import Category

CATEGORIES = ("POS", "Equipment", "Insurance", "Payroll", "Pest control", "Food supply", "Other")


def ensure_categories(session: Session) -> None:
    existing = set(session.scalars(select(Category.name)))
    for position, name in enumerate(CATEGORIES):
        if name not in existing:
            session.add(Category(name=name, position=position))
