"""
Base Feature Extractor Interface (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Defines the contract for family-specific feature extraction routines.
Guarantees:
- Output is always a canonical DerivedFeature conforming to qualification_schema.py.
- Missing or invalid measurements return value=None and quality_status=INVALID.
- Temporal provenance is constructed from observation window timestamps.
- Zero-vs-None semantics strictly preserved.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time

from secondshift.interfaces.qualification_schema import (
    DerivedFeature,
    TemporalProvenance,
    TemporalLeakageStatus
)
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.software.features.feature_metadata import FeatureDefinition


class BaseFeatureExtractor(ABC):
    """Abstract base class for all canonical feature extractors."""

    @abstractmethod
    def extract(
        self,
        definition: FeatureDefinition,
        samples: List[Dict[str, Any]],
        session_id: str = "QUAL_SESSION_DEFAULT",
        segment_id: Optional[str] = None,
        decision_timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> DerivedFeature:
        """
        Extracts the requested feature from validated samples.
        Must return a DerivedFeature with complete lineage and temporal provenance.
        """
        pass

    @staticmethod
    def build_provenance(
        samples: List[Dict[str, Any]],
        decision_timestamp: Optional[float] = None,
        calculation_timestamp: Optional[float] = None
    ) -> TemporalProvenance:
        """Constructs temporal provenance from observation window samples."""
        now = calculation_timestamp if calculation_timestamp is not None else time.time()
        if not samples:
            return TemporalProvenance(
                calculation_timestamp=now,
                observation_window_start=now,
                observation_window_end=now,
                decision_timestamp=decision_timestamp,
                leakage_status=TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value
            )

        def _get_ts(s: Dict[str, Any]) -> float:
            for k in ("timestamp", "timestamp_s", "t_rel", "timestamp_monotonic"):
                if k in s and s[k] is not None:
                    return float(s[k])
            return 0.0

        t_start = _get_ts(samples[0])
        t_end = _get_ts(samples[-1])

        tp = TemporalProvenance(
            calculation_timestamp=now,
            observation_window_start=t_start,
            observation_window_end=t_end,
            decision_timestamp=decision_timestamp
        )
        if decision_timestamp is not None:
            tp.check_leakage(decision_timestamp)
        return tp

    @staticmethod
    def build_invalid_feature(
        definition: FeatureDefinition,
        session_id: str,
        segment_id: Optional[str],
        tp: TemporalProvenance,
        reason: str,
        measurement_scope: str = "CELL",
        context: Optional[Dict[str, Any]] = None
    ) -> DerivedFeature:
        """Constructs an explicit invalid DerivedFeature with value=None."""
        return DerivedFeature(
            feature_name=definition.feature_id,
            feature_version=definition.feature_version,
            value=None,
            unit=definition.units,
            source_session=session_id,
            source_segment=segment_id,
            source_measurements=list(definition.source_measurements),
            temporal_provenance=tp,
            physical_meaning=f"UNAVAILABLE: {reason}",
            expected_direction=definition.directionality.value,
            quality_status=DataQualityState.INVALID.value,
            configuration_version=definition.configuration_version,
            measurement_scope=measurement_scope,
            context=dict(context) if context else {}
        )
