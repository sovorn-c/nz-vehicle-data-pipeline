"""PostgreSQL persistence layer for raw observations and canonical state (ADR 0001, ADR 0004)."""

from nz_vehicle_data_pipeline.persistence.canonical_store import (
    CanonicalRevisionRecord,
    PostgresCanonicalStore,
)
from nz_vehicle_data_pipeline.persistence.database import (
    get_db_session,
    get_engine,
    get_session_factory,
    init_db,
)
from nz_vehicle_data_pipeline.persistence.models import (
    Base,
    CanonicalRevisionRow,
    SourceObservationRow,
    VehicleRow,
)
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)

__all__ = [
    "Base",
    "CanonicalRevisionRecord",
    "CanonicalRevisionRow",
    "PostgresCanonicalStore",
    "PostgresObservationStore",
    "SourceObservationRow",
    "VehicleRow",
    "get_db_session",
    "get_engine",
    "get_session_factory",
    "init_db",
]
