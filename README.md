# TaskMind

A small notes and chat app: a Next.js frontend and a FastAPI backend over PostgreSQL, run locally
with Docker Compose. Signed-in users share notes, and anyone can open a chat on a note to ask an AI
assistant about it.

## Structure

- `backend/` — FastAPI API, SQLAlchemy models, Alembic migrations, pytest tests
- `frontend/` — Next.js app, Vitest tests
- `docs/plans/` — design specs and implementation plans
- `docs/adr/` — decisions already taken; `GLOSSARY.md` — the domain language
- `docker/` — files mounted into Compose services

## Prerequisites

- Docker Desktop (Compose v2)
- [uv](https://docs.astral.sh/uv/) 0.11.24. It installs the pinned Python itself.
- Node.js 24.22.2 (`frontend/.node-version`) with npm, only to run the frontend outside Docker.

## Running everything with Docker

```bash
cp .env.example .env          # then set JWT_SECRET; the comment says how to generate one
docker compose up --build     # Postgres, the backend on :8000, then the frontend on :3000
```

Open http://localhost:3000, register with an email and a password of 8 or more characters, and you
are on the notes page. The backend container runs the migrations and then serves. `/health`
answers 200 once the database does, and the OpenAPI docs are at http://localhost:8000/docs. Data
lives on a named volume and survives `docker compose down`; `docker compose down -v` wipes it.
Logs are JSON on `docker compose logs -f backend`.

If a port is taken, set `POSTGRES_PORT`, `BACKEND_PORT` or `FRONTEND_PORT` in `.env`. For Postgres,
use the same port in `DATABASE_URL` and `TEST_DATABASE_URL`; for the backend, set
`NEXT_PUBLIC_API_URL` to match; for the frontend, set `CORS_ORIGINS` to match.

## Running the backend outside Docker

For development with reload and the tests:

```bash
docker compose up -d db       # Postgres only
cd backend && uv sync --locked
```

### Serving with reload

```bash
cd backend
uv run alembic upgrade head    # create or update the tables
uv run fastapi dev
```

The API is at http://localhost:8000 and the OpenAPI docs at http://localhost:8000/docs.

### Signing in

Set `JWT_SECRET` in `.env` first; the app refuses the placeholder. Then:

```bash
curl -s -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "correct horse battery"}'
curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "correct horse battery"}'
curl -s localhost:8000/auth/me -H "Authorization: Bearer <access_token>"
```

Tokens last `JWT_EXPIRE_MINUTES` (default 60). On `/docs`, the Authorize button takes the token.

### Notes

Every signed-in user sees every note; only the author can change or delete one.

```bash
TOKEN=<access_token>
curl -s -X POST localhost:8000/notes -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan", "content": "Ship the notes API"}'
curl -s 'localhost:8000/notes?limit=10&offset=0' -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PUT localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan", "content": "Shipped"}'
curl -s -X DELETE localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN" -o /dev/null -w '%{http_code}\n'
```

`limit` is 1 to 100 (default 50). Changing someone else's note is a 403; a missing note is a 404.

### Chats

A chat belongs to one note and is private to the user who opened it. Posting a message stores it,
asks the assistant, and stores the reply. Without an `OPENAI_API_KEY` the assistant is an echo, so the
flow can be tried without a key.

```bash
curl -s -X POST localhost:8000/notes/1/chats -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Questions"}'
curl -s localhost:8000/notes/1/chats -H "Authorization: Bearer $TOKEN"
curl -s -X POST localhost:8000/chats/1/messages -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"content": "What is the plan?"}'
curl -s localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PUT localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan questions"}'
curl -s -X DELETE localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN" -o /dev/null -w '%{http_code}\n'
```

A chat detail carries its most recent 200 messages, oldest first. Messages are at most 4000
characters. Another user's chat is a 403; if the assistant fails the reply is a 502 and nothing
is stored.

### The assistant

Set `OPENAI_API_KEY` in `.env` and the assistant answers through OpenAI, using only the note the
chat belongs to; `OPENAI_MODEL` picks the model. Leave the key empty and an echo answers instead,
so everything else can be tried without a key; the log says so once at the first message.

Each call has a 30-second timeout and at most two retries on transient errors. If it still fails,
the message post is a 502 and nothing is stored, so re-send it.

## Running the frontend outside Docker

With the backend up (in Docker or with `fastapi dev`):

```bash
cd frontend
npm ci
npm run dev                    # http://localhost:3000, reloads on save
```

The app reads `NEXT_PUBLIC_API_URL` at build time; it defaults to http://localhost:8000. The pages:

- `/sign-in` — register or sign in. The token is kept for the tab and dropped when it closes.
- `/notes` — every user's notes, newest first; create a note, and edit or delete your own, with a
  confirmation before a delete.
- `/notes/{id}/chats` — your chats on that note in a sidebar: start one, rename it, delete it.
- `/notes/{id}/chats/{chatId}` — the chat: its messages oldest first, and a box to ask the
  assistant. The reply appears under your message without a reload.

Every form refuses an empty title or message before anything is sent, and shows the API's own
message when a request fails. A 401 from the API sends you back to sign in.

Lint, format, type check and test:

```bash
cd frontend && npm run validate
```

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

Frontend tests, with coverage:

```bash
cd frontend && npm run test:coverage
```

They run in jsdom with `fetch` stubbed, so no test needs the API. CI runs `npm run validate` and
`diff-cover` on the changed lines, and a `compose` job that builds all three services and checks
both `/health` endpoints.

## Decisions

See `docs/plans/2026-10-20-backend-design.md` and `docs/adr/`. In short:

- SQLAlchemy 2.0 (sync) with psycopg 3; separate Pydantic request and response schemas.
- Email + password sign-in with Argon2id hashing and short-lived JWT bearer tokens, behind one
  `get_current_user` dependency (ADR 0002).
- Every signed-in user can read every note; only the author edits or deletes it.
- Chats belong to a note and are private to the user who opened them; the assistant answers from
  that note's content only.
- JSON logs with an `X-Request-Id` on every request and response.
- The browser calls the API directly with the bearer token kept in `sessionStorage` (ADR 0004);
  all calls go through `frontend/lib/api.ts`, which bounds every wait and turns errors into
  messages. Chats live under their note in the UI, as in the API, so the assignment's `/chats`
  page is `/notes/{id}/chats`.

## Unfinished and next steps

Written at the deadline, 2026-10-30, and after it: the frontend was finished on 2026-11-02. What
is built: every backend endpoint with 146 tests, Docker for both apps, and a frontend that covers
sign-in, notes, chats and messages with loading, error and validation states. What is not:

- **The assistant has not been tried against OpenAI.** No key was available; the echo assistant
  answered every test. First thing with a key: post a message and read the `openai call` log line.
- **No frontend end-to-end test.** The forms and the API client have unit tests; nothing drives a
  browser through sign-in to a chat. Next: Playwright against `docker compose up`, run in CI.
- **No paging in the UI.** The API bounds every list; the notes page shows the newest 50 and the
  sidebar the 50 most recent chats. Next: a "load more" on each, using `limit` and `offset`.
- **No search by title**, the assignment's first bonus. The API would need a query parameter and
  an index on `lower(title)`.
- **Token in `sessionStorage`** (ADR 0004). Beyond a prototype, an httpOnly cookie with a Next.js
  proxy route, and a refresh token so the hour-long session does not end mid-chat.
- **A slow assistant holds a worker thread.** Each message waits up to 100 s in the API's
  threadpool; 40 slow calls at once would stall every request. Next: an async handler with
  `AsyncOpenAI`, or a queue.
- **No tracing of the assistant call** beyond one log line with tokens and latency. HD's standard
  is OpenInference spans in Arize Phoenix.
- **No login rate limit** and no account lockout.
- **Required status checks on `main`** are not configured on the repository yet.
- **No dependency-update bot** for either manifest; updates are by hand until Dependabot or Renovate
  is switched on.
