# Backend Scaffold Implementation Plan

> **For agentic workers:** Use `/explain-plan` to preview all tasks, then `/execute-plan` to implement task-by-task.

**Goal:** Stand up the backend project so a clean clone can install, lint, type-check and test it, with Postgres in Compose and CI on every pull request, ready for the data model in PR 2.

**Spec:** `docs/plans/2026-10-20-backend-design.md` § Delivery item 1

**Affected components:** backend — `backend/`; repo root (Compose, env example, CI, instruction files)

**Change class:** structural — new subsystem, dependencies added, CI workflow. Decision record: the spec's Decisions table.

| Revision | Closed | Sections changed |
|---|---|---|
| r2 | B1, N1, N2, N3 | Task 2 (`configure_logging`, test), Task 3 (`POSTGRES_PORT`), Task 5 (observability line, CODEOWNERS, README) |

---

## Policy answers, checked

The spec's answers hold for this PR. Nothing here adds an entry point that touches data, so the
authorisation answer is not exercised until PR 3. What this PR does carry:

- **DevOps:** lockfile, exact runtime and package-manager pins, `.env.example` naming every variable
  the app reads, CI running the declared commands verbatim on pull requests to `main`, actions pinned
  to commit SHAs, runner and database images pinned.
- **Observability:** the JSON formatter, the request id, and the per-request log line, so every
  later endpoint inherits them. The middleware's error path logs before re-raising.
- **Reliability:** the test engine has a connect timeout; Compose waits for Postgres health.
- **Testing:** two suites declared, `unit` as the gate and `integration` in CI with a Postgres
  service container. Changed-line coverage checked by `diff-cover` at the prototype figure.
- **Security:** no secrets in source. The Compose password comes from `.env`, which Compose refuses to
  start without. CI's database password is a throwaway for a service container that lives minutes.

One correction to the spec: `.python-version` pins `3.13.14`, the newest 3.13 uv 0.11.24 can install,
rather than "3.13". The Dockerfile in PR 6 uses the matching `python:3.13.14-slim-bookworm` image.

## Files

| File | Job |
|---|---|
| `backend/pyproject.toml` | Manifest, dependency groups, Ruff, mypy, pytest and coverage config, `fastapi` entrypoint |
| `backend/.python-version` | Exact runtime pin |
| `backend/uv.lock` | Generated lockfile |
| `backend/app/__init__.py` | Package marker |
| `backend/app/config.py` | `Settings` from environment, `get_settings`, `SettingsDep` |
| `backend/app/logging.py` | JSON formatter, request id context, request logging middleware |
| `backend/app/main.py` | `create_app()` and the module-level `app` |
| `backend/tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py` | Package markers so mypy and pytest see distinct modules |
| `backend/tests/conftest.py` | Environment defaults for tests |
| `backend/tests/unit/test_app.py` | App smoke tests: docs, request id, CORS, error path logs |
| `backend/tests/unit/test_logging.py` | Formatter output |
| `backend/tests/integration/conftest.py` | Session engine on `TEST_DATABASE_URL` |
| `backend/tests/integration/test_database.py` | The test database answers |
| `docker-compose.yml` | `db` service on a named volume |
| `docker/postgres/init/01-create-test-db.sql` | Creates `taskmind_test` on first start |
| `.env.example` | Every variable Compose and the app read |
| `.github/workflows/ci.yml` | `validate` and `integration` jobs |
| `AGENTS.md`, `CLAUDE.md` | Project facts and the wrapper |
| `.github/CODEOWNERS` | Default reviewers |
| `README.md` | Setup and run commands for what exists |
| `backend/README.md` | Delete: the root README carries the commands |

---

### Task 1: Backend manifest, pins and tooling config

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.python-version`
- Create: `backend/uv.lock` (generated)
- Create: `backend/app/__init__.py`
- Create: `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/integration/__init__.py`
- Delete: `backend/README.md`

- [ ] **Step 1: Write the manifest**

`backend/pyproject.toml`:

```toml
[project]
name = "taskmind-backend"
version = "0.1.0"
description = "TaskMind API: shared notes with note-scoped AI chats"
readme = "../README.md"
requires-python = "==3.13.*"
dependencies = [
    "fastapi[standard]>=0.156.4",
    "pydantic-settings>=2.16.1",
    "sqlalchemy>=2.1.5",
    "psycopg[binary]>=3.3.6",
]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "pytest-cov>=7.1.0",
    "diff-cover>=10.6.0",
    "ruff>=0.17.1",
    "mypy>=2.4.0",
]

[tool.uv]
required-version = "==0.11.24"

[tool.fastapi]
entrypoint = "app.main:app"

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.13"
files = ["app", "tests"]
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"

[tool.coverage.run]
source = ["app"]
branch = true

[tool.coverage.report]
# Package markers hold no logic.
omit = ["app/__init__.py"]
```

Why these pins: the lockfile pins exact versions of every package; `requires-python` and
`.python-version` pin the runtime; `required-version` pins uv. The `>=` floors in the manifest are
the versions current on 2026-10-21, so `uv lock` resolves to them.

- [ ] **Step 2: Pin the runtime**

`backend/.python-version`:

```
3.13.14
```

- [ ] **Step 3: Package markers**

Create empty files: `backend/app/__init__.py`, `backend/tests/__init__.py`,
`backend/tests/unit/__init__.py`, `backend/tests/integration/__init__.py`.

- [ ] **Step 4: Generate the lockfile**

Run from `backend/`:

```bash
uv lock
uv sync --locked
```

`uv sync` downloads CPython 3.13.14 if it is not installed and creates `backend/.venv`, which is
gitignored. Commit `uv.lock`.

- [ ] **Step 5: Remove `backend/README.md`**

The root README carries the commands, so the placeholder is deleted with `git rm backend/README.md`.

---

### Task 2: Settings, structured logging and the app factory

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/logging.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/unit/test_logging.py`
- Create: `backend/tests/unit/test_app.py`

- [ ] **Step 1: Settings**

`backend/app/config.py`:

```python
"""Application settings, read from the environment.

Values come from the process environment first, then from the repository-root ``.env`` file when
it exists. Inside Docker there is no ``.env``: Compose injects the variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """``CORS_ORIGINS`` as a list: comma-separated in the environment, blanks dropped."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """One ``Settings`` per process. Tests clear the cache after changing the environment."""
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
```

- [ ] **Step 2: Logging**

`backend/app/logging.py`:

```python
"""Structured logging and the request id.

Every log event is one JSON object with ``timestamp``, ``level``, ``logger``, ``message`` and
``request_id``. Call sites pass extra fields as ``extra={"fields": {...}}`` and never interpolate
them into the message.

The request id is taken from the ``X-Request-Id`` header when the caller sends one, or generated,
and is returned on the response so a client can quote it.
"""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-Id"
_MAX_REQUEST_ID_LENGTH = 128

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("taskmind.request")


class JsonFormatter(logging.Formatter):
    """Formats a record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        fields = record.__dict__.get("fields")
        if isinstance(fields, dict):
            event.update(fields)
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Route every logger, uvicorn's included, through the JSON formatter.

    Uvicorn's access log is switched off because ``request_logging_middleware`` emits the request
    line with the request id, which uvicorn's line cannot carry.

    Only a previous JSON handler is replaced, so calling this twice (every ``create_app()`` does)
    never stacks handlers, and handlers other tools add, such as pytest's capture, are kept.
    """
    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing.formatter, JsonFormatter):
            root.removeHandler(existing)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def _incoming_request_id(request: Request) -> str:
    supplied = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if supplied and len(supplied) <= _MAX_REQUEST_ID_LENGTH:
        return supplied
    return str(uuid.uuid4())


async def request_logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Bind the request id, time the request, log one line per request, and echo the id back.

    The success line is logged inside the ``try`` so the formatter still sees the request id; the
    ``finally`` resets it afterwards.
    """
    request_id = _incoming_request_id(request)
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        logger.info(
            "request",
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )
        raise
    finally:
        request_id_var.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
```

The error branch logs with the stack trace and re-raises, so Starlette's server-error handler still
returns the generic 500 body. Nothing is swallowed, and the error path emits.

- [ ] **Step 3: App factory**

`backend/app/main.py`:

```python
"""FastAPI application factory.

``create_app()`` builds the app from settings; the module-level ``app`` is what ``fastapi dev`` and
``fastapi run`` serve, named in ``pyproject.toml`` under ``[tool.fastapi]``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging import REQUEST_ID_HEADER, configure_logging, request_logging_middleware


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    application = FastAPI(title="TaskMind API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    application.middleware("http")(request_logging_middleware)
    return application


app = create_app()
```

`allow_credentials=False` is deliberate: auth will use bearer tokens, not cookies, so the browser
never needs credentialed CORS.

- [ ] **Step 4: Test environment defaults**

`backend/tests/conftest.py`:

```python
"""Environment defaults so the suites run without a .env file, as in CI.

A value already in the environment wins, so a developer's exported variables are respected.
"""

import os

_TEST_DATABASE_URL = "postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind_test"

os.environ.setdefault("DATABASE_URL", _TEST_DATABASE_URL)
os.environ.setdefault("TEST_DATABASE_URL", _TEST_DATABASE_URL)
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
```

- [ ] **Step 5: Formatter tests**

`backend/tests/unit/test_logging.py`:

```python
import json
import logging

from app.logging import JsonFormatter, request_id_var


def _record(**attrs: object) -> logging.LogRecord:
    return logging.makeLogRecord(
        {"name": "test", "levelno": logging.INFO, "levelname": "INFO", "msg": "hello", **attrs}
    )


def test_formatter_emits_one_json_object_with_the_request_id() -> None:
    token = request_id_var.set("req-1")
    try:
        event = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)

    assert event["message"] == "hello"
    assert event["level"] == "info"
    assert event["logger"] == "test"
    assert event["request_id"] == "req-1"
    assert event["timestamp"].endswith("+00:00")


def test_formatter_merges_extra_fields() -> None:
    event = json.loads(JsonFormatter().format(_record(fields={"status": 200, "path": "/x"})))

    assert event["status"] == 200
    assert event["path"] == "/x"


def test_formatter_has_null_request_id_outside_a_request() -> None:
    event = json.loads(JsonFormatter().format(_record()))

    assert event["request_id"] is None
```

- [ ] **Step 6: App tests**

`backend/tests/unit/test_app.py`:

```python
import json
import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.logging import REQUEST_ID_HEADER, JsonFormatter
from app.main import app, create_app


def test_openapi_docs_are_served() -> None:
    with TestClient(app) as client:
        response = client.get("/docs")

    assert response.status_code == 200


def test_response_carries_a_generated_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert uuid.UUID(response.headers[REQUEST_ID_HEADER])


def test_response_echoes_a_supplied_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json", headers={REQUEST_ID_HEADER: "client-abc"})

    assert response.headers[REQUEST_ID_HEADER] == "client-abc"


def test_an_oversized_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json", headers={REQUEST_ID_HEADER: "x" * 129})

    assert uuid.UUID(response.headers[REQUEST_ID_HEADER])


def test_cors_allows_the_frontend_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/openapi.json",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_an_unknown_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/openapi.json",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_each_request_logs_one_line_with_the_request_id(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="taskmind.request"), TestClient(app) as client:
        client.get("/openapi.json", headers={REQUEST_ID_HEADER: "log-me"})

    records = [r for r in caplog.records if r.name == "taskmind.request"]
    assert len(records) == 1
    fields = records[0].__dict__["fields"]
    assert fields["method"] == "GET"
    assert fields["path"] == "/openapi.json"
    assert fields["status"] == 200
    assert fields["duration_ms"] >= 0


def _app_with_a_failing_route() -> FastAPI:
    failing = create_app()

    @failing.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    return failing


def test_an_unhandled_error_is_logged_and_returns_500(caplog: pytest.LogCaptureFixture) -> None:
    failing = _app_with_a_failing_route()
    with (
        caplog.at_level(logging.ERROR, logger="taskmind.request"),
        TestClient(failing, raise_server_exceptions=False) as client,
    ):
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].__dict__["fields"]["path"] == "/boom"
    assert errors[0].exc_info is not None


def test_settings_cors_origins_are_split_on_commas(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings, get_settings

    monkeypatch.setenv("CORS_ORIGINS", "http://a.example, http://b.example,")
    get_settings.cache_clear()
    try:
        settings = Settings()
    finally:
        get_settings.cache_clear()

    assert settings.cors_origin_list == ["http://a.example", "http://b.example"]


def test_exactly_one_json_handler_is_on_the_root_logger_after_repeated_setup() -> None:
    create_app()
    create_app()
    json_handlers = [
        h for h in logging.getLogger().handlers if isinstance(h.formatter, JsonFormatter)
    ]

    assert len(json_handlers) == 1
    event = json.loads(json_handlers[0].format(logging.makeLogRecord({"msg": "x"})))
    assert event["message"] == "x"
```

- [ ] **Step 7: Run the gate**

From `backend/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest tests/unit
```

Fix anything Ruff or mypy reports before moving on. Expected: all unit tests pass, mypy reports no
issues.

---

### Task 3: Postgres in Compose, environment example, and the integration smoke test

**Files:**
- Create: `docker-compose.yml`
- Create: `docker/postgres/init/01-create-test-db.sql`
- Create: `.env.example`
- Create: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_database.py`

- [ ] **Step 1: Compose with the database only**

`docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:17.9-alpine@sha256:c7526c0f6c3f30260a563d7bcf8ad778effac59a44f8ffa86678c35418338609
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-taskmind}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is not set; copy .env.example to .env}
      POSTGRES_DB: ${POSTGRES_DB:-taskmind}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - taskmind_pgdata:/var/lib/postgresql/data
      - ./docker/postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  taskmind_pgdata:
```

The image is pinned by its multi-arch index digest, so an Apple Silicon machine and an x86 CI runner
each get their native build of the same release. The `:?` on the password makes Compose refuse to
start without a `.env`, which is the point: no default password in source. `POSTGRES_PORT` is the
host port only; the container always listens on 5432. It exists because this machine already has
another project's Postgres on 5432.

- [ ] **Step 2: Test database init script**

`docker/postgres/init/01-create-test-db.sql`:

```sql
-- Runs once, when the taskmind_pgdata volume is first initialised.
-- To re-run it: docker compose down -v, then docker compose up.
CREATE DATABASE taskmind_test;
```

- [ ] **Step 3: Environment example**

`.env.example`:

```
# Copy to .env and adjust. .env is gitignored.

# Postgres container (docker-compose.yml, service `db`)
POSTGRES_USER=taskmind
POSTGRES_PASSWORD=change-me-locally
POSTGRES_DB=taskmind
# Host port the container is published on. Change it if 5432 is taken, and match the URLs below.
POSTGRES_PORT=5432

# Backend (backend/app/config.py). Host is localhost when the API runs outside Docker.
DATABASE_URL=postgresql+psycopg://taskmind:change-me-locally@localhost:5432/taskmind
CORS_ORIGINS=http://localhost:3000

# Tests (backend/tests). A separate database on the same Postgres, created by docker/postgres/init.
TEST_DATABASE_URL=postgresql+psycopg://taskmind:change-me-locally@localhost:5432/taskmind_test
```

- [ ] **Step 4: Integration fixtures**

`backend/tests/integration/conftest.py`:

```python
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
```

- [ ] **Step 5: Smoke test**

`backend/tests/integration/test_database.py`:

```python
from sqlalchemy import Engine, text


def test_the_test_database_answers(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_the_test_database_is_the_test_database(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT current_database()")).scalar_one() == "taskmind_test"
```

- [ ] **Step 6: Run it against Compose**

From the repo root, then `backend/`:

```bash
cp .env.example .env
docker compose up -d db
docker compose ps
cd backend && uv run pytest tests/integration
```

Expected: `db` reports `healthy`, both tests pass. The `.env` password is the example value; that is
fine on a laptop and is never committed.

---

### Task 4: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Workflow**

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  contents: read

env:
  UV_VERSION: "0.11.24"

jobs:
  validate:
    name: validate
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
      - uses: astral-sh/setup-uv@d0d8abe699bfb85fec6de9f7adb5ae17292296ff # v6
        with:
          version: ${{ env.UV_VERSION }}
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - name: Install
        run: cd backend && uv sync --locked
      - name: Validate
        run: cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest tests/unit

  integration:
    name: integration
    runs-on: ubuntu-24.04
    services:
      postgres:
        image: postgres:17.9-alpine@sha256:c7526c0f6c3f30260a563d7bcf8ad778effac59a44f8ffa86678c35418338609
        env:
          POSTGRES_USER: taskmind
          POSTGRES_PASSWORD: taskmind
          POSTGRES_DB: taskmind_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U taskmind -d taskmind_test"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    env:
      DATABASE_URL: postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind_test
      TEST_DATABASE_URL: postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind_test
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@d0d8abe699bfb85fec6de9f7adb5ae17292296ff # v6
        with:
          version: ${{ env.UV_VERSION }}
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - name: Install
        run: cd backend && uv sync --locked
      - name: Integration tests with changed-line coverage
        run: cd backend && uv run pytest --cov=app --cov-report=xml && uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=20
```

The `Validate` and `Integration` run strings are the `Validate command` and the `integration` suite
command declared in `AGENTS.md`, character for character. `fetch-depth: 0` is what lets `diff-cover`
see `origin/main`. The service-container password is not a secret: the container exists for the
length of the job and is reachable only from it.

- [ ] **Step 2: Required checks on `main`**

After the first run on the pull request shows both jobs, the developer makes them required. HD's
devops decision is that the developer applies branch protection from a printed command, so this is
printed, not run:

```bash
gh api -X PATCH repos/Nashit-HD/taskmind/branches/main/protection/required_status_checks \
  --input - <<'EOF'
{"strict": true, "contexts": ["validate", "integration"]}
EOF
```

---

### Task 5: Instruction files and README

**Files:**
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `.github/CODEOWNERS`
- Modify: `README.md`

- [ ] **Step 1: AGENTS.md**

```markdown
# AGENTS.md
<!-- hd-skills REQUIRED SECTION: maintain-project-docs manages everything above the END marker -->
## Project Overview
TaskMind: shared notes with note-scoped AI chats. FastAPI + SQLAlchemy 2.0 + PostgreSQL backend in `backend/`; Next.js frontend in `frontend/` (not started).
## Project Facts
- **Repo layout:** single-repo
- **Project type:** prototype
- **Components:**
  - backend — `backend/`
  - frontend — `frontend/`
- **Validate command:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest tests/unit`
- **Lint / format command:** `cd backend && uv run ruff check --fix . && uv run ruff format .`
- **Type check command:** `cd backend && uv run mypy`
- **Type check strictness:** `mypy --strict` (`strict = true` in `backend/pyproject.toml`)
- **Plans & docs location:** `docs/plans/`
- **Cloud platform:** none
- **Cloud account owner:** none
- **Cloud guardrails:** none
- **Alerts channel:** none
- **Environments:** none
## Version control
- **Host:** github
- **Repo:** Nashit-HD/taskmind
- **PR tool:** gh CLI
- **Base branch:** main
- **Branch flow:** feature → main   # custom — nothing is deployed, so there is no develop or staging
- **Branch naming:** <type>/<slug>   # no ticket system
- **Automated reviewers:** none
- **Commit format:** conventional-commits
- **Merge method:** merge-commit
- **Required approvals:** 1   # reviewer: hiteshsalavi
## Testing
- **Framework:** pytest
- **Single target:** `cd backend && uv run pytest tests/unit/test_app.py`
- **Location / naming:** `backend/tests/{unit,integration}/test_*.py`, tests tree
- **Coverage target:** 20% — warns (prototype)
- **Suites:**
    - unit — `cd backend && uv run pytest tests/unit` — gate
    - integration — `cd backend && uv run pytest --cov=app --cov-report=xml && uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=20` — ci
## Architecture & Structure
- `backend/app/main.py` — `create_app()`; the module-level `app` is served by `fastapi dev`/`fastapi run` via `[tool.fastapi]` in `pyproject.toml`
- `backend/app/config.py` — `Settings` from env, then the repo-root `.env`; `SettingsDep` for handlers
- `backend/app/logging.py` — JSON formatter, `X-Request-Id` middleware, one log line per request; pass fields as `extra={"fields": {...}}`
- Planned per `docs/plans/2026-10-20-backend-design.md`: `database.py`, `security.py`, `auth.py`, `assistant.py`, `models/`, `schemas/`, `routers/`
- Dependencies are `Annotated[..., Depends(...)]` aliases ending in `Dep`; handlers that touch the database are plain `def`
- Error shape is FastAPI's `{"detail": ...}` everywhere
- Observed through JSON logs on stdout (`docker compose logs backend` once the service exists): one `info` line per request with `status` and `duration_ms`; a failure is an `error` line with `exception` and the same `request_id` the client received
## Key Commands
- Install: `cd backend && uv sync --locked`
- Run API locally: `cd backend && uv run fastapi dev` (needs `db` up and a root `.env`)
- Database: `docker compose up -d db`; reset it: `docker compose down -v`
- Lint and format: `cd backend && uv run ruff check --fix . && uv run ruff format .`
- Type check: `cd backend && uv run mypy`
- Unit tests: `cd backend && uv run pytest tests/unit`
- Integration tests: `cd backend && uv run pytest tests/integration` (needs `db` up)
## Workflows & Verification
- Before calling a change done, run the Validate command and read its output; run the integration suite when the change touches data or an endpoint
- CI (`.github/workflows/ci.yml`) runs the Validate command and the integration suite on every pull request to `main`
## Quirks & Gotchas
- ⚠️ **`taskmind_test` is created by `docker/postgres/init/` only on a fresh volume** — if it is missing, `docker compose down -v` then `up -d db`.
- ⚠️ **Compose refuses to start without `POSTGRES_PASSWORD`** — `cp .env.example .env` first; `.env` is gitignored.
- ⚠️ **Port 5432 may be taken by another project's Postgres** — set `POSTGRES_PORT` in `.env` and use the same port in `DATABASE_URL` and `TEST_DATABASE_URL`.
- ⚠️ **`get_settings()` is cached** — a test that changes env must call `get_settings.cache_clear()` after.
- ⚠️ **No AI attribution in commits or PR descriptions** — remove any `Co-Authored-By: Claude` or "Generated with" line before committing.
<!-- END hd-skills REQUIRED SECTION: everything below is team-maintained; tooling never edits it -->

---

# Project Notes (team-maintained)
```

- [ ] **Step 2: CLAUDE.md**

````markdown
@AGENTS.md

HD engineering policies live at `${CLAUDE_PLUGIN_ROOT}/policies/`. Read the relevant ones before
designing or implementing — they are the standard, not a suggestion.

<!-- Claude Code only. Everything for every agent goes in AGENTS.md. -->
````

- [ ] **Step 3: CODEOWNERS**

`.github/CODEOWNERS`:

```
# Every path: the repository owner reviews, with Hitesh as the assignment reviewer.
* @Nashit-HD @hiteshsalavi
```

- [ ] **Step 4: README**

Replace `README.md` with:

```markdown
# TaskMind

A small notes and chat app: a Next.js frontend and a FastAPI backend over PostgreSQL, run locally
with Docker Compose. Signed-in users share notes, and anyone can open a chat on a note to ask an AI
assistant about it.

## Structure

- `backend/` — FastAPI API, SQLAlchemy models, Alembic migrations, pytest tests
- `frontend/` — Next.js app (not started)
- `docs/plans/` — design specs and implementation plans
- `docker/` — files mounted into Compose services

## Prerequisites

- Docker Desktop (Compose v2)
- [uv](https://docs.astral.sh/uv/) 0.11.24. It installs the pinned Python itself.

## First run

```bash
cp .env.example .env          # local values; never committed
docker compose up -d db       # Postgres 17 on localhost:5432, data on a named volume
cd backend && uv sync --locked
```

If something else already uses port 5432, set `POSTGRES_PORT` in `.env` to a free port and use the
same port in `DATABASE_URL` and `TEST_DATABASE_URL`.

## Running the backend locally

```bash
cd backend && uv run fastapi dev
```

The API is at http://localhost:8000 and the OpenAPI docs at http://localhost:8000/docs.

## Running the tests

```bash
cd backend
uv run pytest tests/unit                 # no database needed
uv run pytest tests/integration          # needs `docker compose up -d db`
```

Lint, format and type check:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Decisions

See `docs/plans/2026-10-20-backend-design.md`. In short:

- SQLAlchemy 2.0 (sync) with psycopg 3; separate Pydantic request and response schemas.
- Email + password sign-in with Argon2id hashing and short-lived JWT bearer tokens.
- Every signed-in user can read every note; only the author edits or deletes it.
- Chats belong to a note; the assistant answers from that note's content only.
- JSON logs with an `X-Request-Id` on every request and response.

## Unfinished and next steps

_Written at the deadline._
```

---

## Documentation Notes

- Branch protection on `main` (review required, admins included, no force-push) was applied by the
  assistant on 2026-10-20, not by the developer from a printed command as the devops policy expects.
  Nothing to change in the repository; the required-checks step in Task 4 is printed for the
  developer to run → **PR** `## Deploy notes`.
- `.python-version` is `3.13.14` because that is the newest 3.13 uv 0.11.24 can install; the
  Dockerfile in PR 6 must match → **code** comment in `backend/Dockerfile` when it is written.
- CI's integration job creates `taskmind_test` through `POSTGRES_DB`, not the init script, because
  GitHub service containers cannot mount repository files → **code** comment in `.github/workflows/ci.yml`.
