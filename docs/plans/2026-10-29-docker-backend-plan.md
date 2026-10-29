# Backend Container Implementation Plan

> **For agentic workers:** Use `/explain-plan` to preview all tasks, then `/execute-plan` to implement task-by-task.

**Goal:** `docker compose up --build` starts Postgres and the backend, the backend migrates then serves on port 8000, and `/health` says whether the database answers.

**Spec:** `docs/plans/2026-10-20-backend-design.md` § Configuration, § Docker Compose, § Endpoints (`/health`), § Policy answers (Dependency failure). Assignment deliverable 4 and Milestone 1's last item.

**Affected components:** backend — `backend/`; `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, README and `AGENTS.md` at the repo root

**Change class:** structural — a new build artefact, a Compose service and a CI job. Elevated per `review.md` § Overrides: a config variable the application reads and a CI workflow (devops lens), a new endpoint (monitoring lens, which reduces to the healthcheck because nothing deploys).

**Branch:** `feat/docker-backend`, cut from `feat/chats`; the PR targets `feat/chats` until PR 5 (#6) merges.

---

## Policy answers, checked

- **Entry point.** `GET /health` is unauthenticated by design: Compose's healthcheck and, later,
  a load balancer call it with no token. It reveals up or down and nothing else: no version, no
  host, no query text (`security.md` rules 1 and 22; the spec lists it with the two auth routes as
  the only unauthenticated ones).
- **Dependency reported.** The route runs `SELECT 1` through the normal session. A connection
  failure raises `OperationalError`, which the app-wide handler from PR 1 turns into 503
  `Database unavailable` with the trace logged (`reliability.md` rule 12, `observability.md`
  rule 3). The Compose healthcheck treats any non-2xx as unhealthy.
- **Image.** `python:3.13-slim` and the uv binary image, both pinned by digest (`devops.md` rule
  19, pulled 2026-10-29: Python 3.13.18, uv 0.11.24, the same uv version `pyproject.toml`
  requires). Dependencies install from `uv.lock` with `--locked --no-dev` in a layer before the
  source is copied, so a code change does not reinstall them. The project has no build system, so
  uv installs only the dependencies and the code runs from `/app`, as it does in development. The
  container runs as a non-root user. Dev tools, tests, caches and `.env` never enter the image
  (`.dockerignore`).
- **Configuration.** The container gets `DATABASE_URL`, `CORS_ORIGINS`, `JWT_SECRET` and
  `JWT_EXPIRE_MINUTES` from Compose, which reads the repo-root `.env`; `DATABASE_URL` is rebuilt
  with host `db` because the `.env` value points at `localhost` for a developer's shell. Compose
  refuses to start without `POSTGRES_PASSWORD` and `JWT_SECRET` (`devops.md` rule 4; the app would
  refuse the placeholder anyway). `BACKEND_PORT` is new and optional, for a taken port 8000, like
  `POSTGRES_PORT`.
- **Start order and migration.** `depends_on: db: condition: service_healthy`, then the
  entrypoint runs `alembic upgrade head` and `exec`s the server. A failed migration stops the
  container with its error in the logs, which is the right outcome (`reliability.md` rule 14).
- **CI.** A third job builds the image and runs `docker compose up --build -d --wait`, which
  returns non-zero unless every service becomes healthy, then curls `/health`. That proves the
  deliverable on every pull request rather than trusting the Dockerfile (`devops.md` rule 7). The
  integration job gains a throwaway `JWT_SECRET`, because Compose now requires it even to start
  `db` alone.
- **Observability.** Logs stay JSON on stdout; `docker compose logs backend` is now real.
- **Testing.** Integration: `/health` is 200 with the real database. Unit: `/health` is 503 with
  the generic body when the session raises `OperationalError`, through the dependency override.
  The Compose path is tested by the CI job, not by pytest.
- **Cloud, monitoring, alerts.** Not applicable; nothing deploys. The healthcheck is the
  monitoring this prototype has.

## Files

| File | Job |
|---|---|
| `backend/Dockerfile` | The image: pinned base, locked dependencies, non-root, entrypoint |
| `backend/.dockerignore` | Keep dev tooling, tests, caches and secrets out of the build context |
| `backend/entrypoint.sh` | Migrate, then serve |
| `backend/app/routers/health.py` | `GET /health` |
| `backend/app/main.py` | Include the router |
| `backend/tests/unit/test_health.py` | 503 when the database is gone |
| `backend/tests/integration/test_health.py` | 200 when it answers |
| `docker-compose.yml` | The `backend` service |
| `.env.example` | `BACKEND_PORT` |
| `.github/workflows/ci.yml` | The `compose` job; `JWT_SECRET` for the integration job |
| `README.md` | "Running everything with Docker" |
| `AGENTS.md` | Key Commands, Architecture, Quirks |

---

### Task 1: The health endpoint

**Files:**
- Create: `backend/app/routers/health.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/unit/test_health.py`
- Create: `backend/tests/integration/test_health.py`

- [ ] **Step 1: The route**

`backend/app/routers/health.py`:

```python
"""Liveness with its one dependency: 200 only when the database answers.

Unauthenticated by design: Compose's healthcheck, and later a load balancer, call it with no
token. It reveals up or down and nothing else. A connection failure raises ``OperationalError``,
which the app-wide handler turns into 503 ``Database unavailable`` with the trace in the log.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.database import SessionDep

router = APIRouter(tags=["health"])


class HealthRead(BaseModel):
    status: str
    database: str


@router.get("/health")
def health(db: SessionDep) -> HealthRead:
    db.execute(text("SELECT 1"))
    return HealthRead(status="ok", database="ok")
```

- [ ] **Step 2: Include it**

In `backend/app/main.py`, the routers import becomes:

```python
from app.routers import auth, chats, health, notes
```

and before `application.include_router(auth.router)`:

```python
    application.include_router(health.router)
```

- [ ] **Step 3: Tests**

`backend/tests/unit/test_health.py`:

```python
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import create_app


class _LostDatabase:
    """Stands in for a session whose connection is gone."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))


def _lost_database() -> Iterator[_LostDatabase]:
    yield _LostDatabase()


def test_health_is_503_with_a_generic_body_when_the_database_is_gone() -> None:
    app = create_app()
    app.dependency_overrides[get_db] = _lost_database
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "refused" not in response.text
```

`backend/tests/integration/test_health.py`:

```python
from fastapi.testclient import TestClient


def test_health_is_200_when_the_database_answers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_needs_no_token(client: TestClient) -> None:
    assert "Authorization" not in client.headers
    assert client.get("/health").status_code == 200
```

Check: `cd backend && uv run pytest tests/unit/test_health.py tests/integration/test_health.py`
passes; the Validate command is clean.

---

### Task 2: The image, the Compose service and the CI job

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Create: `backend/entrypoint.sh` (executable)
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: The Dockerfile**

`backend/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1
# Pinned by digest (devops.md rule 19). Pulled 2026-10-29: Python 3.13.18.
FROM python:3.13-slim@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb

# The same uv version pyproject.toml requires, as a static binary, pinned by digest.
COPY --from=ghcr.io/astral-sh/uv:0.11.24@sha256:99ea34acedc870ba4ad11a1f540a1c04267c9f30aadc465a94406f52dfda2c36 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, from the lockfile only, so this layer is reused until the lock changes.
# The project declares no build system, so uv installs the dependencies and nothing else; the
# code runs from /app exactly as it does in development.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

COPY alembic.ini entrypoint.sh ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
```

- [ ] **Step 2: The build context**

`backend/.dockerignore`:

```
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
coverage.xml
tests
.env
```

- [ ] **Step 3: The entrypoint**

`backend/entrypoint.sh` (then `chmod +x backend/entrypoint.sh`):

```sh
#!/bin/sh
# Migrate, then serve. Postgres is reachable by the time this runs, because Compose waits for the
# db healthcheck. A failed migration stops the container with the error in its logs.
set -eu

alembic upgrade head
exec fastapi run --host 0.0.0.0 --port 8000
```

- [ ] **Step 4: The Compose service**

`docker-compose.yml` becomes:

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

  backend:
    build: ./backend
    environment:
      # Not the DATABASE_URL from .env: that one says localhost, for a developer's shell. Inside
      # the Compose network Postgres is the service `db` on its own port 5432.
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-taskmind}:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is not set; copy .env.example to .env}@db:5432/${POSTGRES_DB:-taskmind}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:3000}
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET is not set; see .env.example for how to generate one}
      JWT_EXPIRE_MINUTES: ${JWT_EXPIRE_MINUTES:-60}
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      # The slim image has no curl; urlopen raises on any non-2xx, which fails the check.
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

volumes:
  taskmind_pgdata:
```

- [ ] **Step 5: `.env.example`**

After the `POSTGRES_PORT=5432` line, add:

```
# Host port the backend container is published on (docker compose up). Change it if 8000 is taken.
BACKEND_PORT=8000
```

- [ ] **Step 6: CI**

In `.github/workflows/ci.yml`, the integration job's `env` block gains one line after
`POSTGRES_PORT: "5432"`:

```yaml
      # Compose now needs it even to start db alone; the app's own check wants 32+ characters.
      JWT_SECRET: ci-only-secret-never-used-anywhere-real-0123456789
```

Append to `.github/workflows/ci.yml`, as a third job:

```yaml

  compose:
    name: compose
    runs-on: ubuntu-24.04
    env:
      POSTGRES_USER: taskmind
      POSTGRES_PASSWORD: taskmind
      POSTGRES_DB: taskmind
      POSTGRES_PORT: "5432"
      JWT_SECRET: ci-only-secret-never-used-anywhere-real-0123456789
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
      - name: Build and start every service
        # --wait returns non-zero unless every service reports healthy, so this is the
        # assignment's "docker compose up --build must start both apps" as a check.
        run: docker compose up --build -d --wait
      - name: Health
        run: curl --fail --silent --show-error http://localhost:8000/health
      - name: Backend logs
        if: always()
        run: docker compose logs backend
      - name: Stop
        if: always()
        run: docker compose down -v
```

Check: `docker compose up --build -d --wait` succeeds locally and `curl localhost:8000/health`
returns `{"status":"ok","database":"ok"}`; `docker compose logs backend` shows the migration
then the server; `docker compose down`.

---

### Task 3: README and AGENTS.md

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: README**

Replace the "## First run" section (from its heading up to, not including, "## Running the
backend locally") with:

````markdown
## Running everything with Docker

```bash
cp .env.example .env          # then set JWT_SECRET; the comment says how to generate one
docker compose up --build     # Postgres, then the backend on http://localhost:8000
```

The backend container runs the migrations and then serves. `/health` answers 200 once the
database does, and the OpenAPI docs are at http://localhost:8000/docs. Data lives on a named volume
and survives `docker compose down`; `docker compose down -v` wipes it. Logs are JSON on
`docker compose logs -f backend`.

If port 5432 or 8000 is taken, set `POSTGRES_PORT` or `BACKEND_PORT` in `.env`; for Postgres, use
the same port in `DATABASE_URL` and `TEST_DATABASE_URL`.

## Running the backend outside Docker

For development with reload and the tests:

```bash
docker compose up -d db       # Postgres only
cd backend && uv sync --locked
```

````

Then change the heading "## Running the backend locally" to "### Serving with reload" and leave
its contents.

- [ ] **Step 2: AGENTS.md**

In "## Architecture & Structure", replace the line beginning "- Planned per
`docs/plans/2026-10-20-backend-design.md`:" with:

```markdown
- `backend/app/routers/health.py` — `GET /health`, unauthenticated, 200 only when `SELECT 1` answers; the Compose healthcheck calls it
- `backend/Dockerfile` + `backend/entrypoint.sh` — pinned `python:3.13-slim`, deps from `uv.lock` with `--no-dev`, non-root; the entrypoint runs `alembic upgrade head` then `fastapi run`
```

and change the "Observed through JSON logs on stdout" line so its parenthesis reads
"(`docker compose logs backend`)" instead of "(`docker compose logs backend` once the service exists)".

In "## Key Commands", add as the first line:

```markdown
- Run everything: `docker compose up --build` (backend on :8000; needs a root `.env` with `POSTGRES_PASSWORD` and `JWT_SECRET`)
```

In "## Quirks & Gotchas", change the Compose line to:

```markdown
- ⚠️ **Compose refuses to start without `POSTGRES_PASSWORD` and `JWT_SECRET`, even for `db` alone** — `cp .env.example .env` and set a real `JWT_SECRET`; `.env` is gitignored.
```

Check: `AGENTS.md` keeps the HD required section above the divider; README renders.

---

## Gaps against HD policy, recorded on purpose

- `devops.md` rules 9 to 12 and 18 (deploy path, rollback, identifiable build) do not apply:
  nothing deploys. The image carries no version label for the same reason.

## Documentation Notes

- `/health` is observed through the Compose healthcheck and the per-request log line → **PR**.
- Compose needs `JWT_SECRET` even for `db` alone → **AGENTS.md** Quirks (Task 3).
- `BACKEND_PORT` beside `POSTGRES_PORT` → **README** (Task 3).
