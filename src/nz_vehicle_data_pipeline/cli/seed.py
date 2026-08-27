"""Seed command executing deterministic offline release scenarios against PostgreSQL (e04s03)."""

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nz_vehicle_data_pipeline.connectors.base import SourceConnector
from nz_vehicle_data_pipeline.connectors.dealer import SyntheticDealerConnector
from nz_vehicle_data_pipeline.connectors.dealer_xml import DealerXMLConnector
from nz_vehicle_data_pipeline.connectors.nhtsa import NHTSAVPICConnector
from nz_vehicle_data_pipeline.connectors.nzta_csv import NZTAFleetCSVConnector
from nz_vehicle_data_pipeline.connectors.ppsr_synthetic import SyntheticPPSRConnector
from nz_vehicle_data_pipeline.connectors.stolen_synthetic import (
    SyntheticStolenConnector,
)
from nz_vehicle_data_pipeline.connectors.writeoff_synthetic import (
    SyntheticWriteoffConnector,
)
from nz_vehicle_data_pipeline.persistence.canonical_store import (
    PostgresCanonicalStore,
)
from nz_vehicle_data_pipeline.persistence.observation_store import (
    PostgresObservationStore,
)
from nz_vehicle_data_pipeline.pipeline.release_runner import (
    ReleasePipeline,
    ReleasePipelineSummary,
)


def load_connectors_from_manifest(
    manifest_data: dict[str, Any], fixtures_dir: Path
) -> list[SourceConnector]:
    """Instantiate connectors for each source listed in the manifest."""
    connectors: list[SourceConnector] = []

    for src in manifest_data["sources"]:
        file_path = fixtures_dir / src["path"]
        fmt = src.get("format", "json")
        source_system = src["source_system"]

        match source_system:
            case "NHTSA_VPIC":
                data = json.loads(file_path.read_text(encoding="utf-8"))
                connectors.append(NHTSAVPICConnector(data=data))
            case "NZTA_MVR":
                csv_text = file_path.read_text(encoding="utf-8")
                connectors.append(NZTAFleetCSVConnector(csv_content=csv_text))
            case "DEALER_FEED":
                if fmt == "xml":
                    xml_text = file_path.read_text(encoding="utf-8")
                    connectors.append(DealerXMLConnector([("LST_HYUNDAI_02", xml_text)]))
                else:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    connectors.append(SyntheticDealerConnector(data=data))
            case "PPSR_SYNTHETIC":
                data = json.loads(file_path.read_text(encoding="utf-8"))
                connectors.append(SyntheticPPSRConnector(data=data))
            case "STOLEN_SYNTHETIC":
                data = json.loads(file_path.read_text(encoding="utf-8"))
                connectors.append(SyntheticStolenConnector(data=data))
            case "WRITEOFF_SYNTHETIC":
                data = json.loads(file_path.read_text(encoding="utf-8"))
                connectors.append(SyntheticWriteoffConnector(data=data))
            case _:
                msg = f"Unknown source system in manifest: {source_system}"
                raise ValueError(msg)

    return connectors


async def run_seed(
    manifest_path: Path,
    db_url: str,
    as_of: datetime | None = None,
) -> ReleasePipelineSummary:
    """Execute complete release scenario seed into PostgreSQL."""
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_data = json.loads(manifest_text)
    fixtures_dir = manifest_path.parent

    manifest_as_of_str = manifest_data.get("as_of")
    eval_as_of = as_of or (
        datetime.fromisoformat(manifest_as_of_str) if manifest_as_of_str else datetime.now(UTC)
    )

    connectors = load_connectors_from_manifest(manifest_data, fixtures_dir)

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            obs_store = PostgresObservationStore(session)
            can_store = PostgresCanonicalStore(session)
            pipeline = ReleasePipeline(obs_store=obs_store, canonical_store=can_store)

            summary = await pipeline.run(
                connectors=connectors,
                as_of=eval_as_of,
                manifest_id=manifest_data["manifest_id"],
            )

            # Contract verification against manifest expected outcomes
            expected = manifest_data.get("expected_outcomes")
            if expected:
                if (
                    "total_observations" in expected
                    and summary.total_observations != expected["total_observations"]
                ):
                    msg = (
                        f"Expected {expected['total_observations']} observations, "
                        f"got {summary.total_observations}"
                    )
                    raise ValueError(msg)
                if (
                    "vehicles_count" in expected
                    and summary.vehicles_processed != expected["vehicles_count"]
                ):
                    msg = (
                        f"Expected {expected['vehicles_count']} vehicles processed, "
                        f"got {summary.vehicles_processed}"
                    )
                    raise ValueError(msg)

            return summary
    finally:
        await engine.dispose()


def main() -> None:
    """Entrypoint for CLI seed invocation."""
    parser = argparse.ArgumentParser(
        description="Seed database with deterministic release scenarios."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("fixtures/manifest.json"),
        help="Path to release manifest",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL"),
        help="Target PostgreSQL database URL",
    )

    args = parser.parse_args()

    db_url = args.database_url
    if not db_url:
        print("Error: DATABASE_URL must be set or passed via --database-url", file=sys.stderr)
        sys.exit(1)

    try:
        summary = asyncio.run(run_seed(args.manifest, db_url))
        print(summary.model_dump_json(indent=2))
    except Exception as exc:
        print(f"Seed command failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
