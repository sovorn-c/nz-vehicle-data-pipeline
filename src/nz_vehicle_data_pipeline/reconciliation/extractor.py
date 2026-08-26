"""Candidate value extraction from normalized staged models (ADR 0001, ADR 0003)."""

from typing import Any

from nz_vehicle_data_pipeline.normalization.engine import NormalizedObservation
from nz_vehicle_data_pipeline.normalization.staging_models import (
    DealerListingStaged,
    NHTSAVPICStaged,
    NZTAFleetStaged,
    PPSRInterestStaged,
    StolenIndicatorStaged,
    WriteoffClassificationStaged,
)
from nz_vehicle_data_pipeline.observation.models import SourceObservation
from nz_vehicle_data_pipeline.reconciliation.provenance import (
    CandidateValue,
    ProvenanceLink,
)


class CandidateExtractor:
    """Extracts discrete candidate values with provenance from normalized observations."""

    def extract(
        self, observation: SourceObservation, normalized: NormalizedObservation
    ) -> list[CandidateValue]:
        """Extract all valid candidate values with provenance links."""
        link = ProvenanceLink(
            observation_id=observation.observation_id,
            source_system=observation.source_system,
            source_record_id=observation.source_record_id,
            retrieved_at=observation.retrieved_at,
            synthetic=observation.synthetic,
        )

        staged = normalized.staged_data
        candidates: list[CandidateValue] = []

        def add_candidate(field_name: str, value: Any) -> None:
            if value is not None:
                candidates.append(
                    CandidateValue(
                        field_name=field_name,
                        value=value,
                        provenance=link,
                    )
                )

        match staged:
            case NHTSAVPICStaged():
                add_candidate("make", staged.make)
                add_candidate("model", staged.model)
                add_candidate("year", staged.model_year)
                add_candidate("body_type", staged.body_class)
                add_candidate("vehicle_type", staged.vehicle_type)
                add_candidate("engine_cylinders", staged.engine_cylinders)
                add_candidate("displacement_l", staged.displacement_l)
                add_candidate("manufacturer", staged.manufacturer)

            case DealerListingStaged():
                add_candidate("asking_price_cents", staged.price_cents)
                add_candidate("odometer_km", staged.odometer_km)
                add_candidate("condition", staged.condition)
                add_candidate("dealer_id", staged.dealer_id)

            case PPSRInterestStaged():
                ppsr_dict = {
                    "ppsr_id": staged.ppsr_id,
                    "secured_party": staged.secured_party,
                    "collateral_type": staged.collateral_type,
                    "registration_date": staged.registration_date.isoformat(),
                }
                add_candidate("ppsr_interests", ppsr_dict)

            case StolenIndicatorStaged():
                status = "LISTED" if staged.stolen_flag else "NOT_LISTED"
                add_candidate("stolen_status", status)
                add_candidate("stolen_report_date", staged.report_date.isoformat())
                add_candidate("police_district", staged.police_district)

            case WriteoffClassificationStaged():
                add_candidate("writeoff_status", staged.category.value)
                if staged.damage_date:
                    add_candidate("writeoff_damage_date", staged.damage_date.isoformat())

            case NZTAFleetStaged():
                # Handled as EVIDENCE ONLY per ADR 0002; does not create vehicle candidates
                pass

        return candidates
