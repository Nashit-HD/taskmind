"""Fixtures that need the test database.

The database comes from ``TEST_DATABASE_URL`` (loaded and checked in ``tests/conftest.py``). It is
the ``<POSTGRES_DB>_test`` database the Compose init script creates, locally and in CI alike. This
suite refuses to run without it; the unit suite does not need it.

The schema is built by the real migrations, through a connection handed to Alembic on this
suite's own engine, so a developer's ``DATABASE_URL`` is never migrated by a test run.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from tests.conftest import TEST_DATABASE_URL

if TEST_DATABASE_URL is None:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Export it, or copy .env.example to .env at the repo root."
    )

_URL: str = TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[2]


def upgrade_to_head(engine: Engine, alembic_config: Config) -> None:
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")


def downgrade_to_base(engine: Engine, alembic_config: Config) -> None:
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.downgrade(alembic_config, "base")


@pytest.fixture(scope="session")
def engine() -> Engine:
    return create_engine(
        _URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_engine(engine: Engine, alembic_config: Config) -> Engine:
    """A clean schema at the head revision, rebuilt by the migrations at the start of every run."""
    downgrade_to_base(engine, alembic_config)
    upgrade_to_head(engine, alembic_config)
    return engine


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test.

    ``join_transaction_mode="create_savepoint"`` lets code under test call ``commit()`` without
    ending the outer transaction, so tests never see each other's rows.
    """
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        transaction.rollback()
