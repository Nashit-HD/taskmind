"""Fixtures that need the test database.

The database comes from ``TEST_DATABASE_URL`` (loaded and checked in ``tests/conftest.py``). It is
the ``<POSTGRES_DB>_test`` database the Compose init script creates, locally and in CI alike.
"""

import pytest
from sqlalchemy import Engine, create_engine

from tests.conftest import TEST_DATABASE_URL


@pytest.fixture(scope="session")
def engine() -> Engine:
    return create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
