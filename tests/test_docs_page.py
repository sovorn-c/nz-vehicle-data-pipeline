"""Contract tests for the branded API documentation page."""

from fastapi.testclient import TestClient

from nz_vehicle_data_pipeline.api.app import app


def test_docs_page_is_branded_and_keeps_openapi_contract() -> None:
    """Verify the custom docs surface is available without replacing OpenAPI JSON."""
    client = TestClient(app)

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert "Evidence, not guesswork." in docs.text
    assert "/v1/vehicles/{vin}" in docs.text
    assert "1HGCR2F85HA000000" in docs.text
    assert "/openapi.json" in docs.text

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/v1/vehicles/{vin}" in openapi.json()["paths"]
    assert "/docs" not in openapi.json()["paths"]


def test_default_swagger_and_redoc_surfaces_are_not_served() -> None:
    """Verify the old generated docs surfaces do not compete with the new explorer."""
    client = TestClient(app)

    assert client.get("/redoc").status_code == 404
    assert "swagger-ui" not in client.get("/docs").text
