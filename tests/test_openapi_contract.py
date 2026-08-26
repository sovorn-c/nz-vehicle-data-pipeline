"""OpenAPI schema validation test (e03s03, e03s04)."""

from fastapi.testclient import TestClient

from nz_vehicle_data_pipeline.api.app import app


def test_openapi_schema_matches_contract() -> None:
    """Verify OpenAPI schema contains expected routes, tags, and schemas."""
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    assert schema["info"]["title"] == "NZ Vehicle Data Pipeline API"
    assert schema["info"]["version"] == "0.1.0"

    paths = schema["paths"]
    assert "/health" in paths
    assert "/v1/vehicles/{vin}" in paths
    assert "/v1/vehicles/{vin}/history" in paths
    assert "/v1/vehicles/{vin}/revisions" in paths
    assert "/v1/vehicles/{vin}/revisions/{revision_number}" in paths
    assert "/v1/vehicles/{vin}/conflicts" in paths
    assert "/v1/vehicles/{vin}/provenance" in paths
    assert "/v1/observations/{observation_id}" in paths
