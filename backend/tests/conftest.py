"""Test environment.

``TEST_DATABASE_URL`` is the one setting the test suites read. It comes from the process
environment or the repo-root ``.env`` (see ``.env.example``), and must name a database whose name
ends in ``_test``, because the integration suite owns that database outright.

The application's ``DATABASE_URL`` is set from it for the test process, so code under test can
never reach a development database.
"""

import os
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class _TestEnvironment(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    test_database_url: str


def _load_test_database_url() -> str:
    try:
        url = _TestEnvironment().test_database_url
    except ValidationError as exc:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. "
            "Export it, or copy .env.example to .env at the repo root."
        ) from exc
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL points at database {database!r}; "
            "the test suite only runs against a database whose name ends in '_test'."
        )
    return url


TEST_DATABASE_URL = _load_test_database_url()

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
