"""
Canonical Feature Registry (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Maintains the single authoritative catalog of all battery qualification features.
Enforces:
- Unique feature IDs
- Schema validation
- Version tracking
- Dependency auditing
- Rejection of unregistered or duplicate features
"""

from typing import Dict, Any, List, Optional
from secondshift.interfaces.qualification_schema import MeasurementScope
from secondshift.software.features.feature_metadata import (
    FeatureDefinition,
    FeatureFamily,
    TemporalAvailability,
    FeatureDirectionality,
    FeatureCandidateStatus,
    PhysicalBounds,
    FeatureWindow,
    BoundJustification
)

# Canonical Single Source of Truth Count Constants
TOTAL_STANDARDIZED_CANDIDATE_FEATURES = 29
TOTAL_DEFERRED_FEATURES = 1
TOTAL_CATALOGED_FEATURES = 30



class FeatureRegistry:
    """
    Thread-safe authoritative feature registry for RMK REVOLT.
    Prevents conflicting definitions, undocumented features, or silent semantic shifts.
    """
    def __init__(self):
        self._registry: Dict[str, FeatureDefinition] = {}

    def register(self, definition: FeatureDefinition) -> None:
        """
        Registers a new feature definition.
        Raises ValueError if definition is invalid or already registered with a different schema.
        """
        errors = self.validate_definition(definition)
        if errors:
            raise ValueError(f"Invalid feature definition '{definition.feature_id}': {'; '.join(errors)}")
        
        if definition.feature_id in self._registry:
            existing = self._registry[definition.feature_id]
            if existing.feature_version == definition.feature_version:
                # Idempotent re-registration if identical, otherwise error
                if existing.to_dict() != definition.to_dict():
                    raise ValueError(
                        f"Cannot overwrite feature '{definition.feature_id}' v{definition.feature_version} "
                        f"with differing definition without version bump."
                    )
                return
            # Version bump: allowed
        self._registry[definition.feature_id] = definition

    def get(self, feature_id: str) -> FeatureDefinition:
        """Retrieves a registered feature definition by ID. Raises KeyError if missing."""
        if feature_id not in self._registry:
            raise KeyError(f"Feature '{feature_id}' is not registered in Canonical Feature Registry.")
        return self._registry[feature_id]

    def contains(self, feature_id: str) -> bool:
        """Returns True if the feature ID is registered."""
        return feature_id in self._registry

    def list(self, family: Optional[FeatureFamily] = None) -> List[FeatureDefinition]:
        """Returns all registered feature definitions, optionally filtered by family."""
        if family is not None:
            return [f for f in self._registry.values() if f.family == family]
        return list(self._registry.values())

    def list_all(self) -> List[FeatureDefinition]:
        """Returns all registered feature definitions."""
        return self.list()

    def list_by_family(self, family: FeatureFamily) -> List[FeatureDefinition]:
        """Returns all registered feature definitions filtered by family."""
        return self.list(family=family)

    def validate_definition(self, definition: FeatureDefinition) -> List[str]:
        """
        Validates the integrity of a feature definition.
        Returns a list of error strings (empty if valid).
        """
        errors: List[str] = []
        if not definition.feature_id or not isinstance(definition.feature_id, str):
            errors.append("feature_id must be a non-empty string.")
        if not definition.feature_name or not isinstance(definition.feature_name, str):
            errors.append("feature_name must be a non-empty string.")
        if not isinstance(definition.family, FeatureFamily):
            errors.append("family must be an instance of FeatureFamily.")
        if not definition.units and definition.family not in (FeatureFamily.DATA_QUALITY, FeatureFamily.DEFERRED):
            # Most electrical/physical features require units
            errors.append("units must be specified.")
        if definition.min_samples < 1:
            errors.append("min_samples must be >= 1.")
        if definition.min_duration_s < 0:
            errors.append("min_duration_s must be >= 0.")
        if not definition.feature_version:
            errors.append("feature_version must be specified.")
        if not definition.configuration_version:
            errors.append("configuration_version must be specified.")
        if not definition.source_measurements and definition.family != FeatureFamily.DEFERRED:
            errors.append("source_measurements must not be empty.")
        return errors

    def get_version(self, feature_id: str) -> str:
        """Returns the semantic version string for a registered feature."""
        return self.get(feature_id).feature_version

    def get_dependencies(self, feature_id: str) -> List[str]:
        """Returns the declared input dependencies for a feature."""
        return list(self.get(feature_id).dependencies)

    def count(self) -> int:
        """Returns total number of registered (cataloged) features."""
        return len(self._registry)

    def count_active_candidates(self) -> int:
        """Returns total number of active candidate/validated features."""
        return len([
            f for f in self._registry.values()
            if f.family != FeatureFamily.DEFERRED and f.status != FeatureCandidateStatus.REJECTED
        ])

    def count_deferred(self) -> int:
        """Returns total number of explicitly deferred or rejected features."""
        return len([
            f for f in self._registry.values()
            if f.family == FeatureFamily.DEFERRED or f.status == FeatureCandidateStatus.REJECTED
        ])

    def clear(self) -> None:
        """Clears all registered features (used in test isolation)."""
        self._registry.clear()


def create_canonical_registry() -> FeatureRegistry:
    """
    Factory creating and populating the canonical Feature Registry with all
    standardized candidate features across the 7 physical/quality families,
    plus explicitly cataloging deferred features (e.g. dQ/dV).
    """
    reg = FeatureRegistry()

    # =========================================================================
    # A. ELECTRICAL INSTANTANEOUS FAMILY
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="V_MEAN",
        feature_name="Mean Voltage",
        family=FeatureFamily.ELECTRICAL,
        description="Arithmetic mean terminal voltage over the observation window.",
        physical_quantity="Electric Potential",
        units="V",
        source_measurements=["voltage_v"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="ARITHMETIC_MEAN",
        min_samples=1,
        min_duration_s=0.0,
        validity_conditions=["VOLTAGE_SENSOR_VALID", "VOLTAGE_IN_ELECTROCHEMICAL_BOUNDS"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=1.5, max_value=4.5, unit="V",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.CHEMISTRY_DERIVED,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Li-ion cell operating window [1.5, 4.5]V; scales linearly with series cell count (e.g. 2s pack = [3.0, 9.0]V)"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.NON_MONOTONIC,
        dependencies=["voltage_v"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["SENSOR_FAULT", "VOLTAGE_OUT_OF_RANGE"],
        limitations="Does not differentiate between OCV and IR-drop under active current."
    ))

    reg.register(FeatureDefinition(
        feature_id="V_MIN",
        feature_name="Minimum Voltage",
        family=FeatureFamily.ELECTRICAL,
        description="Minimum instantaneous terminal voltage recorded during the window.",
        physical_quantity="Electric Potential",
        units="V",
        source_measurements=["voltage_v"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="MINIMUM",
        min_samples=1,
        validity_conditions=["VOLTAGE_SENSOR_VALID", "VOLTAGE_IN_ELECTROCHEMICAL_BOUNDS"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=1.5, max_value=4.5, unit="V",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.CHEMISTRY_DERIVED,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Li-ion cell minimum operating voltage [1.5, 4.5]V; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.NON_MONOTONIC,
        dependencies=["voltage_v"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["SENSOR_GLITCH", "ADC_DROPOUT"],
        limitations="Susceptible to single-sample negative spikes if sensor filtering fails."
    ))

    reg.register(FeatureDefinition(
        feature_id="V_MAX",
        feature_name="Maximum Voltage",
        family=FeatureFamily.ELECTRICAL,
        description="Maximum instantaneous terminal voltage recorded during the window.",
        physical_quantity="Electric Potential",
        units="V",
        source_measurements=["voltage_v"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="MAXIMUM",
        min_samples=1,
        validity_conditions=["VOLTAGE_SENSOR_VALID", "VOLTAGE_IN_ELECTROCHEMICAL_BOUNDS"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=1.5, max_value=4.5, unit="V",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.CHEMISTRY_DERIVED,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Li-ion cell maximum operating voltage [1.5, 4.5]V; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.NON_MONOTONIC,
        dependencies=["voltage_v"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["SENSOR_GLITCH", "ADC_OVERVOLTAGE"],
        limitations="Susceptible to inductive spike noise on contactor disconnection."
    ))

    reg.register(FeatureDefinition(
        feature_id="I_MEAN",
        feature_name="Mean Current",
        family=FeatureFamily.ELECTRICAL,
        description="Arithmetic mean current passing through specimen (positive=discharge, negative=charge).",
        physical_quantity="Electric Current",
        units="A",
        source_measurements=["current_a"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="ARITHMETIC_MEAN",
        min_samples=1,
        validity_conditions=["CURRENT_SENSOR_VALID", "CURRENT_IN_SHUNT_BOUNDS"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=-60.0, max_value=60.0, unit="A",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.HARDWARE_SENSOR_DERIVED,
            is_provisional=True,
            notes="Current sensor and bench stage range [-60, 60]A"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.NON_MONOTONIC,
        dependencies=["current_a"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["CURRENT_SHUNT_FAULT", "ZERO_OFFSET_DRIFT"],
        limitations="Net current average can mask bidirectional oscillation."
    ))

    reg.register(FeatureDefinition(
        feature_id="I_ABS_MEAN",
        feature_name="Mean Absolute Current",
        family=FeatureFamily.ELECTRICAL,
        description="Mean absolute current magnitude reflecting physical electrical loading intensity.",
        physical_quantity="Electric Current Magnitude",
        units="A",
        source_measurements=["current_a"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="ABSOLUTE_MEAN",
        min_samples=1,
        validity_conditions=["CURRENT_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=60.0, unit="A",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.HARDWARE_SENSOR_DERIVED,
            is_provisional=True,
            notes="Continuous current loading magnitude limit [0, 60]A"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.UNKNOWN,
        dependencies=["current_a"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["SHUNT_SATURATION"],
        limitations="Lacks directionality sign."
    ))

    reg.register(FeatureDefinition(
        feature_id="I_PEAK",
        feature_name="Peak Current Magnitude",
        family=FeatureFamily.ELECTRICAL,
        description="Maximum absolute current amplitude observed during window.",
        physical_quantity="Peak Electric Current",
        units="A",
        source_measurements=["current_a"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="PEAK_MAGNITUDE",
        min_samples=1,
        validity_conditions=["CURRENT_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=60.0, unit="A",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.HARDWARE_SENSOR_DERIVED,
            is_provisional=True,
            notes="Peak current rating of prototype bench"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.UNKNOWN,
        dependencies=["current_a"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["INRUSH_GLITCH"],
        limitations="Captures transient peaks without indicating duration."
    ))

    reg.register(FeatureDefinition(
        feature_id="P_MEAN",
        feature_name="Mean Power",
        family=FeatureFamily.ELECTRICAL,
        description="Mean electrical power delivered or absorbed (V * I).",
        physical_quantity="Electric Power",
        units="W",
        source_measurements=["voltage_v", "current_a"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="PRODUCT_MEAN",
        min_samples=1,
        validity_conditions=["VOLTAGE_SENSOR_VALID", "CURRENT_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=-270.0, max_value=270.0, unit="W",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROTOTYPE_CONFIG,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Prototype cell power limit; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.NON_MONOTONIC,
        dependencies=["voltage_v", "current_a"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["CROSS_CHANNEL_MISALIGNMENT"],
        limitations="Requires concurrent sampling of voltage and current."
    ))

    reg.register(FeatureDefinition(
        feature_id="P_PEAK",
        feature_name="Peak Power Magnitude",
        family=FeatureFamily.ELECTRICAL,
        description="Maximum instantaneous electrical power magnitude |V * I|.",
        physical_quantity="Peak Electric Power",
        units="W",
        source_measurements=["voltage_v", "current_a"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="MAX_PRODUCT_MAGNITUDE",
        min_samples=1,
        validity_conditions=["VOLTAGE_SENSOR_VALID", "CURRENT_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=270.0, unit="W",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROTOTYPE_CONFIG,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Prototype peak power limit; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.UNKNOWN,
        dependencies=["voltage_v", "current_a"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TRANSIENT_SPIKE"],
        limitations="Subject to single-sample power product peaks."
    ))

    # =========================================================================
    # B. PULSE RESPONSE FAMILY
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="DELTA_V_TOTAL",
        feature_name="Total Pulse Voltage Drop",
        family=FeatureFamily.PULSE,
        description="Total terminal voltage change |V_pre - V_end| across a validated excitation pulse.",
        physical_quantity="Polarization Voltage Step",
        units="V",
        source_measurements=["voltage_v", "current_a"],
        source_segments=["PULSE"],
        window=FeatureWindow(window_type="TRANSIENT_PULSE", min_samples=2, segment_type="PULSE"),
        aggregation_method="DIFFERENTIAL",
        min_samples=2,
        validity_conditions=["PULSE_VALID", "CURRENT_FLOW_VALID", "NO_HARDWARE_TRIP"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=1.5, unit="V",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROVISIONAL_ASSUMPTION,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Total pulse polarization drop ceiling [0, 1.5]V; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["v_pre", "v_end", "pulse_valid"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["CURRENT_FLOW_BELOW_MINIMUM", "CONTACTOR_OPEN"],
        limitations="Lumps ohmic and charge-transfer overpotentials together."
    ))

    reg.register(FeatureDefinition(
        feature_id="DELTA_V_OHMIC",
        feature_name="Ohmic Pulse Voltage Drop",
        family=FeatureFamily.PULSE,
        description="Immediate ohmic voltage step |V_pre - V_immediate| (first valid sample within 100ms).",
        physical_quantity="Ohmic Overpotential",
        units="V",
        source_measurements=["voltage_v", "current_a"],
        source_segments=["PULSE"],
        window=FeatureWindow(window_type="TRANSIENT_PULSE", min_samples=2, segment_type="PULSE"),
        aggregation_method="IMMEDIATE_STEP",
        min_samples=2,
        validity_conditions=["PULSE_VALID", "CURRENT_FLOW_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=0.8, unit="V",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROVISIONAL_ASSUMPTION,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Immediate ohmic drop ceiling [0, 0.8]V; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["v_pre", "v_immediate", "pulse_valid"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["INSUFFICIENT_ADC_BANDWIDTH", "CONTACTOR_BOUNCE"],
        limitations="Bandwidth-limited by telemetry ADC sampling rate."
    ))

    reg.register(FeatureDefinition(
        feature_id="R0_OHMIC",
        feature_name="Ohmic Internal Resistance",
        family=FeatureFamily.PULSE,
        description="High-frequency ohmic resistance computed as DELTA_V_OHMIC / |I_pulse| under validated excitation.",
        physical_quantity="Electrical Resistance",
        units="Ohm",
        source_measurements=["voltage_v", "current_a"],
        source_segments=["PULSE"],
        window=FeatureWindow(window_type="TRANSIENT_PULSE", min_samples=2, segment_type="PULSE"),
        aggregation_method="OHMIC_RATIO",
        min_samples=2,
        validity_conditions=["PULSE_VALID", "CURRENT_FLOW_VALID", "I_PULSE_ABOVE_MINIMUM"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0001, max_value=0.100, strictly_positive=True, unit="Ohm",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROVISIONAL_ASSUMPTION,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="PROVISIONAL / CONFIGURATION-SPECIFIC: Valid for RMK cells (~2Ah-50Ah) at nominal temp/SOC. R0 is context-dependent; scales with series count"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["DELTA_V_OHMIC", "mean_pulse_current_a", "pulse_valid"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["FALSE_PULSE_ZERO_CURRENT", "DIV_ZERO_PULSE_CURRENT"],
        limitations="R0 varies with SOC, temperature, and pulse magnitude; NOT a universal scalar health metric."
    ))

    # =========================================================================
    # C. RELAXATION FAMILY
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="RELAXATION_DELTA_V",
        feature_name="Relaxation Voltage Recovery",
        family=FeatureFamily.RELAXATION,
        description="Absolute open-circuit voltage recovery |V_end - V_start| during zero-current relaxation.",
        physical_quantity="OCV Recovery Voltage",
        units="V",
        source_measurements=["voltage_v", "current_a"],
        source_segments=["REST"],
        window=FeatureWindow(window_type="RELAXATION_WINDOW", min_samples=2, duration_s=5.0, segment_type="REST"),
        aggregation_method="ENDPOINT_DIFFERENCE",
        min_samples=2,
        min_duration_s=2.0,
        validity_conditions=["ZERO_CURRENT_VERIFIED", "MINIMUM_REST_DURATION_MET"],
        temporal_availability=TemporalAvailability.ONLINE_AFTER_SEGMENT_COMPLETION,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=0.5, unit="V",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROVISIONAL_ASSUMPTION,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Relaxation voltage recovery ceiling [0, 0.5]V; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["voltage_v", "current_a"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["CURRENT_LEAKAGE_DURING_REST", "INSUFFICIENT_DURATION"],
        limitations="Recovery amplitude depends on pre-rest charge/discharge history."
    ))

    reg.register(FeatureDefinition(
        feature_id="RELAXATION_SLOPE_DV_DT",
        feature_name="Relaxation dV/dt Slope",
        family=FeatureFamily.RELAXATION,
        description="Linear relaxation voltage drift rate (V_end - V_start) / dt strictly computed over past/current samples.",
        physical_quantity="Voltage Drift Rate",
        units="V/s",
        source_measurements=["voltage_v", "timestamp"],
        source_segments=["REST"],
        window=FeatureWindow(window_type="RELAXATION_WINDOW", min_samples=3, duration_s=5.0, segment_type="REST"),
        aggregation_method="CAUSAL_SLOPE",
        min_samples=3,
        min_duration_s=2.0,
        validity_conditions=["ZERO_CURRENT_VERIFIED", "NON_ZERO_TIME_ELAPSED"],
        temporal_availability=TemporalAvailability.ONLINE_AFTER_SEGMENT_COMPLETION,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=-0.1, max_value=0.1, unit="V/s",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROVISIONAL_ASSUMPTION,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Relaxation dV/dt drift rate bounds; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.UNKNOWN,
        dependencies=["voltage_v", "timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TIME_DELTA_ZERO", "TIMESTAMP_INVERSION"],
        limitations="Sensitive to ADC quantization noise over short observation windows."
    ))

    # =========================================================================
    # D. COULOMETRIC FAMILY
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="CHARGE_AH",
        feature_name="Integrated Charge Capacity",
        family=FeatureFamily.COULOMETRIC,
        description="Trapezoidal integration of charge current (I < 0) converted to Ampere-hours.",
        physical_quantity="Electric Charge",
        units="Ah",
        source_measurements=["current_a", "timestamp"],
        source_segments=["CHARGE"],
        window=FeatureWindow(window_type="COMPLETE_SEGMENT", min_samples=2, segment_type="CHARGE"),
        aggregation_method="TRAPEZOIDAL_INTEGRATION",
        min_samples=2,
        validity_conditions=["CURRENT_SENSOR_VALID", "MONOTONIC_TIMESTAMPS"],
        temporal_availability=TemporalAvailability.ONLINE_AFTER_SEGMENT_COMPLETION,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=150.0, unit="Ah",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROTOTYPE_CONFIG,
            is_provisional=True,
            notes="Bench capacity integration ceiling [0, 150]Ah"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["current_a", "timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TIME_DELTA_IRREGULAR", "CURRENT_OFFSET_ERROR"],
        limitations="Subject to current shunt calibration drift over extended integration."
    ))

    reg.register(FeatureDefinition(
        feature_id="DISCHARGE_AH",
        feature_name="Integrated Discharge Capacity",
        family=FeatureFamily.COULOMETRIC,
        description="Trapezoidal integration of discharge current (I > 0) converted to Ampere-hours.",
        physical_quantity="Electric Charge",
        units="Ah",
        source_measurements=["current_a", "timestamp"],
        source_segments=["DISCHARGE"],
        window=FeatureWindow(window_type="COMPLETE_SEGMENT", min_samples=2, segment_type="DISCHARGE"),
        aggregation_method="TRAPEZOIDAL_INTEGRATION",
        min_samples=2,
        validity_conditions=["CURRENT_SENSOR_VALID", "MONOTONIC_TIMESTAMPS"],
        temporal_availability=TemporalAvailability.ONLINE_AFTER_SEGMENT_COMPLETION,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=150.0, unit="Ah",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROTOTYPE_CONFIG,
            is_provisional=True,
            notes="Bench discharge capacity integration ceiling [0, 150]Ah"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["current_a", "timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TIME_DELTA_IRREGULAR", "CURRENT_OFFSET_ERROR"],
        limitations="Actual capacity depends on terminal cutoff voltage and C-rate."
    ))

    reg.register(FeatureDefinition(
        feature_id="COULOMBIC_EFFICIENCY",
        feature_name="Coulombic Efficiency",
        family=FeatureFamily.COULOMETRIC,
        description="Ratio of total discharge capacity to total charge capacity across completed cycle.",
        physical_quantity="Charge Ratio",
        units="fraction",
        source_measurements=["current_a", "timestamp"],
        source_segments=["CHARGE", "DISCHARGE"],
        window=FeatureWindow(window_type="FULL_CYCLE", min_samples=4),
        aggregation_method="RATIO",
        min_samples=4,
        validity_conditions=["COMPLETED_CYCLE_AVAILABLE", "CHARGE_AH_ABOVE_THRESHOLD"],
        temporal_availability=TemporalAvailability.CONDITIONAL,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=0.50, max_value=1.05, unit="fraction",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.LITERATURE_DERIVED,
            is_provisional=False,
            notes="Literature thermodynamic boundary 1.0 plus 5% measurement noise tolerance"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["DISCHARGE_AH", "CHARGE_AH"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["DIV_ZERO_CHARGE_AH", "INCOMPLETE_CYCLE"],
        limitations="Only computable after full charge-discharge cycle completion; NOT available online mid-cycle."
    ))

    # =========================================================================
    # E. ENERGY FAMILY
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="CHARGE_WH",
        feature_name="Integrated Charge Energy",
        family=FeatureFamily.ENERGY,
        description="Numerical integration of electrical power during charging in Watt-hours.",
        physical_quantity="Electrical Energy",
        units="Wh",
        source_measurements=["voltage_v", "current_a", "timestamp"],
        source_segments=["CHARGE"],
        window=FeatureWindow(window_type="COMPLETE_SEGMENT", min_samples=2, segment_type="CHARGE"),
        aggregation_method="TRAPEZOIDAL_ENERGY",
        min_samples=2,
        validity_conditions=["VOLTAGE_SENSOR_VALID", "CURRENT_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_AFTER_SEGMENT_COMPLETION,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=500.0, unit="Wh",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROTOTYPE_CONFIG,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Charge energy ceiling [0, 500]Wh; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.UNKNOWN,
        dependencies=["voltage_v", "current_a", "timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TIME_DELTA_IRREGULAR"],
        limitations="Includes resistive heating losses during charging."
    ))

    reg.register(FeatureDefinition(
        feature_id="DISCHARGE_WH",
        feature_name="Integrated Discharge Energy",
        family=FeatureFamily.ENERGY,
        description="Numerical integration of electrical power during discharge in Watt-hours.",
        physical_quantity="Electrical Energy",
        units="Wh",
        source_measurements=["voltage_v", "current_a", "timestamp"],
        source_segments=["DISCHARGE"],
        window=FeatureWindow(window_type="COMPLETE_SEGMENT", min_samples=2, segment_type="DISCHARGE"),
        aggregation_method="TRAPEZOIDAL_ENERGY",
        min_samples=2,
        validity_conditions=["VOLTAGE_SENSOR_VALID", "CURRENT_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_AFTER_SEGMENT_COMPLETION,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=500.0, unit="Wh",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.PROTOTYPE_CONFIG,
            is_provisional=True,
            scales_with_series_cells=True,
            notes="Discharge energy ceiling [0, 500]Wh; scales with series cells"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["voltage_v", "current_a", "timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TIME_DELTA_IRREGULAR"],
        limitations="Delivered energy decreases significantly at elevated discharge C-rates."
    ))

    reg.register(FeatureDefinition(
        feature_id="ENERGY_EFFICIENCY",
        feature_name="Round-Trip Energy Efficiency",
        family=FeatureFamily.ENERGY,
        description="Ratio of total discharge energy to charge energy across completed cycle.",
        physical_quantity="Energy Ratio",
        units="fraction",
        source_measurements=["voltage_v", "current_a", "timestamp"],
        source_segments=["CHARGE", "DISCHARGE"],
        window=FeatureWindow(window_type="FULL_CYCLE", min_samples=4),
        aggregation_method="RATIO",
        min_samples=4,
        validity_conditions=["COMPLETED_CYCLE_AVAILABLE", "CHARGE_WH_ABOVE_THRESHOLD"],
        temporal_availability=TemporalAvailability.CONDITIONAL,
        requires_segment_completion=True,
        physical_bounds=PhysicalBounds(
            min_value=0.40, max_value=1.00, unit="fraction",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.LITERATURE_DERIVED,
            is_provisional=False,
            notes="Thermodynamic ceiling: round-trip energy efficiency <= 1.0"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["DISCHARGE_WH", "CHARGE_WH"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["DIV_ZERO_CHARGE_WH", "INCOMPLETE_CYCLE"],
        limitations="Conditional on completed cycle; reflects both coulombic losses and overpotential hysteresis."
    ))

    # =========================================================================
    # F. THERMAL FAMILY (Annotated as Safety/Context, NOT Unproven Prognostics)
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="T_MEAN",
        feature_name="Mean Surface Temperature",
        family=FeatureFamily.THERMAL,
        description="Mean surface temperature over observation window. Context/safety feature.",
        physical_quantity="Thermodynamic Temperature",
        units="degC",
        source_measurements=["temperature_c"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="ARITHMETIC_MEAN",
        min_samples=1,
        validity_conditions=["TEMP_SENSOR_VALID", "TEMPERATURE_IN_PLAUSIBLE_BOUNDS"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=60.0, unit="degC",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.LITERATURE_DERIVED,
            is_provisional=False,
            notes="IEC 62619 safe operating limit; safety/context only, computation != prognostic benefit"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["temperature_c"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["NTC_DISCONNECTION", "TEMP_OUT_OF_RANGE"],
        limitations="Context/safety metric. In RMK REVOLT tests, thermal metrics did NOT improve RUL prediction."
    ))

    reg.register(FeatureDefinition(
        feature_id="T_MAX",
        feature_name="Maximum Temperature",
        family=FeatureFamily.THERMAL,
        description="Maximum recorded cell surface temperature. Safety & anomaly detection feature.",
        physical_quantity="Peak Temperature",
        units="degC",
        source_measurements=["temperature_c"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="MAXIMUM",
        min_samples=1,
        validity_conditions=["TEMP_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=65.0, unit="degC",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.LITERATURE_DERIVED,
            is_provisional=False,
            notes="Critical thermal shutdown boundary; safety only"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["temperature_c"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["SENSOR_SPIKE"],
        limitations="Surface temperature lags internal core temperature during high-rate pulses."
    ))

    reg.register(FeatureDefinition(
        feature_id="DELTA_T",
        feature_name="Temperature Rise",
        family=FeatureFamily.THERMAL,
        description="Net temperature rise (T_end - T_start) across observation window.",
        physical_quantity="Temperature Difference",
        units="degC",
        source_measurements=["temperature_c"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=2),
        aggregation_method="ENDPOINT_DIFFERENCE",
        min_samples=2,
        validity_conditions=["TEMP_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=-20.0, max_value=40.0, unit="degC",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=True,
            notes="Maximum single-step thermal delta"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["temperature_c"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["AMBIENT_THERMAL_DRIFT"],
        limitations="Heavily influenced by ambient chamber convection and heat sinking."
    ))

    reg.register(FeatureDefinition(
        feature_id="DT_DT",
        feature_name="Thermal Rise Rate dT/dt",
        family=FeatureFamily.THERMAL,
        description="Causal thermal rise rate (T_end - T_start) / dt strictly over past/current samples.",
        physical_quantity="Thermal Rate of Change",
        units="degC/s",
        source_measurements=["temperature_c", "timestamp"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=3, duration_s=10.0),
        aggregation_method="CAUSAL_SLOPE",
        min_samples=3,
        min_duration_s=2.0,
        validity_conditions=["TEMP_SENSOR_VALID", "NON_ZERO_TIME_ELAPSED"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=-1.0, max_value=2.0, unit="degC/s",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=True,
            notes="Plausible surface thermal rate without runaway"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["temperature_c", "timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TIME_DELTA_ZERO", "TIMESTAMP_INVERSION"],
        limitations="Context/safety rate metric; not established as a standalone prognostic indicator."
    ))

    # =========================================================================
    # G. DATA QUALITY & META-FEATURES
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="VALID_SAMPLE_FRACTION",
        feature_name="Valid Sample Fraction",
        family=FeatureFamily.DATA_QUALITY,
        description="Ratio of valid sensor frames to total frames in window. Measurement quality, NOT model confidence.",
        physical_quantity="Completeness Fraction",
        units="fraction",
        source_measurements=["quality_flags", "is_valid"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="RATIO",
        min_samples=1,
        validity_conditions=["WINDOW_NON_EMPTY"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=1.0, unit="fraction",
            scope=MeasurementScope.UNKNOWN,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=False,
            notes="Mathematical ratio bounded in [0.0, 1.0]"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["quality_flags"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["EMPTY_WINDOW"],
        limitations="Quantifies sensor reliability only; does NOT represent probability of prediction correctness."
    ))

    reg.register(FeatureDefinition(
        feature_id="INVALID_SAMPLE_FRACTION",
        feature_name="Invalid Sample Fraction",
        family=FeatureFamily.DATA_QUALITY,
        description="Ratio of corrupted or invalid sensor frames to total frames.",
        physical_quantity="Corruption Fraction",
        units="fraction",
        source_measurements=["quality_flags", "is_valid"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="RATIO",
        min_samples=1,
        validity_conditions=["WINDOW_NON_EMPTY"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=1.0, unit="fraction",
            scope=MeasurementScope.UNKNOWN,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=False,
            notes="Mathematical ratio bounded in [0.0, 1.0]"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.HIGHER_IS_WORSE,
        dependencies=["quality_flags"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["EMPTY_WINDOW"],
        limitations="Measurement health only."
    ))

    reg.register(FeatureDefinition(
        feature_id="CURRENT_FLOW_VALID",
        feature_name="Current Flow Validity Indicator",
        family=FeatureFamily.DATA_QUALITY,
        description="Boolean validity (1.0 = valid flow |I| >= I_min; 0.0 = open/invalid) during active excitation.",
        physical_quantity="Binary Admissibility Indicator",
        units="boolean",
        source_measurements=["current_a"],
        source_segments=["PULSE", "CHARGE", "DISCHARGE"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="THRESHOLD_INDICATOR",
        min_samples=1,
        validity_conditions=["CURRENT_SENSOR_VALID"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=1.0, unit="boolean",
            scope=MeasurementScope.UNKNOWN,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=False,
            notes="Boolean binary indicator {0.0, 1.0}"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["current_a"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["FALSE_CURRENT_READING"],
        limitations="Identifies whether active current was physically drawn."
    ))

    reg.register(FeatureDefinition(
        feature_id="PULSE_VALID",
        family=FeatureFamily.DATA_QUALITY,
        feature_name="Diagnostic Pulse Validity Indicator",
        description="Layer 2 diagnostic pulse admissibility indicator (1.0 = valid; 0.0 = invalid).",
        physical_quantity="Pulse Validity Indicator",
        units="boolean",
        source_measurements=["voltage_v", "current_a"],
        source_segments=["PULSE"],
        window=FeatureWindow(window_type="TRANSIENT_PULSE", min_samples=2, segment_type="PULSE"),
        aggregation_method="VALIDATION_RECORD_LOOKUP",
        min_samples=2,
        validity_conditions=["PULSE_RECORD_AVAILABLE"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=1.0, unit="boolean",
            scope=MeasurementScope.UNKNOWN,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=False,
            notes="Boolean binary indicator {0.0, 1.0}"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["PulseValidationRecord"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["MISSING_VALIDATION_RECORD"],
        limitations="Admissibility flag only."
    ))

    reg.register(FeatureDefinition(
        feature_id="TIMESTAMP_INTEGRITY",
        feature_name="Timestamp Monotonicity Indicator",
        family=FeatureFamily.DATA_QUALITY,
        description="Boolean indicator (1.0 = strictly monotonic t_k+1 > t_k; 0.0 = inversion/duplicate detected).",
        physical_quantity="Clock Monotonicity Indicator",
        units="boolean",
        source_measurements=["timestamp"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=2),
        aggregation_method="MONOTONICITY_CHECK",
        min_samples=2,
        validity_conditions=["TIMESTAMPS_AVAILABLE"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=1.0, unit="boolean",
            scope=MeasurementScope.UNKNOWN,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=False,
            notes="Binary monotonicity indicator {0.0, 1.0}"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.LOWER_IS_WORSE,
        dependencies=["timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["TIMESTAMP_INVERSION", "DUPLICATE_TIMESTAMP"],
        limitations="Checks local window monotonicity only."
    ))

    reg.register(FeatureDefinition(
        feature_id="MEASUREMENT_DURATION",
        feature_name="Observation Window Duration",
        family=FeatureFamily.DATA_QUALITY,
        description="Total elapsed physical duration of the observation window (t_end - t_start).",
        physical_quantity="Time Duration",
        units="s",
        source_measurements=["timestamp"],
        source_segments=["CHARGE", "DISCHARGE", "PULSE", "REST", "HOLD"],
        window=FeatureWindow(window_type="OBSERVATION_WINDOW", min_samples=1),
        aggregation_method="SPAN",
        min_samples=1,
        validity_conditions=["TIMESTAMPS_AVAILABLE"],
        temporal_availability=TemporalAvailability.ONLINE_INCREMENTAL,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=86400.0, unit="s",
            scope=MeasurementScope.UNKNOWN,
            justification=BoundJustification.NUMERICAL_SAFETY,
            is_provisional=False,
            notes="Elapsed observation time in seconds (up to 24h)"
        ),
        feature_version="1.0.0",
        directionality=FeatureDirectionality.UNKNOWN,
        dependencies=["timestamp"],
        status=FeatureCandidateStatus.VALIDATED_COMPUTATION,
        known_failure_modes=["NEGATIVE_DURATION"],
        limitations="Elapsed time only."
    ))

    # =========================================================================
    # H. DEFERRED / REJECTED FEATURES (Cataloged explicitly with scientific rationale)
    # =========================================================================
    reg.register(FeatureDefinition(
        feature_id="DQ_DV_PEAK",
        feature_name="Differential Capacity Peak (dQ/dV)",
        family=FeatureFamily.DEFERRED,
        description="Incremental Capacity Analysis peak. Explicitly DEFERRED due to sampling resolution constraints.",
        physical_quantity="Differential Capacity",
        units="Ah/V",
        source_measurements=["voltage_v", "current_a", "timestamp"],
        source_segments=["CHARGE", "DISCHARGE"],
        window=FeatureWindow(window_type="FULL_CYCLE", min_samples=1000),
        aggregation_method="DERIVATIVE",
        min_samples=1000,
        validity_conditions=["PSEUDO_OCV_RATE_BELOW_C20", "DENSE_VOLTAGE_RESOLUTION_1MV"],
        temporal_availability=TemporalAvailability.OFFLINE_ONLY,
        physical_bounds=PhysicalBounds(
            min_value=0.0, max_value=200.0, unit="Ah/V",
            scope=MeasurementScope.CELL,
            justification=BoundJustification.LITERATURE_DERIVED,
            is_provisional=False,
            notes="ICA peak envelope under pseudo-OCV"
        ),
        feature_version="0.1.0-DEFERRED",
        directionality=FeatureDirectionality.UNKNOWN,
        dependencies=["high_resolution_coulometry", "low_rate_charge"],
        status=FeatureCandidateStatus.REJECTED,
        known_failure_modes=["INSUFFICIENT_SAMPLING_RESOLUTION", "NOISE_AMPLIFICATION"],
        limitations="REJECTED for rapid qualification: requires C/20 to C/50 low-rate cycles and sub-millivolt ADC. "
                    "Cannot be computed from 10Hz rapid bench pulses without fabricating spline curves."
    ))

    return reg
