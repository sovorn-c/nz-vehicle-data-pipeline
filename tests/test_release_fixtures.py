"""Unit tests validating offline release fixtures and manifest integrity (e04s03)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def manifest_data(fixtures_dir: Path) -> dict[str, Any]:
    manifest_path = fixtures_dir / "manifest.json"
    assert manifest_path.exists(), f"Manifest file not found at {manifest_path}"
    with open(manifest_path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def test_manifest_schema_and_file_hashes(fixtures_dir: Path, manifest_data: dict[str, Any]) -> None:
    """Verify all files listed in manifest exist and match their declared SHA-256 digests."""
    assert manifest_data["manifest_id"] == "release-manifest-2026.08"
    assert "sources" in manifest_data

    for src in manifest_data["sources"]:
        rel_path = src["path"]
        expected_hash = src["sha256"]
        file_path = fixtures_dir / rel_path
        assert file_path.exists(), f"Fixture file {file_path} missing"

        actual_bytes = file_path.read_bytes()
        actual_hash = hashlib.sha256(actual_bytes).hexdigest()
        assert actual_hash == expected_hash, (
            f"Hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}"
        )


def test_fixtures_cover_all_required_release_scenarios(manifest_data: dict[str, Any]) -> None:
    """Verify manifest covers all required release scenarios."""
    scenarios = manifest_data.get("scenarios", {})
    required_scenarios = [
        "clean_vehicle",
        "risky_vehicle",
        "unknown_vehicle",
        "conflict_vehicle",
        "dealer_parity",
        "evidence_only_nzta",
        "malformed_record",
    ]
    for req in required_scenarios:
        assert req in scenarios, f"Required scenario '{req}' missing from manifest"
