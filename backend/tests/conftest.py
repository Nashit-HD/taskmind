"""Environment defaults so the suites run without a .env file, as in CI.

A value already in the environment wins, so a developer's exported variables are respected.
"""

import os

_TEST_DATABASE_URL = "postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind_test"

os.environ.setdefault("DATABASE_URL", _TEST_DATABASE_URL)
os.environ.setdefault("TEST_DATABASE_URL", _TEST_DATABASE_URL)
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
