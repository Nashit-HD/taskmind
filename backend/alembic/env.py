"""Alembic environment.

The database URL comes from the application's ``Settings``, so ``alembic.ini`` carries none and
there is one place a URL is configured. A caller may instead pass an open connection through
``config.attributes["connection"]``; the test suite does this to migrate the test database on its
own engine, so a developer's ``DATABASE_URL`` is never migrated by a test run.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine

import app.models  # noqa: F401  registers every table on Base.metadata
from app.config import get_settings
from app.database import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which would silence every logger created before
    # this point, including the app's own when the migrations run inside the test process.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it. Used for `alembic upgrade head --sql`."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_on(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied: Connection | None = config.attributes.get("connection")
    if supplied is not None:
        _run_on(supplied)
        return
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        _run_on(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
