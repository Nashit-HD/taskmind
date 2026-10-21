"""Fixtures that need the test database.

The database comes from ``TEST_DATABASE_URL`` (loaded and checked in ``tests/conftest.py``). It is
the ``<POSTGRES_DB>_test`` database the Compose init script creates, locally and in CI alike. This
suite refuses to run without it; the unit suite does not need it.
"""

import pytest
from sqlalchemy import Engine, create_engine

from tests.conftest import TEST_DATABASE_URL

if TEST_DATABASE_URL is None:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Export it, or copy .env.example to .env at the repo root."
    )

_URL: str = TEST_DATABASE_URL


@pytest.fixture(scope="session")
def engine() -> Engine:
    return create_engine(
        _URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
