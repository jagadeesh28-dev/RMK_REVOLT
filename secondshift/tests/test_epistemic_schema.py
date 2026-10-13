"""
Unit and Invariant Tests for Canonical Epistemic and Operational Decision Schemas
Project: RMK-REVOLT / SECONDShift Platform

Validates Phase 1 requirements:
1. All epistemic states exist
2. KNOWN_GOOD does not exist
3. All operational decisions exist (and TEST is strictly excluded)
4. All information actions exist
5. Enums serialize correctly
6. DecisionAuditRecord validates
7. Optional future prognostic fields remain None without dummy placeholders
8. Invalid decision/action combinations are rejected
9. Missing RUL does not become 0.0
10. Missing evidence does not become SUPPORTED_HEALTHY
11. Deterministic serialization (round-trip)
12. Deterministic equality
13. Reason codes serialize correctly
"""

import pytest
import json
import time

from secondshift.interfaces.epistemic_schema import (
    EpistemicState,
    OperationalDecision,
    InformationAction,
    ReasonCode,
    DecisionAuditRecord
)


def test_epistemic_states_exist():
    """Verify all 5 canonical epistemic states exist with exact count."""
    expected_states = {
        "SUPPORTED_HEALTHY",
        "UNCERTAIN",
        "DISTRIBUTION_SHIFTED",
        "KNOWN_DEGRADED",
        "INSUFFICIENT_DATA"
    }
    actual_states = {s.name for s in EpistemicState}
    assert actual_states == expected_states, f"Mismatch in epistemic states: {actual_states} != {expected_states}"
    assert len(EpistemicState) == 5, f"Expected exactly 5 epistemic states, got {len(EpistemicState)}"


def test_known_good_strictly_prohibited():
    """Verify KNOWN_GOOD is strictly prohibited across all enums."""
    assert not hasattr(EpistemicState, "KNOWN_GOOD"), "CRITICAL VIOLATION: KNOWN_GOOD exists on EpistemicState!"
    for state in EpistemicState:
        assert "GOOD" not in state.name.upper(), f"Prohibited substring 'GOOD' in epistemic state {state.name}"
        assert "GOOD" not in state.value.upper(), f"Prohibited substring 'GOOD' in epistemic state {state.value}"


def test_operational_decisions_exist():
    """Verify the 4 operational decisions exist, and TEST is excluded."""
    expected_decisions = {"OPERATE", "DERATE", "HOLD", "RETIRE"}
    actual_decisions = {d.name for d in OperationalDecision}
    assert actual_decisions == expected_decisions, f"Mismatch in operational decisions: {actual_decisions}"
    assert len(OperationalDecision) == 4

    # TEST must never be an operational decision
    assert not hasattr(OperationalDecision, "TEST"), "INVARIANT 1 BREACH: TEST is in OperationalDecision!"
    assert "TEST" not in actual_decisions


def test_information_actions_exist():
    """Verify information actions exist and cannot be operational decisions."""
    expected_actions = {"NO_TEST", "REQUEST_TEST"}
    actual_actions = {a.name for a in InformationAction}
    assert actual_actions == expected_actions, f"Mismatch in information actions: {actual_actions}"
    assert len(InformationAction) == 2

    # Information actions must never overlap with operational decisions
    for op in OperationalDecision:
        assert op.name not in actual_actions, f"INVARIANT 2 BREACH: {op.name} exists in InformationAction!"


def test_enum_serialization():
    """Verify all enums serialize to clean, expected string values."""
    assert EpistemicState.SUPPORTED_HEALTHY.value == "SUPPORTED_HEALTHY"
    assert OperationalDecision.OPERATE.value == "OPERATE"
    assert InformationAction.REQUEST_TEST.value == "REQUEST_TEST"
    assert ReasonCode.HARD_SAFETY_BARRIER_TRIP.value == "HARD_SAFETY_BARRIER_TRIP"


def test_decision_audit_record_validation():
    """Verify valid DecisionAuditRecord satisfies all invariants."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_01",
        test_id="QUAL_001",
        timestamp=1728300000.0,
        software_version="2.0.0",
        configuration_version="production_v1",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 0.995, "NMC": 0.003, "UNKNOWN": 0.002},
        chemistry_confidence_state="KNOWN",
        soh_estimate=0.912,
        soh_uncertainty=0.018,
        r0_estimate=0.00195,
        r0_uncertainty=0.00015,
        rul_estimate=None,
        rul_uncertainty=None,
        anomaly_status=None,
        distribution_status=None,
        prognostic_identifiability=None,
        degradation_regime=None,
        safety_barrier_status="PASS",
        safety_reason_codes=[],
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.OPERATE,
        information_action=InformationAction.NO_TEST,
        reason_codes=[ReasonCode.SUPPORTED_EVIDENCE, ReasonCode.STATE_UNCERTAINTY_ACCEPTABLE]
    )

    errors = record.validate_invariants()
    assert errors == [], f"Expected zero validation errors, got: {errors}"


def test_nullable_future_prognostic_fields():
    """Verify that unmodeled future modules remain None without fake placeholders."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_02",
        test_id="QUAL_002",
        timestamp=time.time(),
        software_version="2.0.0",
        configuration_version="default",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 0.50, "NMC": 0.45, "UNKNOWN": 0.05},
        soh_estimate=0.74,
        soh_uncertainty=0.05,
        r0_estimate=0.0028,
        r0_uncertainty=0.0004,
        epistemic_state=EpistemicState.UNCERTAIN,
        operational_decision=OperationalDecision.HOLD,
        information_action=InformationAction.REQUEST_TEST,
        reason_codes=[ReasonCode.CHEMISTRY_UNCERTAIN]
    )

    assert record.rul_estimate is None
    assert record.rul_uncertainty is None
    assert record.anomaly_status is None
    assert record.distribution_status is None
    assert record.prognostic_identifiability is None
    assert record.degradation_regime is None

    # Serialization must retain None (null in JSON) rather than coercing to 0 or ""
    d = record.to_dict()
    assert d["rul_estimate"] is None
    assert d["rul_uncertainty"] is None
    assert d["prognostic_identifiability"] is None

    json_str = record.to_json()
    assert '"rul_estimate": null' in json_str


def test_invalid_decision_action_combinations_rejected():
    """Verify Invariant 8: System cannot authorize OPERATE while requesting additional testing."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_03",
        test_id="QUAL_003",
        timestamp=time.time(),
        software_version="2.0.0",
        configuration_version="default",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 0.95, "NMC": 0.04, "UNKNOWN": 0.01},
        soh_estimate=0.88,
        soh_uncertainty=0.02,
        r0_estimate=0.0021,
        r0_uncertainty=0.0002,
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.OPERATE,
        information_action=InformationAction.REQUEST_TEST, # CONFLICT with OPERATE
        reason_codes=[ReasonCode.ADDITIONAL_TEST_VALUE_HIGH]
    )

    errors = record.validate_invariants()
    assert any("INVARIANT 8 VIOLATION" in e for e in errors), f"Invariant 8 failed to catch conflict: {errors}"


def test_sensor_fault_prevents_operate():
    """Verify Invariant 4: System cannot authorize OPERATE under invalid sensor or telemetry fault."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_04",
        test_id="QUAL_004",
        timestamp=time.time(),
        software_version="2.0.0",
        configuration_version="default",
        data_quality="SENSOR_FAULT",
        sensor_valid=False, # SENSOR FAULT
        telemetry_status="FAULT",
        chemistry_belief={"LFP": 0.99, "NMC": 0.01, "UNKNOWN": 0.0},
        soh_estimate=0.92,
        soh_uncertainty=0.01,
        r0_estimate=0.0019,
        r0_uncertainty=0.0001,
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.OPERATE, # FORBIDDEN when sensor invalid
        information_action=InformationAction.NO_TEST,
        reason_codes=[ReasonCode.SENSOR_FAULT]
    )

    errors = record.validate_invariants()
    assert any("INVARIANT 4 VIOLATION" in e for e in errors), f"Invariant 4 failed to catch fault: {errors}"


def test_missing_rul_does_not_become_zero():
    """Verify Invariant 5: Missing RUL cannot be faked with 0.0."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_05",
        test_id="QUAL_005",
        timestamp=time.time(),
        software_version="2.0.0",
        configuration_version="default",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 0.99, "NMC": 0.01, "UNKNOWN": 0.0},
        soh_estimate=0.85,
        soh_uncertainty=0.02,
        r0_estimate=0.0022,
        r0_uncertainty=0.0002,
        rul_estimate=0.0, # FAKE 0.0 PLACEHOLDER
        rul_uncertainty=None,
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.HOLD,
        information_action=InformationAction.NO_TEST,
        reason_codes=[]
    )

    errors = record.validate_invariants()
    assert any("INVARIANT 5 VIOLATION" in e for e in errors), f"Invariant 5 failed to catch 0.0 RUL placeholder: {errors}"


def test_missing_evidence_does_not_become_supported_healthy():
    """Verify Invariant 6: High uncertainty cannot be declared SUPPORTED_HEALTHY."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_06",
        test_id="QUAL_006",
        timestamp=time.time(),
        software_version="2.0.0",
        configuration_version="default",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 0.33, "NMC": 0.33, "UNKNOWN": 0.34},
        soh_estimate=0.75,
        soh_uncertainty=0.15, # HIGH UNCERTAINTY (15% sigma)
        r0_estimate=0.0025,
        r0_uncertainty=0.0010,
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY, # INADMISSIBLE UNDER HIGH SIGMA
        operational_decision=OperationalDecision.HOLD,
        information_action=InformationAction.REQUEST_TEST,
        reason_codes=[]
    )

    errors = record.validate_invariants()
    assert any("INVARIANT 6 VIOLATION" in e for e in errors), f"Invariant 6 failed to catch high uncertainty: {errors}"


def test_deterministic_serialization_and_roundtrip():
    """Verify deterministic JSON serialization, deserialization, and field fidelity."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_07",
        test_id="QUAL_007",
        timestamp=1728301234.56,
        software_version="2.0.0",
        configuration_version="v2_baseline",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 0.98, "NMC": 0.015, "UNKNOWN": 0.005},
        chemistry_confidence_state="KNOWN",
        soh_estimate=0.885,
        soh_uncertainty=0.022,
        r0_estimate=0.0021,
        r0_uncertainty=0.00018,
        rul_estimate=None,
        rul_uncertainty=None,
        anomaly_status=None,
        distribution_status=None,
        prognostic_identifiability=None,
        degradation_regime=None,
        safety_barrier_status="PASS",
        safety_reason_codes=[],
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.OPERATE,
        information_action=InformationAction.NO_TEST,
        reason_codes=[ReasonCode.SUPPORTED_EVIDENCE]
    )

    # 1. Determinism
    json1 = record.to_json(indent=2)
    json2 = record.to_json(indent=2)
    assert json1 == json2, "Non-deterministic JSON serialization detected"

    # 2. Round-trip Deserialization
    reconstructed = DecisionAuditRecord.from_json(json1)
    assert reconstructed.battery_id == record.battery_id
    assert reconstructed.epistemic_state == record.epistemic_state
    assert reconstructed.operational_decision == record.operational_decision
    assert reconstructed.information_action == record.information_action
    assert reconstructed.rul_estimate is None
    assert reconstructed.reason_codes == record.reason_codes


def test_deterministic_equality():
    """Verify deterministic equality between identical record instances."""
    params = dict(
        battery_id="SPECIMEN_08",
        test_id="QUAL_008",
        timestamp=1000.0,
        software_version="2.0.0",
        configuration_version="default",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 1.0},
        soh_estimate=0.90,
        soh_uncertainty=0.01,
        r0_estimate=0.002,
        r0_uncertainty=0.0001,
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.OPERATE,
        information_action=InformationAction.NO_TEST,
        reason_codes=[ReasonCode.SUPPORTED_EVIDENCE]
    )

    rec1 = DecisionAuditRecord(**params)
    rec2 = DecisionAuditRecord(**params)
    assert rec1 == rec2

    # Mutation breaks equality
    rec3 = DecisionAuditRecord(**{**params, "operational_decision": OperationalDecision.DERATE})
    assert rec1 != rec3


def test_reason_codes_serialization():
    """Verify reason codes serialize to/from string lists cleanly."""
    record = DecisionAuditRecord(
        battery_id="SPECIMEN_09",
        test_id="QUAL_009",
        timestamp=time.time(),
        software_version="2.0.0",
        configuration_version="default",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="CONNECTED",
        chemistry_belief={"LFP": 0.99},
        soh_estimate=0.55,
        soh_uncertainty=0.02,
        r0_estimate=0.0045,
        r0_uncertainty=0.0003,
        epistemic_state=EpistemicState.KNOWN_DEGRADED,
        operational_decision=OperationalDecision.RETIRE,
        information_action=InformationAction.NO_TEST,
        safety_reason_codes=[ReasonCode.SAFETY_LIMIT_EXCEEDED, ReasonCode.HARD_SAFETY_BARRIER_TRIP],
        reason_codes=[ReasonCode.KNOWN_DEGRADATION, ReasonCode.NO_ADDITIONAL_TEST_VALUE]
    )

    d = record.to_dict()
    assert d["safety_reason_codes"] == ["SAFETY_LIMIT_EXCEEDED", "HARD_SAFETY_BARRIER_TRIP"]
    assert d["reason_codes"] == ["KNOWN_DEGRADATION", "NO_ADDITIONAL_TEST_VALUE"]

    # Reconstruct from dict
    rec_reconstructed = DecisionAuditRecord.from_dict(d)
    assert rec_reconstructed.safety_reason_codes == [
        ReasonCode.SAFETY_LIMIT_EXCEEDED,
        ReasonCode.HARD_SAFETY_BARRIER_TRIP
    ]
    assert rec_reconstructed.reason_codes == [
        ReasonCode.KNOWN_DEGRADATION,
        ReasonCode.NO_ADDITIONAL_TEST_VALUE
    ]
