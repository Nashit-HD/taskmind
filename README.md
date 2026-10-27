# TaskMind

A small notes and chat app: a Next.js frontend and a FastAPI backend over PostgreSQL, run locally
with Docker Compose. Signed-in users share notes, and anyone can open a chat on a note to ask an AI
assistant about it.

## Structure

- `backend/` — FastAPI API, SQLAlchemy models, Alembic migrations, pytest tests
- `frontend/` — Next.js app (not started)
- `docs/plans/` — design specs and implementation plans
- `docs/adr/` — decisions already taken; `GLOSSARY.md` — the domain language
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
cd backend
uv run alembic upgrade head    # create or update the tables
uv run fastapi dev
```

The API is at http://localhost:8000 and the OpenAPI docs at http://localhost:8000/docs.

### Changing the schema

Edit the models under `backend/app/models/`, then:

```bash
cd backend
uv run alembic revision --autogenerate -m "what changed"
```

Read the generated file under `backend/alembic/versions/`, check the names and `ondelete` rules,
and make sure `downgrade()` reverses `upgrade()`. Then `uv run alembic upgrade head`. The test
suite runs `alembic check`, so a model change without a migration fails CI.

## Running the tests

```bash
cd backend
uv run pytest tests/unit                 # no database needed
uv run pytest tests/integration          # needs `docker compose up -d db`; rebuilds the test database from the migrations
```

The integration suite reads `TEST_DATABASE_URL` from `.env` or the environment and refuses any
database whose name does not end in `_test`.

Lint, format and type check:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Decisions

See `docs/plans/2026-10-20-backend-design.md` and `docs/adr/`. In short:

- SQLAlchemy 2.0 (sync) with psycopg 3; separate Pydantic request and response schemas.
- Email + password sign-in with Argon2id hashing and short-lived JWT bearer tokens.
- Every signed-in user can read every note; only the author edits or deletes it.
- Chats belong to a note and are private to the user who opened them; the assistant answers from
  that note's content only.
- JSON logs with an `X-Request-Id` on every request and response.

## Unfinished and next steps

_Written at the deadline._
