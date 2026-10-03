from sqlalchemy import create_engine

from alembic import context
from osfl.models import ALL_TABLES, Base
from osfl.settings import get_settings

target_metadata = Base.metadata


def _include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """Autogenerate only our own tables; never touch alembic's version table."""
    if type_ == "table":
        return name in ALL_TABLES
    return True


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


run_migrations_online()
