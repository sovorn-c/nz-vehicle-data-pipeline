"""Acceptance tests verifying complete reviewer documentation contract in README.md (e04s04)."""

from pathlib import Path

import pytest

from nz_vehicle_data_pipeline.normalization.staging_models import SYNTHETIC_DISCLAIMER


@pytest.fixture
def readme_content() -> str:
    readme_path = Path(__file__).parent.parent.parent / "README.md"
    assert readme_path.exists(), f"README.md missing at {readme_path}"
    return readme_path.read_text(encoding="utf-8")


def test_readme_contains_architecture_and_data_flow(readme_content: str) -> None:
    """Verify README contains architectural overview and data-flow diagram."""
    assert "```mermaid" in readme_content or "mermaid" in readme_content.lower()
    assert "Architecture" in readme_content
    assert "Reconciliation" in readme_content
    assert "Provenance" in readme_content


def test_readme_contains_commands_and_examples(readme_content: str) -> None:
    """Verify README documents exact commands for startup, seed, smoke, checks, and cleanup."""
    assert "docker compose up" in readme_content
    assert "smoke-local.sh" in readme_content
    assert "check.sh" in readme_content
    assert "docker compose down" in readme_content
    assert "curl" in readme_content or "/v1/vehicles/" in readme_content


def test_readme_contains_attributions_disclaimer_and_generalization(
    readme_content: str,
) -> None:
    """Verify README contains source classifications, disclaimer, and generalization."""
    assert SYNTHETIC_DISCLAIMER in readme_content
    assert "NHTSA" in readme_content
    assert "NZTA" in readme_content
    assert "Synthetic" in readme_content
    assert "Generalization" in readme_content or "domain-generalization" in readme_content.lower()
