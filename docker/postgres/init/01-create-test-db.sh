#!/bin/sh
# Runs once, when the taskmind_pgdata volume is first initialised. Creates the test database next
# to the main one and names it after it, so the name is declared only through POSTGRES_DB.
# To re-run it: docker compose down -v, then docker compose up.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE DATABASE \"${POSTGRES_DB}_test\""
