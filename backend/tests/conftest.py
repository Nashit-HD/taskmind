"""Test environment.

``TEST_DATABASE_URL`` is the one setting the test suites read. It comes from the process
environment or the repo-root ``.env`` (see ``.env.example``), and must name a database whose name
ends in ``_test``, because the integration suite owns that database outright.

The unit suite needs no database. The application's ``Settings`` still require ``DATABASE_URL`` at
import, so the test process sets it to ``TEST_DATABASE_URL`` when that is configured, and otherwise
to a sentinel that can never connect. Either way, code under test cannot reach a development
database. The integration suite's ``conftest.py`` is what refuses to run without the real value.

The JWT secret is likewise set here for the test process, so a developer's real secret is never
used by a test.
"""

import os
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Port 1 is never a Postgres. A unit test that reached the database would fail at once, loudly.
_NO_DATABASE_URL = "postgresql+psycopg://nobody@localhost:1/unit_tests_do_not_connect"


class _TestEnvironment(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    test_database_url: str


def _load_test_database_url() -> str | None:
    """The configured test database URL, or None when it is not configured at all."""
    try:
        url = _TestEnvironment().test_database_url
    except ValidationError:
        return None
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL points at database {database!r}; "
            "the test suite only runs against a database whose name ends in '_test'."
        )
    return url


TEST_DATABASE_URL = _load_test_database_url()

os.environ["DATABASE_URL"] = TEST_DATABASE_URL or _NO_DATABASE_URL

# A throwaway secret for the test process only, so tests need no real secret and never use one.
TEST_JWT_SECRET = "test-only-secret-never-used-anywhere-real-0123456789"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

# A developer's real key must never be called by a test: without one the echo answers, and the
# unit tests that cover the OpenAI path patch the client.
os.environ.pop("OPENAI_API_KEY", None)
