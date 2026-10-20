# TaskMind backend — design

**Date:** 2026-10-20 · **Status:** approved · **Scope:** week 1 of the TaskMind assignment (backend and database)

## Intent

Build the TaskMind backend: a FastAPI service over PostgreSQL exposing notes, chats and messages,
with Alembic migrations, pytest tests against a separate test database, and a Docker Compose stack
that starts Postgres and the backend. The frontend is a separate design in week 2.

The assignment is an up-skilling exercise reviewed by Hitesh. Clean, working, well-structured code
matters more than feature count.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| ORM and driver | SQLAlchemy 2.0, synchronous, psycopg 3 | Simplest to read and test. Separate Pydantic schemas are required by the assignment, so SQLModel saves nothing. Async adds moving parts with no benefit at this load |
| Python | 3.13, pinned in `.python-version` | 3.14 is weeks old and some wheels lag |
| Package manager | uv, with a committed `uv.lock` | Lockfile and pinned runtime per the devops policy |
| Lint, format, types | Ruff (lint + format), mypy `--strict` | Assignment asks for Ruff; typed code needs a checker |
| Primary keys | Integer, auto-increment | The assignment's table says `id`; integers are the simplest correct choice |
| Timestamps | `timestamptz`, UTC, serialised as ISO 8601 | Assignment requires ISO 8601 UTC |
| Layers | Routers call the session directly | Assignment asks for routers, schemas, models and session setup. A service layer is a fourth layer this app does not need |
| Authorisation | None, by design | The assignment has no sign-in. Every endpoint is open. Recorded here and in the README so it is a decision, not an omission |
| List bounds | `limit` (default 50, max 100) and `offset` on `GET /notes` and `GET /chats` | Result sets must be bounded. This also covers the pagination bonus for notes |
| Health | `GET /health` runs `SELECT 1`; 200 or 503 | Reports the database, not just liveness. Compose uses it as the backend healthcheck |
| Error shape | FastAPI's default `{"detail": ...}` | One shape everywhere, as the assignment asks. 422 bodies keep FastAPI's list under `detail` |
| Database down | 503 `{"detail": "Database unavailable"}` | Degrades to a clear error instead of a 500 with a stack trace |
| Logging | Standard-library logging with a JSON formatter; `X-Request-Id` accepted or generated | Structured logs with a correlation id, no new dependency |
| Project type | `prototype` | Nothing deploys and there are no users. Coverage target seeded at 20%; we aim far higher |

## Data model

| Table | Columns | Notes |
|---|---|---|
| `notes` | `id` int PK; `title` varchar(200) not null; `content` text not null default `''`; `created_at`, `updated_at` timestamptz not null | Index on `created_at` for "newest first" |
| `chats` | `id` int PK; `title` varchar(100) not null; `created_at`, `updated_at` timestamptz not null | Index on `updated_at` for "most recently updated first" |
| `messages` | `id` int PK; `chat_id` int FK → `chats.id` on delete cascade, not null; `content` text not null; `created_at` timestamptz not null | Index on `(chat_id, created_at)` for "oldest first" within a chat |

`created_at` and `updated_at` are set by the database (`server_default=now()`), and `updated_at`
is refreshed on update. Adding a message updates the parent chat's `updated_at` in the same
transaction, so chat ordering reflects activity.

Deleting a chat deletes its messages through the foreign key cascade, in the database.

## Schemas

Request and response schemas are separate classes.

| Resource | Request | Response |
|---|---|---|
| Note | `NoteCreate(title, content="")`, `NoteUpdate(title, content)` | `NoteRead(id, title, content, created_at, updated_at)` |
| Chat | `ChatCreate(title)`, `ChatUpdate(title)` | `ChatRead(id, title, created_at, updated_at)`; `ChatDetail = ChatRead + messages: list[MessageRead]` |
| Message | `MessageCreate(content)` | `MessageRead(id, chat_id, content, created_at)` |

Titles and message content are stripped of surrounding whitespace and must be non-empty after
stripping. Titles respect the max lengths (200 for notes, 100 for chats). `PUT` replaces, so update
schemas require every field.

## Endpoints

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/health` | 200 `{"status": "ok"}` or 503 | `SELECT 1` |
| GET | `/notes?limit=&offset=` | 200 `list[NoteRead]` | newest first |
| POST | `/notes` | 201 `NoteRead` | |
| GET | `/notes/{id}` | 200 `NoteRead` / 404 | |
| PUT | `/notes/{id}` | 200 `NoteRead` / 404 | |
| DELETE | `/notes/{id}` | 204 / 404 | |
| GET | `/chats?limit=&offset=` | 200 `list[ChatRead]` | most recently updated first |
| POST | `/chats` | 201 `ChatRead` | |
| GET | `/chats/{id}` | 200 `ChatDetail` / 404 | messages oldest first, one query |
| PUT | `/chats/{id}` | 200 `ChatRead` / 404 | rename |
| DELETE | `/chats/{id}` | 204 / 404 | cascades to messages |
| POST | `/chats/{id}/messages` | 201 `MessageRead` / 404 | bumps chat `updated_at` |

Invalid bodies, non-integer ids and out-of-range `limit`/`offset` return 422. CORS allows
`http://localhost:3000`, read from settings.

## Code layout

```
backend/
├── app/
│   ├── main.py          create_app(): CORS, routers, exception handlers, logging setup
│   ├── config.py        Settings (pydantic-settings): DATABASE_URL, CORS_ORIGINS
│   ├── database.py      engine, SessionLocal, Base, get_db dependency
│   ├── logging.py       JSON formatter, request-id middleware, per-request log line
│   ├── models/          note.py, chat.py, message.py
│   ├── schemas/         note.py, chat.py, message.py
│   └── routers/         health.py, notes.py, chats.py
├── alembic/             env.py reads DATABASE_URL from settings; versions/
├── alembic.ini
├── tests/
│   ├── conftest.py
│   ├── unit/            schema validation; no database
│   └── integration/     endpoint tests against taskmind_test
├── pyproject.toml, uv.lock, .python-version
├── Dockerfile, .dockerignore
```

## Configuration

| Variable | Used by | Example |
|---|---|---|
| `DATABASE_URL` | backend, Alembic | `postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind` |
| `TEST_DATABASE_URL` | pytest | `postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind_test` |
| `CORS_ORIGINS` | backend | `http://localhost:3000` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose `db` service | local dev values |

A committed `.env.example` holds local development values. `.env` is ignored. Compose overrides
`DATABASE_URL` for the backend container so it reaches Postgres at host `db`.

## Docker Compose

- `db`: `postgres:17-alpine` pinned to an exact minor version, named volume `taskmind_pgdata`, healthcheck
  with `pg_isready`, an init script in `docker-entrypoint-initdb.d/` that creates `taskmind_test`.
- `backend`: built from `backend/Dockerfile`, `depends_on: db: condition: service_healthy`,
  entrypoint runs `alembic upgrade head` then uvicorn on port 8000, healthcheck on `/health`.
- `frontend`: added in week 2.

The Dockerfile uses a slim official Python image, installs dependencies from the lockfile in a
cached layer before copying source, runs as a non-root user, and has a `.dockerignore`.

## Policy answers

| Question | Answer |
|---|---|
| Existing patterns | Greenfield. The conventions above are chosen once and recorded in `AGENTS.md` |
| Trust boundary | Request bodies, path ids, `limit`/`offset`. All validated by Pydantic and FastAPI typing. No authorisation by design (see Decisions) |
| Stored data | Notes, chats, messages. No personal data, no credentials |
| Data volume | Tiny, single user, local. Lists bounded by `limit`; the three ordered queries are indexed; chat detail loads messages in one query |
| Dependency failure | Postgres only. `pool_pre_ping=True`, 5 s connect timeout. Connection failure → 503 with a logged error. Compose waits for Postgres health before starting the backend; the entrypoint migrates before serving |
| Multi-step writes | Message insert and chat `updated_at` bump share one transaction. Chat delete cascades in the database |
| Migrations | Every Alembic revision has a working `downgrade()` |
| Observability | JSON log per request: method, path, status, duration_ms, request_id. Error handlers log before responding. Uvicorn loggers use the same formatter. No print |
| Testing | pytest. `unit` suite (schemas) is the push gate with Ruff and mypy. `integration` suite runs against `taskmind_test` in CI with a Postgres service container; migrations applied once per session, each test in a rolled-back transaction |
| Cloud, monitoring, alerts | Not applicable: nothing deploys. `Cloud platform: none`, `Environments: none`, `Alerts channel: none` |

## Edge cases

- Whitespace-only title or message → 422.
- Title over the max length → 422.
- Non-integer id in the path → 422. Unknown integer id → 404.
- `limit` of 0 or over 100, negative `offset` → 422.
- Message posted to a missing chat → 404, nothing written.
- Deleting an already-deleted item → 404 (nothing destroyed twice).
- Postgres unreachable → 503 on data endpoints and `/health`.

## Testing design

- `tests/unit/test_schemas.py`: strip-and-reject-empty on titles and content; max lengths;
  `content` default on `NoteCreate`.
- `tests/integration/test_notes.py`: create returns 201 with the item; list newest first and bounded;
  get, update, delete; 404s on missing; 422 on invalid.
- `tests/integration/test_chats.py`: create, list by `updated_at` desc, rename, delete cascades;
  get returns messages oldest first; add message bumps `updated_at`; 404 for a missing chat.
- `tests/integration/test_health.py`: 200 when the database answers.

Fixtures: session-scoped engine on `TEST_DATABASE_URL` that runs `alembic upgrade head`;
function-scoped connection + transaction + `Session`, injected through `app.dependency_overrides`
for `get_db`, rolled back after each test.

## Delivery

Five pull requests, each reviewed by Hitesh before the next builds on it:

1. Repo scaffold: `AGENTS.md`/`CLAUDE.md`, `pyproject.toml`, tooling config, Compose with Postgres,
   `.env.example`, CI workflow running lint, types and the (empty) test suites.
2. Models, database setup and the initial Alembic migration.
3. Notes endpoints and tests.
4. Chats and messages endpoints and tests.
5. Backend Dockerfile, Compose backend service, health endpoint, README setup section.

## Documentation Notes

- Greenfield conventions (layout, naming, error shape, logging fields) → **AGENTS.md** Architecture & Structure, new: nothing exists yet.
- No authorisation by design → **AGENTS.md** Quirks & Gotchas, and **README** Decisions.
- `taskmind_test` created by the Postgres init script, which only runs on a fresh volume → **AGENTS.md** Quirks & Gotchas.
- Message insert bumps chat `updated_at` → **code** `app/routers/chats.py` docstring.
