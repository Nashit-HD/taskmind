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
- ⚠️ **The test database is `<POSTGRES_DB>_test`, created by `docker/postgres/init/` only on a fresh volume** — if it is missing, `docker compose down -v` then `up -d db`.
- ⚠️ **Tests read only `TEST_DATABASE_URL` and refuse a database whose name does not end in `_test`** — set it in `.env` or the environment; the test process overrides `DATABASE_URL` with it.
- ⚠️ **Compose refuses to start without `POSTGRES_PASSWORD`** — `cp .env.example .env` first; `.env` is gitignored.
- ⚠️ **Port 5432 may be taken by another project's Postgres** — set `POSTGRES_PORT` in `.env` and use the same port in `DATABASE_URL` and `TEST_DATABASE_URL`.
- ⚠️ **`get_settings()` is cached** — a test that changes env must call `get_settings.cache_clear()` after.
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
