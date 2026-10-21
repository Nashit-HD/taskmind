# TaskMind backend — design

**Date:** 2026-10-20, revised 2026-10-21 · **Status:** approved · **Scope:** backend and database

Related decisions: `docs/adr/`. Terms: `GLOSSARY.md` (a note's **author**, a chat's **user**, the **assistant**).

## Intent

Build the TaskMind backend: a FastAPI service over PostgreSQL where signed-in users share notes,
and anyone can open a chat on a note to ask an AI assistant questions that it answers from the
note's content. Alembic migrations, pytest against a separate test database, and a Docker Compose
stack that starts Postgres and the backend. The frontend is a separate design.

The assignment is an up-skilling exercise reviewed by Hitesh. Clean, working, well-structured code
matters more than feature count.

### Revision on 2026-10-21

After discussion with Hitesh the scope grew from the original assignment document:

1. Users sign in. Every signed-in user can see all notes and create notes. Only a note's author can
   edit or delete it.
2. Every chat belongs to one note and to the one user who opened it. Anyone signed in can open a
   chat on any note, and nobody else can see that chat (ADR 0003).
3. When the user posts a message in their chat, the assistant replies, using only the note's content.

The original assignment's standalone `/chats` endpoints are replaced by note-scoped ones.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| ORM and driver | SQLAlchemy 2.0, synchronous, psycopg 3 | Simplest to read and test. Separate Pydantic schemas are required by the assignment, so SQLModel saves nothing. Async adds moving parts with no benefit at this load |
| Python | 3.13, pinned in `.python-version` | 3.14 is weeks old and some wheels lag |
| Package manager | uv, with a committed `uv.lock` | Lockfile and pinned runtime per the devops policy |
| Lint, format, types | Ruff (lint + format), mypy `--strict` | Assignment asks for Ruff; typed code needs a checker |
| FastAPI conventions | `Annotated` parameters and dependencies, return types on handlers, plain `def` handlers for database work, router-level prefix/tags/dependencies, `fastapi dev` / `fastapi run` with the entrypoint in `pyproject.toml` | The official FastAPI skill's conventions |
| Primary keys | Integer, auto-increment | Simplest correct choice |
| Timestamps | `timestamptz`, UTC, serialised as ISO 8601 | Assignment requires ISO 8601 UTC |
| Layers | Routers call the session directly; one `assistant` module wraps the OpenAI call | Routers, schemas, models and session setup as the assignment asks. The assistant is the one piece with an outbound dependency, so it gets its own module and is injected as a dependency so tests can replace it |
| Authentication | Email + password; Argon2id via `pwdlib`; JWT (HS256, `pyjwt`) sent as `Authorization: Bearer` | HD's password-hashing decision. Bearer tokens need no CSRF handling for the Next.js client |
| Token lifetime | 60 minutes, no refresh token | A product decision for a practice app. The server enforces `exp` |
| Authorisation | Every `/notes` and `/chats` route requires a signed-in user. Notes: anyone signed in reads and creates; edit and delete are author-only (403 otherwise). Chats: anyone signed in opens a chat on any note; listing, reading, renaming, deleting and posting to a chat are for its user only (403 otherwise) | Checked against the actor from the token, never an id in the request. Private chats per ADR 0003 |
| List bounds | `limit` (default 50, max 100) and `offset` on every list endpoint | Result sets must be bounded. Also covers the pagination bonus |
| Health | `GET /health` runs `SELECT 1`; 200 or 503 | Reports the database, not just liveness. Compose uses it as the backend healthcheck |
| Error shape | FastAPI's default `{"detail": ...}` | One shape everywhere. 422 bodies keep FastAPI's list under `detail` |
| Database down | 503 `{"detail": "Database unavailable"}` | Degrades to a clear error instead of a 500 with a stack trace |
| Assistant down | 502 `{"detail": "Assistant unavailable"}`; nothing is written | The user message and the reply are stored in one transaction, so a failed call leaves no half-conversation. The user re-sends |
| Assistant grounding | System prompt carries the note's title and content and instructs the model to answer only from it, and to say when the note does not cover the question. The last 20 messages of the chat are sent as history | "Use only what is in the note", and bounded payloads |
| AI provider | OpenAI, model name in `OPENAI_MODEL`, key in `OPENAI_API_KEY` | Chosen by the team. Timeout 30 s, the SDK's bounded retries on transient failures only |
| Logging | Standard-library logging with a JSON formatter; `X-Request-Id` accepted or generated | Structured logs with a correlation id, no new dependency |
| Project type | `prototype` | Nothing deploys and there are no real users. Coverage target seeded at 20%; we aim far higher |

## Data model

| Table | Columns | Notes |
|---|---|---|
| `users` | `id` int PK; `email` varchar(254) not null, unique, stored lower-cased; `password_hash` text not null; `created_at` timestamptz not null | |
| `notes` | `id` int PK; `author_id` int FK → `users.id` not null; `title` varchar(200) not null; `content` text not null default `''`; `created_at`, `updated_at` timestamptz not null | Index on `created_at` for "newest first" |
| `chats` | `id` int PK; `note_id` int FK → `notes.id` on delete cascade, not null; `user_id` int FK → `users.id` not null, the user the chat belongs to; `title` varchar(100) not null; `created_at`, `updated_at` timestamptz not null | Index on `(note_id, user_id, updated_at)` for "this user's chats on this note, most recently updated first" |
| `messages` | `id` int PK; `chat_id` int FK → `chats.id` on delete cascade, not null; `role` varchar(16) not null, one of `user`, `assistant`; `content` text not null; `created_at` timestamptz not null | Index on `(chat_id, created_at)` for "oldest first" within a chat |

`created_at` and `updated_at` are set by the database (`server_default=now()`), and `updated_at`
is refreshed on update. Posting a message updates the parent chat's `updated_at` in the same
transaction.

Deleting a note cascades to its chats, and deleting a chat cascades to its messages, in the
database. Deleting a user is not an endpoint.

## Schemas

Request and response schemas are separate classes.

| Resource | Request | Response |
|---|---|---|
| Auth | `UserRegister(email, password)`, `UserLogin(email, password)` | `UserRead(id, email, created_at)`; `Token(access_token, token_type="bearer")` |
| Note | `NoteCreate(title, content="")`, `NoteUpdate(title, content)` | `NoteRead(id, author_id, title, content, created_at, updated_at)` |
| Chat | `ChatCreate(title)`, `ChatUpdate(title)` | `ChatRead(id, note_id, user_id, title, created_at, updated_at)`; `ChatDetail = ChatRead + messages: list[MessageRead]` |
| Message | `MessageCreate(content)` | `MessageRead(id, chat_id, role, content, created_at)`; `MessageExchange(user_message: MessageRead, assistant_message: MessageRead)` |

Titles and message content are stripped of surrounding whitespace and must be non-empty after
stripping. Titles respect the max lengths (200 for notes, 100 for chats). Message content is capped
at 4000 characters. Passwords are 8 to 128 characters. Emails are validated by Pydantic's
`EmailStr`. `PUT` replaces, so update schemas require every field.

## Endpoints

All routes below `/auth/register` and `/auth/login` require a valid bearer token; a missing or
invalid token returns 401 with `WWW-Authenticate: Bearer`.

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/health` | 200 `{"status": "ok"}` or 503 | no auth |
| POST | `/auth/register` | 201 `UserRead` / 409 | 409 when the email exists |
| POST | `/auth/login` | 200 `Token` / 401 | same 401 body for unknown email and wrong password |
| GET | `/auth/me` | 200 `UserRead` | |
| GET | `/notes?limit=&offset=` | 200 `list[NoteRead]` | all users' notes, newest first |
| POST | `/notes` | 201 `NoteRead` | author is the caller |
| GET | `/notes/{id}` | 200 `NoteRead` / 404 | |
| PUT | `/notes/{id}` | 200 `NoteRead` / 403 / 404 | author only |
| DELETE | `/notes/{id}` | 204 / 403 / 404 | author only; cascades to chats and messages |
| GET | `/notes/{id}/chats?limit=&offset=` | 200 `list[ChatRead]` / 404 | the caller's chats on the note, most recently updated first |
| POST | `/notes/{id}/chats` | 201 `ChatRead` / 404 | the chat belongs to the caller |
| GET | `/chats/{id}` | 200 `ChatDetail` / 403 / 404 | the chat's user only; messages oldest first, one query |
| PUT | `/chats/{id}` | 200 `ChatRead` / 403 / 404 | rename, the chat's user only |
| DELETE | `/chats/{id}` | 204 / 403 / 404 | the chat's user only; cascades to messages |
| POST | `/chats/{id}/messages` | 201 `MessageExchange` / 403 / 404 / 502 | the chat's user only; stores the user message, gets the assistant reply, stores it, bumps chat `updated_at`, all in one transaction |

Invalid bodies, non-integer ids and out-of-range `limit`/`offset` return 422. CORS allows
`http://localhost:3000`, read from settings.

## Code layout

```
backend/
├── app/
│   ├── main.py          create_app(): CORS, routers, exception handlers, logging setup
│   ├── config.py        Settings (pydantic-settings): DATABASE_URL, CORS_ORIGINS, JWT_SECRET, JWT_EXPIRE_MINUTES, OPENAI_API_KEY, OPENAI_MODEL
│   ├── database.py      engine, SessionLocal, Base, get_db dependency, SessionDep
│   ├── logging.py       JSON formatter, request-id middleware, per-request log line
│   ├── security.py      hash_password, verify_password, create_access_token, decode_access_token
│   ├── auth.py          get_current_user dependency, CurrentUserDep
│   ├── assistant.py     Assistant protocol, OpenAIAssistant, get_assistant dependency, AssistantDep
│   ├── models/          user.py, note.py, chat.py, message.py
│   ├── schemas/         user.py, note.py, chat.py, message.py
│   └── routers/         health.py, auth.py, notes.py, chats.py
├── alembic/             env.py reads DATABASE_URL from settings; versions/
├── alembic.ini
├── tests/
│   ├── conftest.py
│   ├── unit/            schemas, security helpers, assistant prompt building; no database, no network
│   └── integration/     endpoint tests against taskmind_test with a fake assistant
├── pyproject.toml, uv.lock, .python-version
├── Dockerfile, .dockerignore
```

## Configuration

| Variable | Used by | Example |
|---|---|---|
| `DATABASE_URL` | backend, Alembic | `postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind` |
| `TEST_DATABASE_URL` | pytest | `postgresql+psycopg://taskmind:taskmind@localhost:5432/taskmind_test` |
| `CORS_ORIGINS` | backend | `http://localhost:3000` |
| `JWT_SECRET` | backend | a long random string; `.env.example` says how to generate one, and ships a placeholder that the app refuses |
| `JWT_EXPIRE_MINUTES` | backend | `60` |
| `OPENAI_API_KEY` | backend | set locally, never committed |
| `OPENAI_MODEL` | backend | the model name, chosen at implementation time from the current OpenAI catalogue |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose `db` service | local dev values |

A committed `.env.example` holds local development values and placeholders. `.env` is ignored.
Compose overrides `DATABASE_URL` for the backend container so it reaches Postgres at host `db`.

## Docker Compose

- `db`: `postgres:17-alpine` pinned to an exact minor version, named volume `taskmind_pgdata`,
  healthcheck with `pg_isready`, an init script in `docker-entrypoint-initdb.d/` that creates
  `taskmind_test`.
- `backend`: built from `backend/Dockerfile`, `depends_on: db: condition: service_healthy`,
  entrypoint runs `alembic upgrade head` then `fastapi run` on port 8000, healthcheck on `/health`.
- `frontend`: added with the frontend design.

The Dockerfile uses a slim official Python image, installs dependencies from the lockfile in a
cached layer before copying source, runs as a non-root user, and has a `.dockerignore`.

## Policy answers

| Question | Answer |
|---|---|
| Existing patterns | Greenfield. The conventions above are chosen once and recorded in `AGENTS.md` |
| Trust boundary | Request bodies, path ids, `limit`/`offset`, the bearer token. Bodies and params validated by Pydantic and FastAPI typing. The token is verified (signature with the expected algorithm, `exp`) before any data access. `/auth/register` and `/auth/login` are the only unauthenticated data routes, plus `/health` |
| Authorisation | Router-level `get_current_user` on `/notes`, `/chats` and `/auth/me`. Ownership checks compare the row's `author_id` (notes) or `user_id` (chats) with the actor's id from the token; chat lists are filtered by the actor's id in the query. Default is deny: no token, bad token, expired token → 401; wrong user → 403 |
| Stored data | Users (email and password hash), notes, chats, messages. Email is personal data: it is needed to sign in, stays in the one table, and never appears in logs or in another user's responses (`NoteRead` carries `author_id`, not the email) |
| Credentials and secrets | Argon2id with library defaults. `JWT_SECRET` and `OPENAI_API_KEY` from the environment only. Login returns the same 401 for unknown email and wrong password. Error responses carry no stack traces, query text or tokens |
| Data volume | Tiny. Lists bounded by `limit`; ordered queries indexed; chat detail loads messages in one query; the assistant gets at most the last 20 messages and the one note |
| Dependency failure | Postgres: `pool_pre_ping=True`, 5 s connect timeout, 503 on connection failure, Compose waits for health, entrypoint migrates before serving. OpenAI: 30 s timeout, SDK retries (at most 2) on timeouts, connection errors, 429 and 5xx only, 502 on failure with nothing written. A failing assistant breaks only `POST /chats/{id}/messages`; every other route is unaffected |
| Multi-step writes | Message insert, assistant call, reply insert and chat `updated_at` bump are one transaction committed after the call succeeds. Deletes cascade in the database |
| Migrations | Every Alembic revision has a working `downgrade()` |
| Observability | JSON log per request: method, path, status, duration_ms, request_id, user_id where signed in. Error handlers log before responding. Each assistant call logs model, prompt and completion token counts, latency and request_id with the call site. No prompt or note content in logs. OpenInference tracing to Arize Phoenix is HD's standard for agentic flows and is not in this scope: recorded as a gap below |
| Testing | pytest. `unit` suite (schemas, password and token helpers, prompt building) is the push gate with Ruff and mypy. `integration` suite runs against `taskmind_test` in CI with a Postgres service container; the assistant dependency is overridden with a fake that returns a fixed reply, so no test reaches the network |
| Cloud, monitoring, alerts | Not applicable: nothing deploys. `Cloud platform: none`, `Environments: none`, `Alerts channel: none` |

## Edge cases

- Whitespace-only title or message → 422. Title over the max length → 422. Message over 4000 chars → 422.
- Register with an existing email, any letter case → 409.
- Login with unknown email or wrong password → 401, identical body.
- Expired or tampered token → 401. Token signed with a different algorithm → 401.
- Non-integer id in the path → 422. Unknown integer id → 404.
- Editing or deleting another user's note → 403, nothing changed.
- Listing never shows another user's chats; reading, renaming, deleting or posting to one → 403, nothing changed.
- `limit` of 0 or over 100, negative `offset` → 422.
- Chat opened on a missing note, message posted to a missing chat → 404, nothing written.
- Deleting an already-deleted item → 404.
- Assistant times out or errors → 502, the user message is not stored, chat `updated_at` unchanged.
- Postgres unreachable → 503 on data endpoints and `/health`.

## Testing design

- `tests/unit/test_schemas.py`: strip-and-reject-empty on titles and content; max lengths; password
  length bounds; `content` default on `NoteCreate`.
- `tests/unit/test_security.py`: hash verifies and a wrong password does not; token round-trips;
  expired token and wrong-secret token are rejected.
- `tests/unit/test_assistant.py`: the prompt contains the note title and content and the grounding
  instruction; history is capped at 20 messages.
- `tests/integration/test_auth.py`: register 201; duplicate 409; login 200 with a token; bad
  password 401; `/auth/me` with and without a token.
- `tests/integration/test_notes.py`: create 201 with `author_id`; list newest first, bounded, shows
  other users' notes; get; update and delete by the author; 403 for another user; 404s; 422s.
- `tests/integration/test_chats.py`: create a chat on a note; list shows only the caller's chats,
  by `updated_at` desc; rename and delete by the chat's user; get, rename, delete and post return
  403 for another user; get returns messages oldest first; post message stores both messages with
  the fake assistant's reply and bumps `updated_at`; assistant failure gives 502 and stores nothing;
  404 for a missing chat or note; deleting a note removes its chats.
- `tests/integration/test_health.py`: 200 when the database answers.

Fixtures: session-scoped engine on `TEST_DATABASE_URL` that runs `alembic upgrade head`;
function-scoped connection + transaction + `Session`, injected through `app.dependency_overrides`
for `get_db`, rolled back after each test. A `user` fixture registers a user and returns its
bearer header; a `second_user` fixture does the same for 403 cases. A `fake_assistant` fixture
overrides `get_assistant`.

## Delivery

Pull requests, each reviewed by Hitesh before the next builds on it:

1. Repo scaffold: `AGENTS.md`/`CLAUDE.md`, `pyproject.toml`, tooling config, Compose with Postgres,
   `.env.example`, CI workflow running lint, types and the (empty) test suites.
2. Models, database setup and the initial Alembic migration (users, notes, chats, messages).
3. Auth: register, login, me, the current-user dependency, and tests.
4. Notes endpoints with ownership, and tests.
5. Note chats and messages with a stub assistant that echoes, and tests. The stub is the fake used
   in tests, wired as the default until PR 7.
6. Backend Dockerfile, Compose backend service, health endpoint, README setup section.
7. OpenAI assistant: the real `OpenAIAssistant`, configuration, call-site logging, and tests.

PRs 1 to 6 are the original week-1 milestone plus auth. PR 7 may land in week 2 alongside the
frontend; Hitesh should know that.

## Gaps against HD policy, recorded on purpose

- Observability rule 11 (OpenInference tracing viewed in Arize Phoenix for agentic flows) is not
  met. The assistant call logs model, tokens and latency with its request id instead. Adding
  Phoenix is a candidate for after the assignment.

## Documentation Notes

- Greenfield conventions (layout, naming, error shape, logging fields, dependency aliases) → **AGENTS.md** Architecture & Structure, new: nothing exists yet.
- Who may do what (signed-in for everything; notes edited by their author; chats visible only to their user) → **AGENTS.md** Quirks & Gotchas, and **README** Decisions.
- `taskmind_test` created by the Postgres init script, which only runs on a fresh volume → **AGENTS.md** Quirks & Gotchas.
- Message post is one transaction around the assistant call → **code** `app/routers/chats.py` docstring.
- The assistant is a dependency so tests replace it; never call OpenAI directly from a router → **AGENTS.md** Architecture & Structure.
