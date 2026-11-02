#!/bin/sh
# Migrate, then serve. Postgres is reachable by the time this runs, because Compose waits for the
# db healthcheck. A failed migration stops the container with the error in its logs.
set -eu

alembic upgrade head
exec fastapi run --host 0.0.0.0 --port 8000
