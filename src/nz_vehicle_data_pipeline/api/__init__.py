"""FastAPI OpenAPI service layer (ADR 0004)."""

from nz_vehicle_data_pipeline.api.app import app, create_app

__all__ = [
    "app",
    "create_app",
]
