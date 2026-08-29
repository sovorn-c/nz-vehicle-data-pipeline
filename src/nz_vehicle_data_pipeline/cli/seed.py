"""Seed command executing deterministic offline release scenarios against PostgreSQL (e04s03)."""

import argparse
import asyncio
import hashlib
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
    enable_phase2: bool = False,
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

            # Build deterministic capture_times from manifest
            capture_times_raw = manifest_data.get("capture_times", {})
            capture_times = {
                src_sys: datetime.fromisoformat(ts) for src_sys, ts in capture_times_raw.items()
            }
            run_id_prefix = manifest_data.get("manifest_id")

            # Fail-closed: validate all fixture hashes upfront before any pipeline run
            all_sources = list(manifest_data.get("sources", []))
            if enable_phase2 and "phase2" in manifest_data:
                all_sources.extend(manifest_data["phase2"].get("sources", []))

            for src in all_sources:
                file_path = fixtures_dir / src["path"]
                if not file_path.exists():
                    msg = f"Fixture file missing: {file_path}"
                    raise FileNotFoundError(msg)
                actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if actual_hash != src["sha256"]:
                    msg = (
                        f"Fixture hash mismatch for {src['path']}: "
                        f"expected {src['sha256']}, got {actual_hash}"
                    )
                    raise ValueError(msg)

            summary = await pipeline.run(
                connectors=connectors,
                capture_times=capture_times or None,
                as_of=eval_as_of,
                manifest_id=manifest_data["manifest_id"],
                run_id_prefix=run_id_prefix,
            )

            # Fail-closed: verify all expected outcome counts for Phase 1
            expected = manifest_data.get("expected_outcomes", {})
            checks = [
                ("total_observations", summary.total_observations),
                ("eligible_count", summary.eligible_count),
                ("rejected_count", summary.rejected_count),
                ("evidence_only_count", summary.evidence_only_count),
                ("vehicles_count", summary.vehicles_processed),
            ]
            for key, actual in checks:
                if key in expected and actual != expected[key]:
                    msg = f"[Phase 1] Expected {key}={expected[key]}, got {actual}"
                    raise ValueError(msg)

            if enable_phase2 and "phase2" in manifest_data:
                p2 = manifest_data["phase2"]
                p2_as_of_str = p2.get("as_of")
                p2_eval_as_of = (
                    datetime.fromisoformat(p2_as_of_str) if p2_as_of_str else datetime.now(UTC)
                )
                p2_connectors = load_connectors_from_manifest(p2, fixtures_dir)
                p2_capture_times_raw = p2.get("capture_times", {})
                p2_capture_times = {
                    src_sys: datetime.fromisoformat(ts)
                    for src_sys, ts in p2_capture_times_raw.items()
                }

                summary = await pipeline.run(
                    connectors=p2_connectors,
                    capture_times=p2_capture_times or None,
                    as_of=p2_eval_as_of,
                    manifest_id=p2["manifest_id"],
                    run_id_prefix=p2["manifest_id"],
                )

                # Fail-closed: verify expected outcomes for Phase 2
                p2_expected = p2.get("expected_outcomes", {})
                p2_checks = [
                    ("total_observations", summary.total_observations),
                    ("eligible_count", summary.eligible_count),
                    ("rejected_count", summary.rejected_count),
                    ("evidence_only_count", summary.evidence_only_count),
                    ("vehicles_count", summary.vehicles_processed),
                ]
                for key, actual in p2_checks:
                    if key in p2_expected and actual != p2_expected[key]:
                        msg = f"[Phase 2] Expected {key}={p2_expected[key]}, got {actual}"
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
    parser.add_argument(
        "--phase2",
        action="store_true",
        help="Execute phase 2 material updates after baseline seed",
    )

    args = parser.parse_args()

    db_url = args.database_url
    if not db_url:
        print("Error: DATABASE_URL must be set or passed via --database-url", file=sys.stderr)
        sys.exit(1)

    try:
        summary = asyncio.run(run_seed(args.manifest, db_url, enable_phase2=args.phase2))
        print(summary.model_dump_json(indent=2))
    except Exception as exc:
        print(f"Seed command failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
