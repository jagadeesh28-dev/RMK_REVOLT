"""
Test Suite: Canonical Feature Engine (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Validates:
1. Feature registry: registration, retrieval, duplicate handling, versioning, dependency lookup
2. Feature metadata: schema validation, physical bounds, directionality
3. Feature calculation across families: electrical, pulse, relaxation, coulometric, energy, thermal, data quality
4. Provenance completeness: session, segment, source measurements, timestamps, versions
5. Temporal admissibility: t_end <= t_decision vs future leakage rejection
6. Measurement validity: sensor fault, NaN, Inf rejection
7. Missingness semantics: missing values remain None, never coerced
8. Zero vs None semantics: physically measured 0.0 preserved; invalid is None
9. Numerical stability: division-by-zero, dt=0, near-zero denominators
10. Deterministic output: bitwise identical outputs for identical inputs
11. Online vs offline / conditional classification
12. Explicit failure modes and dQ/dV deferral
13. Integration with QualificationSession and get_admissible_features
"""

import pytest
import time
import math

from secondshift.interfaces.qualification_schema import (
    DerivedFeature,
    TemporalProvenance,
    TemporalLeakageStatus,
    QualificationSession,
    TestSegment,
    SegmentType,
    BatteryRecord,
    MeasurementScope
)
from secondshift.interfaces.data_quality_schema import (
    DataQualityState,
    PulseValidationRecord
)
from secondshift.interfaces.telemetry_schema import TelemetryFrame

from secondshift.software.features.feature_metadata import (
    FeatureFamily,
    TemporalAvailability,
    FeatureDirectionality,
    FeatureCandidateStatus,
    PhysicalBounds,
    FeatureWindow,
    FeatureDefinition,
    BoundJustification
)
from secondshift.software.features.feature_registry import (
    FeatureRegistry,
    create_canonical_registry,
    TOTAL_STANDARDIZED_CANDIDATE_FEATURES,
    TOTAL_DEFERRED_FEATURES,
    TOTAL_CATALOGED_FEATURES
)
from secondshift.software.features.admission import (
    FeatureAdmissionEngine,
    AdmissionAuditResult
)
from secondshift.software.features.feature_engine import (
    CanonicalFeatureEngine
)


# =============================================================================
# 1. REGISTRY & METADATA TESTS
# =============================================================================

def test_feature_registry_initialization_and_lookup():
    reg = create_canonical_registry()
    assert reg.count() >= 20
    assert reg.contains("V_MEAN")
    assert reg.contains("R0_OHMIC")
    assert reg.contains("COULOMBIC_EFFICIENCY")
    assert reg.contains("DQ_DV_PEAK")

    defn = reg.get("V_MEAN")
    assert defn.feature_name == "Mean Voltage"
    assert defn.family == FeatureFamily.ELECTRICAL
    assert defn.units == "V"
    assert defn.feature_version == "1.0.0"
    assert defn.temporal_availability in (TemporalAvailability.ONLINE_INCREMENTAL, TemporalAvailability.ONLINE_AVAILABLE)


def test_feature_registry_duplicate_and_version_handling():
    reg = FeatureRegistry()
    defn = FeatureDefinition(
        feature_id="CUSTOM_FEAT",
        feature_name="Custom Feature",
        family=FeatureFamily.ELECTRICAL,
        description="Test feature",
        physical_quantity="Voltage",
        units="V",
        source_measurements=["voltage_v"],
        source_segments=["PULSE"],
        window=FeatureWindow(window_type="WINDOW"),
        aggregation_method="MEAN",
        feature_version="1.0.0"
    )
    reg.register(defn)
    assert reg.count() == 1

    # Idempotent re-registration of identical definition succeeds
    reg.register(defn)
    assert reg.count() == 1

    # Overwrite with different definition without version bump must raise ValueError
    defn_diff = FeatureDefinition(
        feature_id="CUSTOM_FEAT",
        feature_name="Altered Feature",
        family=FeatureFamily.ELECTRICAL,
        description="Altered description",
        physical_quantity="Voltage",
        units="V",
        source_measurements=["voltage_v"],
        source_segments=["PULSE"],
        window=FeatureWindow(window_type="WINDOW"),
        aggregation_method="MEAN",
        feature_version="1.0.0"
    )
    with pytest.raises(ValueError, match="Cannot overwrite feature"):
        reg.register(defn_diff)


def test_feature_dependencies_lookup():
    reg = create_canonical_registry()
    deps_r0 = reg.get_dependencies("R0_OHMIC")
    assert "DELTA_V_OHMIC" in deps_r0
    assert "pulse_valid" in deps_r0


# =============================================================================
# 2. ELECTRICAL FAMILY TESTS
# =============================================================================

def test_electrical_features_mean_min_max_power():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 100.0, "voltage_v": 3.30, "current_a": 10.0},
        {"timestamp": 101.0, "voltage_v": 3.25, "current_a": 10.0},
        {"timestamp": 102.0, "voltage_v": 3.20, "current_a": 10.0}
    ]

    v_mean = engine.extract_feature("V_MEAN", samples, decision_timestamp=105.0)
    assert v_mean.value == pytest.approx(3.25, abs=1e-3)
    assert v_mean.quality_status == DataQualityState.VALID.value
    assert v_mean.is_admissible is True
    assert v_mean.unit == "V"

    v_min = engine.extract_feature("V_MIN", samples, decision_timestamp=105.0)
    assert v_min.value == pytest.approx(3.20, abs=1e-3)

    v_max = engine.extract_feature("V_MAX", samples, decision_timestamp=105.0)
    assert v_max.value == pytest.approx(3.30, abs=1e-3)

    p_mean = engine.extract_feature("P_MEAN", samples, decision_timestamp=105.0)
    # (33.0 + 32.5 + 32.0) / 3 = 32.5 W
    assert p_mean.value == pytest.approx(32.5, abs=1e-2)
    assert p_mean.unit == "W"


# =============================================================================
# 3. PULSE RESPONSE & UNKNOWN != ZERO TESTS
# =============================================================================

def test_pulse_features_valid_excitation():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 10.0, "voltage_v": 3.300, "current_a": 10.0},
        {"timestamp": 10.05, "voltage_v": 3.250, "current_a": 10.0},
        {"timestamp": 10.10, "voltage_v": 3.200, "current_a": 10.0}
    ]
    ctx = {
        "v_pre": 3.320,
        "i_min_pulse_a": 1.0,
        "pulse_valid": True
    }

    r0_feat = engine.extract_feature("R0_OHMIC", samples, decision_timestamp=15.0, context=ctx)
    assert r0_feat.value is not None
    # delta_v_ohmic = |3.320 - 3.250| = 0.070V. R0 = 0.070 / 10 = 0.007 Ohm (7 mOhm)
    assert r0_feat.value == pytest.approx(0.007, abs=1e-4)
    assert r0_feat.unit == "Ohm"
    assert r0_feat.quality_status == DataQualityState.VALID.value
    assert r0_feat.is_admissible is True


def test_pulse_features_invalid_zero_current_returns_none():
    engine = CanonicalFeatureEngine()
    # Contactors open or zero current (< 1.0A)
    samples = [
        {"timestamp": 10.0, "voltage_v": 3.320, "current_a": 0.0},
        {"timestamp": 10.05, "voltage_v": 3.320, "current_a": 0.0}
    ]
    ctx = {
        "v_pre": 3.320,
        "i_min_pulse_a": 1.0,
        "pulse_valid": False
    }

    r0_feat = engine.extract_feature("R0_OHMIC", samples, decision_timestamp=15.0, context=ctx)
    # INVARIANT: Invalid pulse must return None, NEVER 0.0
    assert r0_feat.value is None
    assert r0_feat.quality_status == DataQualityState.INVALID.value
    assert r0_feat.is_admissible is False

    dv_feat = engine.extract_feature("DELTA_V_TOTAL", samples, decision_timestamp=15.0, context=ctx)
    assert dv_feat.value is None
    assert dv_feat.quality_status == DataQualityState.INVALID.value


# =============================================================================
# 4. RELAXATION & CAUSAL DERIVATIVE TESTS
# =============================================================================

def test_relaxation_voltage_recovery_and_causal_slope():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 0.0, "voltage_v": 3.200, "current_a": 0.0},
        {"timestamp": 2.5, "voltage_v": 3.210, "current_a": 0.0},
        {"timestamp": 5.0, "voltage_v": 3.220, "current_a": 0.0}
    ]

    rec_v = engine.extract_feature("RELAXATION_DELTA_V", samples, decision_timestamp=10.0)
    assert rec_v.value == pytest.approx(0.020, abs=1e-4)
    assert rec_v.is_admissible is True

    slope = engine.extract_feature("RELAXATION_SLOPE_DV_DT", samples, decision_timestamp=10.0)
    # (3.220 - 3.200) / 5.0 = 0.004 V/s
    assert slope.value == pytest.approx(0.004, abs=1e-4)
    assert slope.unit == "V/s"
    assert slope.is_admissible is True


def test_relaxation_fails_when_current_active():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 0.0, "voltage_v": 3.200, "current_a": 5.0},
        {"timestamp": 5.0, "voltage_v": 3.250, "current_a": 5.0}
    ]
    rec_v = engine.extract_feature("RELAXATION_DELTA_V", samples, decision_timestamp=10.0)
    assert rec_v.value is None
    assert rec_v.quality_status == DataQualityState.INVALID.value


# =============================================================================
# 5. COULOMETRIC & ENERGY EFFICIENCY TESTS
# =============================================================================

def test_coulometric_integration_and_efficiency():
    engine = CanonicalFeatureEngine()
    # 3600 seconds of 10A discharge = 10 Ah
    samples_dis = [
        {"timestamp": 0.0, "voltage_v": 3.2, "current_a": 10.0},
        {"timestamp": 3600.0, "voltage_v": 3.0, "current_a": 10.0}
    ]
    dis_ah = engine.extract_feature("DISCHARGE_AH", samples_dis, decision_timestamp=4000.0)
    assert dis_ah.value == pytest.approx(10.0, abs=1e-2)

    # Efficiency via context
    eff_feat = engine.extract_feature(
        "COULOMBIC_EFFICIENCY", samples_dis, decision_timestamp=4000.0,
        context={"charge_ah": 10.2, "discharge_ah": 10.0}
    )
    assert eff_feat.value == pytest.approx(10.0 / 10.2, abs=1e-3)
    assert eff_feat.is_admissible is True


def test_efficiency_zero_denominator_returns_none():
    engine = CanonicalFeatureEngine()
    eff_feat = engine.extract_feature(
        "COULOMBIC_EFFICIENCY", [], decision_timestamp=10.0,
        context={"charge_ah": 0.0, "discharge_ah": 5.0}
    )
    assert eff_feat.value is None
    assert eff_feat.quality_status == DataQualityState.INVALID.value


# =============================================================================
# 6. THERMAL CONTEXT & SAFETY ANNOTATION TESTS
# =============================================================================

def test_thermal_features_context_and_safety():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 0.0, "temperature_c": 25.0},
        {"timestamp": 10.0, "temperature_c": 27.0},
        {"timestamp": 20.0, "temperature_c": 29.0}
    ]
    t_mean = engine.extract_feature("T_MEAN", samples, decision_timestamp=30.0)
    assert t_mean.value == pytest.approx(27.0, abs=1e-2)

    t_max = engine.extract_feature("T_MAX", samples, decision_timestamp=30.0)
    assert t_max.value == pytest.approx(29.0, abs=1e-2)

    dt_dt = engine.extract_feature("DT_DT", samples, decision_timestamp=30.0)
    # (29 - 25) / 20 = 0.2 degC/s
    assert dt_dt.value == pytest.approx(0.2, abs=1e-3)


# =============================================================================
# 7. DATA QUALITY & META-FEATURES
# =============================================================================

def test_data_quality_fraction_and_monotonicity():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": 3.3, "is_valid": True},
        {"timestamp": 2.0, "voltage_v": 3.3, "is_valid": True},
        {"timestamp": 3.0, "voltage_v": 3.3, "is_valid": False},
        {"timestamp": 4.0, "voltage_v": 3.3, "is_valid": True}
    ]

    val_frac = engine.extract_feature("VALID_SAMPLE_FRACTION", samples, decision_timestamp=10.0)
    assert val_frac.value == pytest.approx(0.75, abs=1e-2)

    inval_frac = engine.extract_feature("INVALID_SAMPLE_FRACTION", samples, decision_timestamp=10.0)
    assert inval_frac.value == pytest.approx(0.25, abs=1e-2)

    mono = engine.extract_feature("TIMESTAMP_INTEGRITY", samples, decision_timestamp=10.0)
    assert mono.value == 1.0

    duration = engine.extract_feature("MEASUREMENT_DURATION", samples, decision_timestamp=10.0)
    assert duration.value == pytest.approx(3.0, abs=1e-2)


def test_timestamp_inversion_detected():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": 3.3},
        {"timestamp": 0.5, "voltage_v": 3.3}  # Inversion!
    ]
    mono = engine.extract_feature("TIMESTAMP_INTEGRITY", samples, decision_timestamp=10.0)
    assert mono.value == 0.0


# =============================================================================
# 8. TEMPORAL ADMISSIBILITY & FUTURE LEAKAGE REJECTION
# =============================================================================

def test_future_leakage_rejection_at_decision_time():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 10.0, "voltage_v": 3.3},
        {"timestamp": 20.0, "voltage_v": 3.3}
    ]
    # Decision made at t=15.0, but samples extend to t=20.0 (future information!)
    feat = engine.extract_feature("V_MEAN", samples, decision_timestamp=15.0)

    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value
    assert feat.is_admissible is False
    assert feat.temporal_provenance.leakage_status == TemporalLeakageStatus.FUTURE_INFORMATION.value


# =============================================================================
# 9. PHYSICAL BOUNDS & NUMERICAL STABILITY
# =============================================================================

def test_physical_bounds_violation_returns_none():
    engine = CanonicalFeatureEngine()
    # Unphysically low voltage (e.g. 0.05V)
    samples = [
        {"timestamp": 1.0, "voltage_v": 0.05}
    ]
    feat = engine.extract_feature("V_MEAN", samples, decision_timestamp=5.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value


def test_nan_and_inf_handling():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": float("nan")},
        {"timestamp": 2.0, "voltage_v": 3.3}
    ]
    feat = engine.extract_feature("V_MEAN", samples, decision_timestamp=5.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value


# =============================================================================
# 10. DETERMINISM & DEFERRED FEATURE AUDIT
# =============================================================================

def test_extraction_determinism():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": 3.25, "current_a": 5.0},
        {"timestamp": 2.0, "voltage_v": 3.26, "current_a": 5.0}
    ]
    ctx = {"calculation_timestamp": 1000.0}
    feat1 = engine.extract_feature("P_MEAN", samples, decision_timestamp=5.0, context=ctx)
    feat2 = engine.extract_feature("P_MEAN", samples, decision_timestamp=5.0, context=ctx)
    assert feat1.value == feat2.value
    assert feat1.to_dict() == feat2.to_dict()


def test_dq_dv_is_explicitly_deferred_and_rejected():
    engine = CanonicalFeatureEngine()
    feat = engine.extract_feature("DQ_DV_PEAK", [], decision_timestamp=5.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value
    assert "DEFERRED" in feat.physical_meaning


# =============================================================================
# 11. QUALIFICATION SESSION INTEGRATION
# =============================================================================

def test_qualification_session_feature_extraction_and_admissibility():
    engine = CanonicalFeatureEngine()

    seg1 = TestSegment(
        segment_id="SEG_PULSE_01",
        session_id="SESS_P4_TEST",
        segment_type=SegmentType.PULSE.value,
        validation_status="VALID",
        validation_record=PulseValidationRecord(
            pulse_valid=True,
            admissible_for_r0=True,
            admissible_for_chemistry=True,
            configured_i_min=1.0,
            mean_pulse_current_a=10.0,
            current_margin_a=9.0,
            duration_s=10.0,
            delta_v_ohmic=0.08,
            delta_v_total=0.15
        )
    )

    session = QualificationSession(
        session_id="SESS_P4_TEST",
        battery_id="BAT_TEST_01",
        battery_record=BatteryRecord(battery_id="BAT_TEST_01", declared_chemistry="LFP")
    )
    session.add_segment(seg1)

    pulse_samples = [
        {"timestamp": 1.0, "voltage_v": 3.32, "current_a": 10.0},
        {"timestamp": 1.05, "voltage_v": 3.24, "current_a": 10.0},
        {"timestamp": 1.10, "voltage_v": 3.17, "current_a": 10.0}
    ]
    segment_data = {"SEG_PULSE_01": pulse_samples}

    extracted = engine.extract_for_session(session, segment_data, decision_timestamp=5.0)
    assert len(extracted) > 0
    assert len(session.derived_features) == len(extracted)

    # Check session admissibility filtering
    admissible = session.get_admissible_features(decision_timestamp=5.0)
    assert len(admissible) > 0
    names = [f.feature_name for f in admissible]
    assert "V_MEAN" in names
    assert "R0_OHMIC" in names


# =============================================================================
# 12. EDGE CASES & ADMISSION AUDIT
# =============================================================================

def test_edge_cases_empty_samples_and_single_sample():
    engine = CanonicalFeatureEngine()
    # Empty samples
    feat_empty = engine.extract_feature("V_MEAN", [], decision_timestamp=10.0)
    assert feat_empty.value is None
    assert feat_empty.quality_status == DataQualityState.INVALID.value

    # 1 sample when 3 required (e.g. slope)
    feat_single = engine.extract_feature(
        "RELAXATION_SLOPE_DV_DT",
        [{"timestamp": 1.0, "voltage_v": 3.2}],
        decision_timestamp=10.0
    )
    assert feat_single.value is None
    assert feat_single.quality_status == DataQualityState.INVALID.value


def test_online_vs_offline_and_conditional_classification():
    reg = create_canonical_registry()
    v_mean_def = reg.get("V_MEAN")
    assert v_mean_def.temporal_availability in (TemporalAvailability.ONLINE_INCREMENTAL, TemporalAvailability.ONLINE_AVAILABLE)

    charge_ah_def = reg.get("CHARGE_AH")
    assert charge_ah_def.temporal_availability == TemporalAvailability.ONLINE_AFTER_SEGMENT_COMPLETION
    assert charge_ah_def.requires_segment_completion is True

    coul_eff_def = reg.get("COULOMBIC_EFFICIENCY")
    assert coul_eff_def.temporal_availability == TemporalAvailability.CONDITIONAL

    dq_dv_def = reg.get("DQ_DV_PEAK")
    assert dq_dv_def.temporal_availability == TemporalAvailability.OFFLINE_ONLY


def test_8_gate_audit_report():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": 3.3, "current_a": 10.0},
        {"timestamp": 2.0, "voltage_v": 3.2, "current_a": 10.0}
    ]
    feat = engine.extract_feature("V_MEAN", samples, decision_timestamp=5.0)
    audit = engine.audit_admission(feat, samples, decision_timestamp=5.0)

    assert audit.admissible is True
    assert len(audit.gate_evaluations) == 8
    assert audit.all_passed is True
    assert len(audit.failure_reasons) == 0


# =============================================================================
# 14. PHASE 4 ACCEPTANCE & REMEDIATION TESTS (MANDATORY AUDIT ITEMS 1-20)
# =============================================================================

def test_remediation_item1_feature_count_consistency():
    reg = create_canonical_registry()
    assert TOTAL_STANDARDIZED_CANDIDATE_FEATURES == 29
    assert TOTAL_DEFERRED_FEATURES == 1
    assert TOTAL_CATALOGED_FEATURES == 30
    assert reg.count_active_candidates() == 29
    assert reg.count_deferred() == 1
    assert reg.count() == 30
    assert len(reg.list_by_family(FeatureFamily.ELECTRICAL)) == 8
    assert len(reg.list_by_family(FeatureFamily.PULSE)) == 3
    assert len(reg.list_by_family(FeatureFamily.RELAXATION)) == 2
    assert len(reg.list_by_family(FeatureFamily.COULOMETRIC)) == 3
    assert len(reg.list_by_family(FeatureFamily.ENERGY)) == 3
    assert len(reg.list_by_family(FeatureFamily.THERMAL)) == 4
    assert len(reg.list_by_family(FeatureFamily.DATA_QUALITY)) == 6
    assert len(reg.list_by_family(FeatureFamily.DEFERRED)) == 1


def test_remediation_item2_measurement_scope_and_scaling_2s_pack():
    engine = CanonicalFeatureEngine()
    pack_samples = [
        {"timestamp": 1.0, "voltage_v": 7.4, "current_a": 5.0, "temperature_c": 25.0},
        {"timestamp": 2.0, "voltage_v": 7.3, "current_a": 5.0, "temperature_c": 25.0}
    ]
    # If evaluated at CELL scope (series_cells=1), 7.35V exceeds cell max 4.5V -> REJECTED
    feat_cell = engine.extract_feature(
        "V_MEAN",
        pack_samples,
        decision_timestamp=5.0,
        context={"measurement_scope": MeasurementScope.CELL.value, "series_cells": 1}
    )
    assert feat_cell.value is None
    assert feat_cell.quality_status == DataQualityState.INVALID.value

    # When evaluated at PACK scope with series_cells=2, bounds scale [3.0, 9.0]V -> ADMITTED
    feat_pack = engine.extract_feature(
        "V_MEAN",
        pack_samples,
        decision_timestamp=5.0,
        context={"measurement_scope": MeasurementScope.PACK.value, "series_cells": 2}
    )
    assert feat_pack.value is not None
    assert math.isclose(feat_pack.value, 7.35, rel_tol=1e-3)
    assert feat_pack.measurement_scope == MeasurementScope.PACK.value
    assert feat_pack.quality_status == DataQualityState.VALID.value


def test_remediation_item3_4_physical_bounds_justification_and_provisional():
    reg = create_canonical_registry()
    for defn in reg.list_all():
        pb = defn.physical_bounds
        assert isinstance(pb.justification, BoundJustification)
        assert isinstance(pb.is_provisional, bool)
        assert hasattr(pb, "notes")
        if defn.feature_id == "R0_OHMIC":
            assert pb.is_provisional is True
            assert pb.justification == BoundJustification.PROVISIONAL_ASSUMPTION
            assert "provisional" in pb.notes.lower()
        elif defn.feature_id == "VALID_SAMPLE_FRACTION":
            assert pb.justification == BoundJustification.NUMERICAL_SAFETY
            assert pb.is_provisional is False


def test_remediation_item5_invalid_physical_values_rejected():
    engine = CanonicalFeatureEngine()
    samples_low_v = [
        {"timestamp": 1.0, "voltage_v": 0.5, "current_a": 1.0},
        {"timestamp": 2.0, "voltage_v": 0.5, "current_a": 1.0}
    ]
    feat = engine.extract_feature("V_MEAN", samples_low_v, decision_timestamp=5.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value
    assert "ADMISSION REJECTED" in feat.physical_meaning


def test_remediation_item6_no_silent_clipping_inverted_timestamps():
    engine = CanonicalFeatureEngine()
    inverted_samples = [
        {"timestamp": 10.0, "voltage_v": 3.6, "current_a": 1.0},
        {"timestamp": 5.0, "voltage_v": 3.6, "current_a": 1.0}
    ]
    feat = engine.extract_feature("MEASUREMENT_DURATION", inverted_samples, decision_timestamp=20.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value


def test_remediation_item7_availability_semantics_and_offline_rejection():
    engine = CanonicalFeatureEngine()
    samples = [{"timestamp": float(i), "voltage_v": 3.5, "current_a": 1.0} for i in range(10)]
    feat_offline = engine.extract_feature("DQ_DV_PEAK", samples, decision_timestamp=20.0)
    assert feat_offline.value is None
    assert feat_offline.quality_status == DataQualityState.INVALID.value


def test_remediation_item8_segment_completion_dependency():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": 3.7, "current_a": 2.0},
        {"timestamp": 2.0, "voltage_v": 3.8, "current_a": 2.0}
    ]
    feat_incomplete = engine.extract_feature(
        "CHARGE_AH",
        samples,
        decision_timestamp=5.0,
        context={"segment_completed": False}
    )
    assert feat_incomplete.value is None
    assert feat_incomplete.quality_status == DataQualityState.INVALID.value

    feat_complete = engine.extract_feature(
        "CHARGE_AH",
        samples,
        decision_timestamp=5.0,
        context={"segment_completed": True}
    )
    assert feat_complete.value is not None
    assert feat_complete.quality_status == DataQualityState.VALID.value


def test_remediation_item9_10_future_data_injection_attack_rejected():
    engine = CanonicalFeatureEngine()
    future_samples = [
        {"timestamp": 5.0, "voltage_v": 3.7, "current_a": 1.0},
        {"timestamp": 15.0, "voltage_v": 3.6, "current_a": 1.0}
    ]
    feat = engine.extract_feature("V_MEAN", future_samples, decision_timestamp=10.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value
    assert "Look-ahead future information leakage" in feat.physical_meaning


def test_remediation_item11_r0_contextual_provenance():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 0.0, "voltage_v": 3.700, "current_a": 10.0, "temperature_c": 25.0},
        {"timestamp": 0.1, "voltage_v": 3.650, "current_a": 10.0, "temperature_c": 25.0}
    ]
    feat = engine.extract_feature(
        "R0_OHMIC",
        samples=samples,
        decision_timestamp=10.0,
        context={
            "v_pre": 3.700,
            "temperature_c": 25.0,
            "soc": 0.50,
            "pulse_duration_s": 0.1,
            "direction": "DISCHARGE"
        }
    )
    assert feat.value is not None
    assert math.isclose(feat.value, 0.0050, rel_tol=1e-3)
    assert "pulse_amplitude_a" in feat.context
    assert feat.context["pulse_amplitude_a"] == 10.0
    assert feat.context["temperature_c"] == 25.0
    assert feat.context["soc"] == 0.50


def test_remediation_item12_computational_vs_prognostic_distinction():
    reg = create_canonical_registry()
    for defn in reg.list_all():
        assert defn.status in (FeatureCandidateStatus.CANDIDATE, FeatureCandidateStatus.VALIDATED_COMPUTATION, FeatureCandidateStatus.REJECTED)
        desc_lower = defn.description.lower()
        assert "predicts rul" not in desc_lower
        assert "guarantees safety" not in desc_lower


def test_remediation_item13_missingness_semantics_none_not_zero():
    engine = CanonicalFeatureEngine()
    zero_samples = [
        {"timestamp": 1.0, "current_a": 0.0},
        {"timestamp": 2.0, "current_a": 0.0}
    ]
    feat_zero = engine.extract_feature("I_MEAN", zero_samples, decision_timestamp=5.0)
    assert feat_zero.value == 0.0
    assert feat_zero.quality_status == DataQualityState.VALID.value

    corrupt_samples = [
        {"timestamp": 1.0, "current_a": 0.0, "is_valid": False},
        {"timestamp": 2.0, "current_a": 0.0, "is_valid": False}
    ]
    feat_corrupt = engine.extract_feature("I_MEAN", corrupt_samples, decision_timestamp=5.0)
    assert feat_corrupt.value is None
    assert feat_corrupt.quality_status == DataQualityState.INVALID.value


def test_remediation_item14_ground_truth_isolation():
    engine = CanonicalFeatureEngine()
    leaked_samples = [
        {"timestamp": 1.0, "voltage_v": 3.7, "current_a": 1.0, "soh": 0.95},
        {"timestamp": 2.0, "voltage_v": 3.7, "current_a": 1.0, "soh": 0.95}
    ]
    feat = engine.extract_feature("V_MEAN", leaked_samples, decision_timestamp=5.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value
    assert "Ground-truth leakage detected" in feat.physical_meaning


def test_remediation_item15_battery_id_shortcut_rejection():
    defn = FeatureDefinition(
        feature_id="SPECIMEN_ID_PROXY_FEAT",
        feature_name="Specimen ID Shortcut",
        family=FeatureFamily.ELECTRICAL,
        description="Shortcut feature",
        physical_quantity="ID",
        units="dimensionless",
        source_measurements=["voltage_v"],
        source_segments=["PULSE"],
        window=FeatureWindow(window_type="WINDOW"),
        aggregation_method="DIRECT"
    )
    reg = FeatureRegistry()
    reg.register(defn)
    engine = CanonicalFeatureEngine(registry=reg)
    samples = [{"timestamp": 1.0, "voltage_v": 3.7}]
    feat = engine.extract_feature("SPECIMEN_ID_PROXY_FEAT", samples, decision_timestamp=5.0)
    assert feat.value is None
    assert feat.quality_status == DataQualityState.INVALID.value
    assert "Prohibited feature pattern" in feat.physical_meaning


def test_remediation_item16_deterministic_feature_extraction():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": 3.65, "current_a": 2.5, "temperature_c": 24.5},
        {"timestamp": 2.0, "voltage_v": 3.60, "current_a": 2.5, "temperature_c": 24.6},
        {"timestamp": 3.0, "voltage_v": 3.55, "current_a": 2.5, "temperature_c": 24.7}
    ]
    first_feat = engine.extract_feature("V_MEAN", samples, decision_timestamp=5.0)
    for _ in range(5):
        repeat_feat = engine.extract_feature("V_MEAN", samples, decision_timestamp=5.0)
        assert first_feat.value == repeat_feat.value
        assert first_feat.quality_status == repeat_feat.quality_status
        assert first_feat.measurement_scope == repeat_feat.measurement_scope
        assert first_feat.temporal_provenance.observation_window_end == repeat_feat.temporal_provenance.observation_window_end


def test_remediation_item17_feature_versioning_consistency():
    reg = create_canonical_registry()
    for defn in reg.list_all():
        assert defn.feature_version in ("1.0.0", "0.1.0-DEFERRED")
        assert defn.configuration_version == "2.0.0"


def test_remediation_item18_provenance_completeness():
    engine = CanonicalFeatureEngine()
    samples = [
        {"timestamp": 1.0, "voltage_v": 3.7, "current_a": 1.0, "temperature_c": 25.0},
        {"timestamp": 2.0, "voltage_v": 3.7, "current_a": 1.0, "temperature_c": 25.0}
    ]
    feat = engine.extract_feature(
        "V_MEAN",
        samples,
        session_id="SESS_PROV_TEST",
        segment_id="SEG_PROV_TEST",
        decision_timestamp=5.0
    )
    assert feat.value is not None
    assert feat.source_session == "SESS_PROV_TEST"
    assert feat.source_segment == "SEG_PROV_TEST"
    assert feat.source_measurements == ["voltage_v"]
    assert feat.temporal_provenance.observation_window_start == 1.0
    assert feat.temporal_provenance.observation_window_end == 2.0
    assert feat.temporal_provenance.decision_timestamp == 5.0
    assert feat.feature_version == "1.0.0"
    assert feat.configuration_version == "2.0.0"
    assert feat.measurement_scope == MeasurementScope.CELL.value
    assert feat.quality_status == DataQualityState.VALID.value


def test_remediation_item19_thermal_feature_computation_and_safety_context():
    engine = CanonicalFeatureEngine()
    # Physically plausible thermal rise: 25.0 to 26.0 over 2 seconds (0.5 degC/s, within [-1.0, 2.0])
    samples = [
        {"timestamp": 1.0, "temperature_c": 25.0},
        {"timestamp": 2.0, "temperature_c": 25.5},
        {"timestamp": 3.0, "temperature_c": 26.0}
    ]
    t_mean = engine.extract_feature("T_MEAN", samples, decision_timestamp=5.0)
    t_max = engine.extract_feature("T_MAX", samples, decision_timestamp=5.0)
    delta_t = engine.extract_feature("DELTA_T", samples, decision_timestamp=5.0)
    dt_dt = engine.extract_feature("DT_DT", samples, decision_timestamp=5.0)

    assert math.isclose(t_mean.value, 25.5, rel_tol=1e-2)
    assert math.isclose(t_max.value, 26.0, rel_tol=1e-3)
    assert math.isclose(delta_t.value, 1.0, rel_tol=1e-3)
    assert dt_dt.value is not None
    assert math.isclose(dt_dt.value, 0.5, rel_tol=1e-3)

    reg = create_canonical_registry()
    for feat_id in ("T_MEAN", "T_MAX", "DELTA_T", "DT_DT"):
        defn = reg.get(feat_id)
        assert defn.family == FeatureFamily.THERMAL
        assert "predict" not in defn.description.lower()


def test_remediation_item20_registry_single_source_of_truth():
    reg = create_canonical_registry()
    assert reg.count_active_candidates() == TOTAL_STANDARDIZED_CANDIDATE_FEATURES
    assert reg.count_deferred() == TOTAL_DEFERRED_FEATURES
    assert reg.count() == TOTAL_CATALOGED_FEATURES
    for defn in reg.list_all():
        d = defn.to_dict()
        assert "feature_id" in d
        assert "physical_bounds" in d
        assert "supported_scopes" in d
        assert "temporal_availability" in d


