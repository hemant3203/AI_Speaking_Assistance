"""Alembic environment. Uses the application's engine so the URL is only ever read from settings."""
from alembic import context

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.core.database import Base, get_engine


def run_migrations() -> None:
    """Run migrations online. Offline mode is unused because the container always has the database."""
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
