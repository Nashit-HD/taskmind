"""Fixtures that need the test database.

``TEST_DATABASE_URL`` must point at a database the suite may own. Locally that is ``taskmind_test``
on the Compose Postgres; in CI it is the service container.
"""

import os

import pytest
from sqlalchemy import Engine, create_engine


@pytest.fixture(scope="session")
def engine() -> Engine:
    return create_engine(
        os.environ["TEST_DATABASE_URL"],
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
