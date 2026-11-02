# AGENTS.md
<!-- hd-skills REQUIRED SECTION: maintain-project-docs manages everything above the END marker -->
## Project Overview
TaskMind: shared notes with note-scoped AI chats. FastAPI + SQLAlchemy 2.0 + PostgreSQL backend in `backend/`; Next.js 16 (App Router, TypeScript strict) frontend in `frontend/`.
## Project Facts
- **Repo layout:** single-repo
- **Project type:** prototype
- **Components:**
  - backend — `backend/`
  - frontend — `frontend/`
- **Validate command:** `cd backend && uv run pytest tests/unit && uv run ruff check . && uv run ruff format --check . && uv run mypy && cd ../frontend && npm test && npm run lint && npm run format:check && npm run typecheck`
- **Lint / format command:** `cd backend && uv run ruff check --fix . && uv run ruff format . && cd ../frontend && npm run lint && npm run format`
- **Type check command:** `cd backend && uv run mypy && cd ../frontend && npm run typecheck`
- **Type check strictness:** `mypy --strict` (`strict = true` in `backend/pyproject.toml`); `tsc` with `strict` and `noUncheckedIndexedAccess` (`frontend/tsconfig.json`)
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
- **Framework:** pytest (backend), Vitest + Testing Library in jsdom (frontend)
- **Single target:** `cd backend && uv run pytest tests/unit/test_app.py`; frontend: `cd frontend && npx vitest run lib/api.test.ts`
- **Location / naming:** `backend/tests/{unit,integration}/test_*.py`, tests tree; `frontend/**/*.test.{ts,tsx}`, colocated. Suite commands run inside `backend/` or `frontend/`, as the Validate command does
- **Coverage target:** 20% — warns (prototype)
- **Suites:**
    - unit — `uv run pytest tests/unit` — gate
    - integration — `cd backend && uv run pytest --cov=app --cov-report=xml && uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=20` — ci
    - frontend-unit — `npm test` — gate
    - frontend-coverage — `cd frontend && npm run test:coverage && uvx diff-cover coverage/cobertura-coverage.xml --compare-branch=origin/main --fail-under=20` — ci
## Architecture & Structure
- `backend/app/main.py` — `create_app()`; the module-level `app` is served by `fastapi dev`/`fastapi run` via `[tool.fastapi]` in `pyproject.toml`
- `backend/app/config.py` — `Settings` from env, then the repo-root `.env`; `SettingsDep` for handlers
- `backend/app/logging.py` — JSON formatter, `X-Request-Id` middleware, one log line per request; pass fields as `extra={"fields": {...}}`
- `backend/app/assistant.py` — the `Assistant` protocol, `get_assistant` and `AssistantDep`; routers never call a provider directly. `build_assistant()` picks `OpenAIAssistant` when `OPENAI_API_KEY` is set, else `EchoAssistant`, once per process (cached); tests override the dependency or clear the cache
- `backend/app/pagination.py` — `LimitQuery`/`OffsetQuery`, the bounds every list endpoint shares
- `backend/app/routers/health.py` — `GET /health`, unauthenticated, 200 only when `SELECT 1` answers; the Compose healthcheck calls it
- `backend/Dockerfile` + `backend/entrypoint.sh` — pinned `python:3.13-slim`, deps from `uv.lock` with `--no-dev`, non-root; the entrypoint runs `alembic upgrade head` then `fastapi run`
- `frontend/lib/api.ts` — the one API client: every call adds the bearer token, has a timeout, and throws `ApiError` (the API's `detail`) or `NetworkError`; `errorMessage()` turns either into text for the UI
- `frontend/lib/session.ts` — the token in `sessionStorage` (ADR 0004) with `subscribe` for `useSyncExternalStore`; a 401 anywhere clears it
- `frontend/components/RequireAuth.tsx` — wraps the `app/(app)` route group: no token → `/sign-in`, else loads `/auth/me` and provides `useUser()`
- `frontend/app/(app)/notes/[noteId]/chats/` — chats live under their note: `layout.tsx` loads the note and holds `ChatsProvider` (the sidebar's list, shared with the chat view so a new message re-sorts it)
- `frontend/lib/validation.ts` — form checks that copy the API's limits; the API is the rule
- `frontend/Dockerfile` — pinned `node:24-alpine`, `npm ci`, `next build` with `output: "standalone"`, non-root `node` user; `NEXT_PUBLIC_API_URL` is a build argument
- Dependencies are `Annotated[..., Depends(...)]` aliases ending in `Dep`; handlers that touch the database are plain `def`
- Error shape is FastAPI's `{"detail": ...}` everywhere
- Observed through JSON logs on stdout (`docker compose logs backend`): one `info` line per request with `status` and `duration_ms`; a failure is an `error` line with `exception` and the same `request_id` the client received
## Key Commands
- Run everything: `docker compose up --build` (frontend on :3000, backend on :8000; needs a root `.env` with `POSTGRES_PASSWORD` and `JWT_SECRET`)
- Install: `cd backend && uv sync --locked`; `cd frontend && npm ci`
- Run API locally: `cd backend && uv run fastapi dev` (needs `db` up and a root `.env`)
- Run frontend locally: `cd frontend && npm run dev` (needs the API up)
- Database: `docker compose up -d db`; reset it: `docker compose down -v`
- Lint and format: `cd backend && uv run ruff check --fix . && uv run ruff format .`; `cd frontend && npm run lint && npm run format`
- Type check: `cd backend && uv run mypy`; `cd frontend && npm run typecheck`
- Unit tests: `cd backend && uv run pytest tests/unit`; `cd frontend && npm test`
- Integration tests: `cd backend && uv run pytest tests/integration` (needs `db` up)
## Workflows & Verification
- Before calling a change done, run the Validate command and read its output; run the integration suite when the change touches data or an endpoint
- CI (`.github/workflows/ci.yml`) runs the backend validate and integration jobs, the frontend validate and changed-line coverage, and a `compose` job that builds all three services, on every pull request
## Quirks & Gotchas
- ⚠️ **The test database is `<POSTGRES_DB>_test`, created by `docker/postgres/init/` only on a fresh volume** — if it is missing, `docker compose down -v` then `up -d db`.
- ⚠️ **Integration tests read only `TEST_DATABASE_URL` and refuse a database whose name does not end in `_test`** — set it in `.env` or the environment; unit tests need no database; the test process overrides `DATABASE_URL`.
- ⚠️ **Compose refuses to start without `POSTGRES_PASSWORD` and `JWT_SECRET`, even for `db` alone** — `cp .env.example .env` and set a real `JWT_SECRET`; `.env` is gitignored.
- ⚠️ **Port 5432 may be taken by another project's Postgres** — set `POSTGRES_PORT` in `.env` and use the same port in `DATABASE_URL` and `TEST_DATABASE_URL`.
- ⚠️ **`get_settings()` is cached** — a test that changes env must call `get_settings.cache_clear()` after.
- ⚠️ **`build_assistant()` is cached like `get_settings()`** — a test that sets `OPENAI_API_KEY` must clear both caches; `tests/conftest.py` unsets the key so no test ever calls OpenAI.
- ⚠️ **`NEXT_PUBLIC_API_URL` is baked into the frontend image** — after changing it, `docker compose up --build`. A new `FRONTEND_PORT` needs a matching `CORS_ORIGINS`.
- ⚠️ **Lint refuses `setState` directly in an effect** (React compiler rule) — key loaded state to its id instead of resetting it; see `RequireAuth.tsx`, `ChatsProvider.tsx`.
- ⚠️ **No AI attribution in commits or PR descriptions** — remove any `Co-Authored-By: Claude` or "Generated with" line before committing.
- ⚠️ **Read `GLOSSARY.md` and `docs/adr/` before changing the domain** — chats are private to their user (ADR 0003); use author, user, assistant, not owner, creator, bot.
<!-- END hd-skills REQUIRED SECTION: everything below is team-maintained; tooling never edits it -->

---

# Project Notes (team-maintained)

## Agent skills

### Issue tracker

Local markdown under `.scratch/<feature>/` (`spec.md` plus one `issues/NN-slug.md` per ticket). See `docs/agents/issue-tracker.md`.

### Triage labels

The default five roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
