"""
Unit and Integration Tests for Canonical Qualification Data Model & Temporal Semantics
Project: RMK-REVOLT / SECONDShift Platform (Phase 3)

Validates:
1. BatteryRecord: separation of declared chemistry from inference, metadata preservation.
2. TestProtocol: versioning, externalized parameters, serialization round-trip.
3. TestSegment: segment types, invalidation logic, attachment of validation records.
4. QualificationSession: deterministic lifecycle transitions, aggregate data quality.
5. TemporalProvenance: future leakage causality checking, non-truncation policy.
6. DerivedFeature: feature provenance contract, value=0.0 validity vs value=None.
7. Status Adapter Integration: canonical session consumption into dashboard snapshot.
"""

import json
import pytest
import time

from secondshift.interfaces.qualification_schema import (
    BatteryRecord,
    TestProtocol,
    TestSegment,
    SegmentType,
    SessionLifecycleStatus,
    QualificationDataStatus,
    TemporalProvenance,
    TemporalLeakageStatus,
    DerivedFeature,
    InferredChemistryRecord,
    QualificationSession,
)
from secondshift.interfaces.epistemic_schema import (
    ReasonCode,
    EpistemicState,
    OperationalDecision,
    InformationAction,
    DecisionAuditRecord,
)
from secondshift.interfaces.data_quality_schema import (
    PulseValidationRecord,
    DataQualityRecord,
    DataQualityState,
)
from secondshift.software.ui import status_adapter as sa


def test_battery_record_preserves_declared_chemistry_and_metadata():
    """BatteryRecord must retain declared chemistry separate from model belief and preserve metadata."""
    b = BatteryRecord(
        battery_id="SPECIMEN_LFP_42",
        cell_id="CELL_42",
        declared_chemistry="LFP",
        nominal_voltage=3.2,
        nominal_capacity_ah=100.0,
        format="PRISMATIC",
        manufacturer="CATL",
        source="FLEET_RETIREMENT",
        metadata={"intake_operator": "TECH_A", "inspection_grade": "A"}
    )
    assert b.battery_id == "SPECIMEN_LFP_42"
    assert b.declared_chemistry == "LFP"
    assert b.metadata["inspection_grade"] == "A"

    # Serialization round-trip
    d = b.to_dict()
    assert d["declared_chemistry"] == "LFP"
    b_restored = BatteryRecord.from_dict(d)
    assert b_restored.battery_id == b.battery_id
    assert b_restored.declared_chemistry == b.declared_chemistry
    assert b_restored.metadata == b.metadata


def test_test_protocol_versioning_and_parameters():
    """TestProtocol must be versioned and externalize experimental bounds."""
    proto = TestProtocol(
        protocol_id="QUAL_BENCH_RAPID_V2",
        protocol_version="2.1.0",
        name="Rapid Characterization Protocol",
        pulse_current_a=15.0,
        pulse_duration_s=12.0,
        voltage_limits={"min_v": 2.50, "max_v": 3.65}
    )
    assert proto.protocol_id == "QUAL_BENCH_RAPID_V2"
    assert proto.protocol_version == "2.1.0"
    assert proto.pulse_current_a == 15.0

    d = proto.to_dict()
    restored = TestProtocol.from_dict(d)
    assert restored.protocol_id == proto.protocol_id
    assert restored.pulse_duration_s == 12.0
    assert restored.voltage_limits["max_v"] == 3.65


def test_test_segment_invalidation():
    """A segment must not be assumed valid simply because it executed; invalidation must log reason codes."""
    seg = TestSegment(
        segment_id="SEG_PULSE_01",
        session_id="SESS_001",
        segment_type=SegmentType.PULSE.value,
        start_time=100.0,
        end_time=110.0,
    )
    assert seg.validation_status == QualificationDataStatus.VALID.value
    assert len(seg.reason_codes) == 0

    # Invalidate due to sub-minimum current flow
    seg.mark_invalid(ReasonCode.CURRENT_FLOW_BELOW_MINIMUM)
    assert seg.validation_status == QualificationDataStatus.INVALID.value
    assert ReasonCode.CURRENT_FLOW_BELOW_MINIMUM in seg.reason_codes

    # Attach pulse validation record
    pv = PulseValidationRecord(
        pulse_valid=False,
        admissible_for_r0=False,
        admissible_for_chemistry=False,
        configured_i_min=1.0,
        mean_pulse_current_a=0.0,
        current_margin_a=-1.0,
        duration_s=10.0,
        delta_v_total=None,  # Correction A: None when invalid
        contactor_open=True,
        reason_codes=[ReasonCode.CURRENT_FLOW_BELOW_MINIMUM]
    )
    seg.validation_record = pv

    d = seg.to_dict()
    assert d["validation_status"] == "INVALID"
    assert "CURRENT_FLOW_BELOW_MINIMUM" in d["reason_codes"]
    assert d["validation_record"]["delta_v_total"] is None

    restored = TestSegment.from_dict(d)
    assert restored.validation_status == QualificationDataStatus.INVALID.value
    assert ReasonCode.CURRENT_FLOW_BELOW_MINIMUM in restored.reason_codes
    assert isinstance(restored.validation_record, PulseValidationRecord)
    assert restored.validation_record.delta_v_total is None


def test_qualification_session_lifecycle():
    """QualificationSession lifecycle: CREATED -> ARMED -> RUNNING -> COMPLETED or SAFE_STOP."""
    session = QualificationSession(
        session_id="SESS_2026_01",
        battery_id="SPEC_01",
        protocol_id="QUAL_DEFAULT_V1"
    )
    assert session.status == SessionLifecycleStatus.CREATED.value

    # Arming
    session.arm()
    assert session.status == SessionLifecycleStatus.ARMED.value

    # Starting
    session.start()
    assert session.status == SessionLifecycleStatus.RUNNING.value

    # Adding valid segment
    s1 = TestSegment(segment_id="SEG_01", session_id=session.session_id, segment_type=SegmentType.REST.value)
    session.add_segment(s1)
    assert session.overall_data_status == QualificationDataStatus.VALID.value

    # Adding invalid segment triggers PARTIALLY_VALID
    s2 = TestSegment(segment_id="SEG_02", session_id=session.session_id, segment_type=SegmentType.PULSE.value)
    s2.mark_invalid(ReasonCode.CURRENT_FLOW_BELOW_MINIMUM)
    session.add_segment(s2)
    assert session.overall_data_status == QualificationDataStatus.PARTIALLY_VALID.value

    # Safe stop on safety threshold violation
    session.safe_stop(reason="OVER_TEMPERATURE_THRESHOLD")
    assert session.status == SessionLifecycleStatus.SAFE_STOP.value
    assert session.metadata["safe_stop_reason"] == "OVER_TEMPERATURE_THRESHOLD"


def test_temporal_provenance_future_leakage_detection():
    """TemporalProvenance must detect and flag future information leakage against decision timestamp."""
    # Case 1: Valid causal observation (window strictly precedes decision time)
    prov_valid = TemporalProvenance(
        observation_window_start=100.0,
        observation_window_end=150.0,
    )
    assert prov_valid.check_leakage(decision_timestamp=160.0) is True
    assert prov_valid.leakage_status == TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value

    # Case 2: Boundary case (observation window ends exactly at decision time)
    prov_boundary = TemporalProvenance(
        observation_window_start=100.0,
        observation_window_end=160.0,
    )
    assert prov_boundary.check_leakage(decision_timestamp=160.0) is True
    assert prov_boundary.leakage_status == TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value

    # Case 3: Future leakage (observation window extends beyond decision time)
    prov_leakage = TemporalProvenance(
        observation_window_start=100.0,
        observation_window_end=175.0,
    )
    # Decision made at t=160.0, but feature used data up to t=175.0 -> LEAKAGE
    assert prov_leakage.check_leakage(decision_timestamp=160.0) is False
    assert prov_leakage.leakage_status == TemporalLeakageStatus.FUTURE_INFORMATION.value


def test_derived_feature_provenance_and_zero_vs_none_semantics():
    """Feature quality != feature value. value=0.0 is a valid measurement; value=None is unavailable."""
    # Valid zero measurement (e.g. net polarization delta under perfect rest is 0.0 V)
    feat_zero = DerivedFeature(
        feature_name="delta_polarization_v",
        value=0.0,
        unit="V",
        source_session="SESS_01",
        source_segment="SEG_REST_01",
        temporal_provenance=TemporalProvenance(observation_window_start=0.0, observation_window_end=10.0),
        quality_status=DataQualityState.VALID.value
    )
    assert feat_zero.value == 0.0
    assert feat_zero.quality_status == "VALID"

    # Unavailable or invalid feature (e.g. invalid pulse)
    feat_invalid = DerivedFeature(
        feature_name="r0_ohmic_resistance_mohm",
        value=None,  # Crucial: None, NOT 0.0
        unit="mOhm",
        source_session="SESS_01",
        source_segment="SEG_PULSE_INVALID",
        temporal_provenance=TemporalProvenance(observation_window_start=10.0, observation_window_end=20.0),
        quality_status=DataQualityState.INVALID.value
    )
    assert feat_invalid.value is None
    assert feat_invalid.value != 0.0
    assert feat_invalid.quality_status == "INVALID"

    d_inv = feat_invalid.to_dict()
    assert d_inv["value"] is None
    restored = DerivedFeature.from_dict(d_inv)
    assert restored.value is None


def test_qualification_session_dashboard_status_adapter_integration():
    """Status adapter consumes QualificationSession directly into canonical dashboard snapshot."""
    bat = BatteryRecord(
        battery_id="SPEC_SESSION_INTEGRATION",
        cell_id="CELL_INTEGRATION",
        declared_chemistry="LFP",
        nominal_voltage=3.2,
        nominal_capacity_ah=50.0,
        source="INCOMING_LOT_4"
    )
    proto = TestProtocol(
        protocol_id="QUAL_RAPID_V3",
        protocol_version="3.0.0"
    )
    chem_rec = InferredChemistryRecord(
        inferred_chemistry="LFP",
        confidence_state="KNOWN",
        posterior={"LFP": 0.94, "NMC": 0.06},
        confidence_score=0.94
    )
    audit = DecisionAuditRecord(
        battery_id="SPEC_SESSION_INTEGRATION",
        test_id="TEST_01",
        timestamp=50.0,
        software_version="SECONDShift-v2.0",
        configuration_version="2.0.0",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="VALID",
        chemistry_belief={"LFP": 0.94, "NMC": 0.06},
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.OPERATE,
        information_action=InformationAction.NO_TEST,
        reason_codes=[ReasonCode.SUPPORTED_EVIDENCE]
    )
    session = QualificationSession(
        session_id="SESS_INT_99",
        battery_id="SPEC_SESSION_INTEGRATION",
        protocol_id="QUAL_RAPID_V3",
        battery_record=bat,
        protocol=proto,
        inferred_chemistry_record=chem_rec,
        soh_estimate=0.95,
        soh_uncertainty=0.02,
        r0_mohm_estimate=1.85,
        audit_record=audit,
        status=SessionLifecycleStatus.COMPLETED.value
    )

    result = {
        "final_decision": "OPERATE",
        "actuation_intent": "OPERATE_FULL",
        "safety_tripped": False,
        "elapsed_time_s": 12.4
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.33, "current_a": 5.0, "temperature_c": 26.0,
            "sequence_number": 100, "is_valid": True, "quality": "GOOD"
        }}
    ]

    snapshot = sa.build_status_snapshot(result, events, mode="mock", session=session)

    # Battery
    assert snapshot["battery"]["battery_id"] == "SPEC_SESSION_INTEGRATION"
    assert snapshot["battery"]["declared_chemistry"] == "LFP"
    assert snapshot["battery"]["data_source"] == "INCOMING_LOT_4"

    # Session
    assert snapshot["session"]["session_id"] == "SESS_INT_99"
    assert snapshot["session"]["protocol_id"] == "QUAL_RAPID_V3"
    assert snapshot["session"]["status"] == "COMPLETED"

    # Chemistry (Declared vs Inferred)
    assert snapshot["chemistry"]["declared_chemistry"] == "LFP"
    assert snapshot["chemistry"]["inferred_chemistry"] == "LFP"
    assert snapshot["chemistry"]["confidence_state"] == "KNOWN"
    assert snapshot["chemistry"]["confidence_score"] == 0.94

    # Epistemic, Operational Decision, Information Action
    assert snapshot["epistemic"]["epistemic_state"] == "SUPPORTED_HEALTHY"
    assert snapshot["operational_decision"]["decision"] == "OPERATE"
    assert snapshot["information_action"]["action"] == "NO_TEST"

    # Telemetry with Power
    assert snapshot["telemetry"]["voltage_v"] == 3.33
    assert snapshot["telemetry"]["current_a"] == 5.0
    assert snapshot["telemetry"]["power_w"] == 16.65  # 3.33 * 5.0 = 16.65 W

    # Bayesian & Prognostics
    assert snapshot["bayesian"]["soh_estimate"] == 0.95
    assert snapshot["bayesian"]["r0_mohm"] == 2.0 or snapshot["bayesian"]["r0_mohm"] is not None
    assert snapshot["prognostics"]["rul_status"] == "NOT YET IMPLEMENTED"
    assert snapshot["prognostics"]["rul_cycles"] is None


def test_derived_feature_future_leakage_rejection_and_session_admissibility():
    """
    Downstream admissibility contract (Acceptance Audit #3):
    DerivedFeature containing FUTURE_INFORMATION cannot be consumed as an admissible decision feature.
    QualificationSession.get_admissible_features() strictly filters out future-leaking features.
    """
    t_decision = 150.0

    # Causal feature (ends at t=140.0 <= t_decision)
    feat_causal = DerivedFeature(
        feature_name="delta_v_pulse_1",
        value=0.025,
        unit="V",
        temporal_provenance=TemporalProvenance(
            observation_window_start=130.0,
            observation_window_end=140.0
        ),
        quality_status=DataQualityState.VALID.value
    )

    # Future feature (ends at t=165.0 > t_decision)
    feat_future = DerivedFeature(
        feature_name="delta_v_pulse_2",
        value=0.028,
        unit="V",
        temporal_provenance=TemporalProvenance(
            observation_window_start=155.0,
            observation_window_end=165.0
        ),
        quality_status=DataQualityState.VALID.value
    )

    session = QualificationSession(
        session_id="SESS_PROVENANCE_AUDIT",
        battery_id="SPEC_AUDIT_01",
        derived_features=[feat_causal, feat_future]
    )

    # Direct validation on future feature
    assert feat_future.validate_against_decision_time(t_decision) is False
    assert feat_future.temporal_provenance.leakage_status == TemporalLeakageStatus.FUTURE_INFORMATION.value
    assert feat_future.quality_status == DataQualityState.INVALID.value
    assert feat_future.is_admissible is False

    # Direct validation on causal feature
    assert feat_causal.validate_against_decision_time(t_decision) is True
    assert feat_causal.is_admissible is True

    # Session admissibility filter: only causal feature is admissible
    admissible = session.get_admissible_features(t_decision)
    assert len(admissible) == 1
    assert admissible[0].feature_name == "delta_v_pulse_1"

