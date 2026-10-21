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
