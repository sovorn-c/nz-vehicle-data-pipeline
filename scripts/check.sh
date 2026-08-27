#!/usr/bin/env bash
set -euo pipefail

echo "==> Running Ruff check..."
uv run ruff check .

echo "==> Running Ruff format check..."
uv run ruff format --check .

echo "==> Running Mypy type check..."
uv run mypy src tests

echo "==> Running Pytest suite..."
if [[ -n "${TEST_DATABASE_URL:-}" ]]; then
    uv run pytest
elif [[ -f "scripts/test-postgres.sh" ]]; then
    bash scripts/test-postgres.sh
else
    uv run pytest
fi

echo "==> Verifying Alembic migration and rollback cycle..."
MIG_DB_URL="${DATABASE_URL:-${TEST_DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:54329/postgres}}"
DATABASE_URL="$MIG_DB_URL" uv run alembic upgrade head
DATABASE_URL="$MIG_DB_URL" uv run alembic downgrade base
DATABASE_URL="$MIG_DB_URL" uv run alembic upgrade head

echo "==> Building distribution package..."
uv build

echo "==> All quality checks passed!"
