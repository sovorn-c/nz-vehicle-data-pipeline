"""Smoke test for nz_vehicle_data_pipeline."""

import nz_vehicle_data_pipeline


def test_package_version() -> None:
    """Verify package exposes version."""
    assert nz_vehicle_data_pipeline.__version__ == "0.1.0"
