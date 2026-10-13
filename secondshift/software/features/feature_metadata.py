"""
Canonical Feature Metadata & Definition Contracts (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Defines strongly-typed metadata schemas for battery qualification features:
- FeatureFamily: Categorical taxonomy (ELECTRICAL, PULSE, RELAXATION, COULOMETRIC, ENERGY, THERMAL, DATA_QUALITY)
- TemporalAvailability: ONLINE_AVAILABLE, OFFLINE_ONLY, CONDITIONAL
- FeatureDirectionality: HIGHER_IS_WORSE, LOWER_IS_WORSE, NON_MONOTONIC, UNKNOWN
- FeatureCandidateStatus: CANDIDATE, VALIDATED_COMPUTATION, ADMITTED, REJECTED, NOT_EVALUATED
- PhysicalBounds: Established physical feasibility envelopes
- FeatureWindow: Strict observation window definitions
- FeatureDefinition: Comprehensive metadata container supporting provenance, dependency auditing, and ablation
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Union

from secondshift.interfaces.qualification_schema import MeasurementScope


class FeatureFamily(str, Enum):
    """Categorical family classification for battery qualification features."""
    ELECTRICAL = "ELECTRICAL"
    PULSE = "PULSE"
    RELAXATION = "RELAXATION"
    COULOMETRIC = "COULOMETRIC"
    ENERGY = "ENERGY"
    THERMAL = "THERMAL"
    DATA_QUALITY = "DATA_QUALITY"
    DEFERRED = "DEFERRED"


class TemporalAvailability(str, Enum):
    """
    Temporal availability classification at decision time.
    Distinguishes when evidence is first physically and causally computable.
    """
    ONLINE_INCREMENTAL = "ONLINE_INCREMENTAL"
    ONLINE_AFTER_SEGMENT_COMPLETION = "ONLINE_AFTER_SEGMENT_COMPLETION"
    ONLINE_AVAILABLE = "ONLINE_AVAILABLE"  # Preserved for backward compatibility
    CONDITIONAL = "CONDITIONAL"
    OFFLINE_ONLY = "OFFLINE_ONLY"
    TEMPORALLY_UNAVAILABLE = "TEMPORALLY_UNAVAILABLE"


class BoundJustification(str, Enum):
    """
    Epistemic classification of physical validity bounds.
    Distinguishes scientific truths from hardware limits and engineering assumptions.
    """
    LITERATURE_DERIVED = "LITERATURE_DERIVED"             # Standard or peer-reviewed electrochemical truth
    CHEMISTRY_DERIVED = "CHEMISTRY_DERIVED"               # Specific to active electrochemical couple (e.g. Li-ion)
    HARDWARE_SENSOR_DERIVED = "HARDWARE_SENSOR_DERIVED"   # Acquisition sensor resolution or ADC range limit
    PROTOTYPE_CONFIG = "PROTOTYPE_CONFIG"                 # Test bench or specimen specific configuration limit
    NUMERICAL_SAFETY = "NUMERICAL_SAFETY"                 # Mathematical guardrail (ratios in [0, 1], finite time)
    PROVISIONAL_ASSUMPTION = "PROVISIONAL_ASSUMPTION"     # Provisional engineering hypothesis; not universal truth


class FeatureDirectionality(str, Enum):
    """
    Degradation monotonicity directionality.
    Must be UNKNOWN unless physically or experimentally established.
    """
    HIGHER_IS_WORSE = "HIGHER_IS_WORSE"
    LOWER_IS_WORSE = "LOWER_IS_WORSE"
    NON_MONOTONIC = "NON_MONOTONIC"
    UNKNOWN = "UNKNOWN"


class FeatureCandidateStatus(str, Enum):
    """Lifecycle admission status of a feature in the research pipeline."""
    CANDIDATE = "CANDIDATE"
    VALIDATED_COMPUTATION = "VALIDATED_COMPUTATION"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    NOT_EVALUATED = "NOT_EVALUATED"


# Helper type
Tuple_Bool_Str = tuple[bool, str]


@dataclass(frozen=True)
class PhysicalBounds:
    """
    Established physical plausibility window for a computed feature value.
    Explicitly scoped to CELL, MODULE, or PACK to prevent cross-hierarchy false alarms.
    """
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    strictly_positive: bool = False
    allow_zero: bool = True
    unit: str = ""
    scope: MeasurementScope = MeasurementScope.CELL
    justification: BoundJustification = BoundJustification.PROVISIONAL_ASSUMPTION
    is_provisional: bool = True
    notes: str = ""
    scales_with_series_cells: bool = False

    def validate(
        self,
        val: Optional[float],
        scope: Optional[Union[MeasurementScope, str]] = None,
        series_cells: int = 1
    ) -> Tuple_Bool_Str:
        """
        Validates a scalar against the physical plausibility envelope.
        Scales extensive properties when evaluated at MODULE or PACK scope with series_cells > 1.
        """
        if val is None:
            return True, "OK"
        if not (val == val):  # NaN check
            return False, "VALUE_IS_NAN"
        if val == float("inf") or val == float("-inf"):
            return False, "VALUE_IS_INFINITE"
        if self.strictly_positive and val <= 0.0:
            return False, f"VALUE_NOT_STRICTLY_POSITIVE: {val} <= 0"
        if not self.allow_zero and val == 0.0:
            return False, "VALUE_CANNOT_BE_ZERO"

        eff_min = self.min_value
        eff_max = self.max_value

        req_scope = scope.value if isinstance(scope, MeasurementScope) else scope
        if req_scope in (MeasurementScope.PACK.value, MeasurementScope.MODULE.value, "PACK", "MODULE"):
            if self.scales_with_series_cells and series_cells > 1:
                if eff_min is not None:
                    eff_min = eff_min * series_cells
                if eff_max is not None:
                    eff_max = eff_max * series_cells

        eff_scope_str = req_scope if req_scope else (self.scope.value if hasattr(self.scope, "value") else str(self.scope))
        if eff_min is not None and val < eff_min:
            return False, f"VALUE_BELOW_MINIMUM: {val} < {eff_min} (scope={eff_scope_str}, series_cells={series_cells})"
        if eff_max is not None and val > eff_max:
            return False, f"VALUE_ABOVE_MAXIMUM: {val} > {eff_max} (scope={eff_scope_str}, series_cells={series_cells})"
        return True, "OK"


@dataclass
class FeatureWindow:
    """
    Explicit specification of the temporal observation window.
    No ambiguous 'recent average' windows permitted.
    """
    window_type: str  # e.g., "COMPLETE_SEGMENT", "TRANSIENT_PULSE", "RELAXATION_WINDOW"
    duration_s: Optional[float] = None
    min_samples: int = 1
    start_offset_s: float = 0.0
    end_offset_s: Optional[float] = None
    segment_type: Optional[str] = None  # e.g., "CHARGE", "DISCHARGE", "PULSE", "REST"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureDefinition:
    """
    Canonical, versioned metadata contract for an individual feature.
    Contains complete lineage, physical interpretation, dependencies, and failure modes.
    """
    feature_id: str
    feature_name: str
    family: FeatureFamily
    description: str
    physical_quantity: str
    units: str
    source_measurements: List[str]
    source_segments: List[str]
    window: FeatureWindow
    aggregation_method: str
    min_samples: int = 1
    min_duration_s: float = 0.0
    validity_conditions: List[str] = field(default_factory=list)
    missing_value_policy: str = "RETURN_NONE"
    temporal_availability: TemporalAvailability = TemporalAvailability.ONLINE_AVAILABLE
    physical_bounds: PhysicalBounds = field(default_factory=PhysicalBounds)
    configuration_version: str = "2.0.0"
    feature_version: str = "1.0.0"
    directionality: FeatureDirectionality = FeatureDirectionality.UNKNOWN
    dependencies: List[str] = field(default_factory=list)
    status: FeatureCandidateStatus = FeatureCandidateStatus.CANDIDATE
    known_failure_modes: List[str] = field(default_factory=list)
    limitations: str = ""
    supported_scopes: List[MeasurementScope] = field(default_factory=lambda: [MeasurementScope.CELL, MeasurementScope.MODULE, MeasurementScope.PACK])
    default_scope: MeasurementScope = MeasurementScope.CELL
    requires_segment_completion: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "family": self.family.value if isinstance(self.family, FeatureFamily) else str(self.family),
            "description": self.description,
            "physical_quantity": self.physical_quantity,
            "units": self.units,
            "source_measurements": list(self.source_measurements),
            "source_segments": list(self.source_segments),
            "window": self.window.to_dict(),
            "aggregation_method": self.aggregation_method,
            "min_samples": self.min_samples,
            "min_duration_s": self.min_duration_s,
            "validity_conditions": list(self.validity_conditions),
            "missing_value_policy": self.missing_value_policy,
            "temporal_availability": self.temporal_availability.value if isinstance(self.temporal_availability, TemporalAvailability) else str(self.temporal_availability),
            "physical_bounds": asdict(self.physical_bounds),
            "configuration_version": self.configuration_version,
            "feature_version": self.feature_version,
            "directionality": self.directionality.value if isinstance(self.directionality, FeatureDirectionality) else str(self.directionality),
            "dependencies": list(self.dependencies),
            "status": self.status.value if isinstance(self.status, FeatureCandidateStatus) else str(self.status),
            "known_failure_modes": list(self.known_failure_modes),
            "limitations": self.limitations,
            "supported_scopes": [s.value if isinstance(s, MeasurementScope) else str(s) for s in self.supported_scopes],
            "default_scope": self.default_scope.value if isinstance(self.default_scope, MeasurementScope) else str(self.default_scope),
            "requires_segment_completion": self.requires_segment_completion
        }
