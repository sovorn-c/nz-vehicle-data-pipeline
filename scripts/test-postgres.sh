#!/usr/bin/env bash
set -euo pipefail

# Ensure TEST_DATABASE_URL defaults to the local PostgreSQL port
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:54329/postgres}"

exec uv run pytest "$@"
