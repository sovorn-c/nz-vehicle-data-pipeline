"""Acceptance test verifying fail-closed CI pipeline contract (e04s04)."""

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).parent.parent.parent


def test_ci_workflow_contract(repo_root: Path) -> None:
    """Verify GitHub Actions CI workflow exists and defines locked checks against PostgreSQL."""
    workflow_path = repo_root / ".github" / "workflows" / "ci.yml"
    assert workflow_path.exists(), f"CI workflow missing at {workflow_path}"

    content = workflow_path.read_text(encoding="utf-8")

    # Verify PostgreSQL service
    assert "postgres" in content.lower()
    assert "pg_isready" in content or "health" in content.lower()

    # Verify locked check script execution
    assert "scripts/check.sh" in content
    assert "setup-uv" in content or "uv" in content


def test_check_script_contract(repo_root: Path) -> None:
    """Verify scripts/check.sh runs lint, types, full tests, migration cycle, and build."""
    check_path = repo_root / "scripts" / "check.sh"
    assert check_path.exists(), f"Quality check script missing at {check_path}"

    content = check_path.read_text(encoding="utf-8")

    # Must be fail-closed
    assert "set -euo pipefail" in content

    # Must include all required quality gates
    assert "ruff check" in content
    assert "mypy" in content
    assert "pytest" in content
    assert "alembic upgrade head" in content
    assert "alembic downgrade" in content
    assert "uv build" in content
