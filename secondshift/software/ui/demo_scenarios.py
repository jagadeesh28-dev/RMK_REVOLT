"""
Deterministic Demo & Replay Scenarios (Phase 3)
Project: RMK-REVOLT / SECONDShift Platform

Provides six deterministic scenarios representing canonical operational and
adversarial situations on the qualification test station:

SCENARIO A: Healthy valid pulse
SCENARIO B: Zero-current false pulse
SCENARIO C: Sensor fault
SCENARIO D: Contactor trip (Hardware safety override)
SCENARIO E: Insufficient data (Passive intake)
SCENARIO F: Distribution shift placeholder (OOD boundary)

Zero fake ML values: RUL is explicitly displayed as NOT YET IMPLEMENTED.
"""

from typing import Dict, Any
from secondshift.interfaces.qualification_schema import (
    BatteryRecord,
    TestProtocol,
    TestSegment,
    SegmentType,
    SessionLifecycleStatus,
    QualificationDataStatus,
    TemporalProvenance,
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


def create_scenario_a_healthy_pulse() -> Dict[str, Any]:
    """Scenario A: Healthy valid pulse characterization."""
    bat = BatteryRecord(
        battery_id="BAT_DEMO_01",
        cell_id="CELL_DEMO_01",
        declared_chemistry="LFP",
        nominal_voltage=3.2,
        nominal_capacity_ah=50.0,
        source="INCOMING_INSPECTION"
    )
    proto = TestProtocol(protocol_id="QUAL_BENCH_RAPID_V2", pulse_current_a=10.0, pulse_duration_s=10.0)
    chem = InferredChemistryRecord(
        inferred_chemistry="LFP",
        confidence_state="KNOWN",
        confidence_score=0.96,
        posterior={"LFP": 0.96, "NMC": 0.04}
    )
    audit = DecisionAuditRecord(
        battery_id="BAT_DEMO_01",
        test_id="TEST_PULSE_01",
        timestamp=12.0,
        software_version="SECONDShift-v2.0",
        configuration_version="2.0.0",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="VALID",
        chemistry_belief={"LFP": 0.96, "NMC": 0.04},
        epistemic_state=EpistemicState.SUPPORTED_HEALTHY,
        operational_decision=OperationalDecision.OPERATE,
        information_action=InformationAction.NO_TEST,
        reason_codes=[ReasonCode.SUPPORTED_EVIDENCE]
    )
    session = QualificationSession(
        session_id="SESS_DEMO_A",
        battery_id="BAT_DEMO_01",
        protocol_id=proto.protocol_id,
        battery_record=bat,
        protocol=proto,
        inferred_chemistry_record=chem,
        soh_estimate=0.96,
        soh_uncertainty=0.02,
        r0_mohm_estimate=1.52,
        audit_record=audit,
        status=SessionLifecycleStatus.COMPLETED.value
    )

    result = {
        "final_decision": "OPERATE",
        "actuation_intent": "OPERATE_FULL",
        "safety_tripped": False,
        "elapsed_time_s": 15.2,
        "reason": "Specimen verified healthy within calibrated operational bounds"
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.28, "current_a": 10.0, "temperature_c": 24.8,
            "sequence_number": 42, "is_valid": True, "quality": "GOOD"
        }},
        {"event_type": "PULSE_VALIDATION", "data": {
            "pulse_valid": True, "current_flow_valid": True,
            "delta_v_total": 0.020, "delta_v_ohmic": 0.015,
            "admissibility_reasons": []
        }}
    ]
    return sa.build_status_snapshot(result, events, mode="mock", session=session)


def create_scenario_b_zero_current_false_pulse() -> Dict[str, Any]:
    """Scenario B: Zero-current false pulse (command issued, but I ≈ 0 A)."""
    bat = BatteryRecord(
        battery_id="BAT_DEMO_02",
        cell_id="CELL_DEMO_02",
        declared_chemistry="NMC",
        nominal_voltage=3.65,
        nominal_capacity_ah=60.0
    )
    audit = DecisionAuditRecord(
        battery_id="BAT_DEMO_02",
        test_id="TEST_PULSE_01",
        timestamp=10.0,
        software_version="SECONDShift-v2.0",
        configuration_version="2.0.0",
        data_quality="INVALID",
        sensor_valid=True,
        telemetry_status="VALID",
        chemistry_belief={"LFP": 0.5, "NMC": 0.5},
        epistemic_state=EpistemicState.INSUFFICIENT_DATA,
        operational_decision=OperationalDecision.HOLD,
        information_action=InformationAction.REQUEST_TEST,
        reason_codes=[ReasonCode.CURRENT_FLOW_BELOW_MINIMUM]
    )
    session = QualificationSession(
        session_id="SESS_DEMO_B",
        battery_id="BAT_DEMO_02",
        battery_record=bat,
        soh_estimate=None,  # Unavailable
        r0_mohm_estimate=None,  # Never 0.0!
        audit_record=audit,
        status=SessionLifecycleStatus.RUNNING.value
    )

    result = {
        "final_decision": "HOLD",
        "actuation_intent": "SAFE_STANDBY",
        "safety_tripped": False,
        "elapsed_time_s": 8.0,
        "reason": "Diagnostic pulse rejected: Current flow below configured bench threshold",
        "pulse_valid": False,
        "current_flow_valid": False,
        "final_r0_mohm": None
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.65, "current_a": 0.0, "temperature_c": 23.5,
            "sequence_number": 15, "is_valid": True, "quality": "GOOD"
        }},
        {"event_type": "PULSE_VALIDATION", "data": {
            "pulse_valid": False, "current_flow_valid": False,
            "delta_v_total": None, "delta_v_ohmic": None,
            "admissibility_reasons": ["CURRENT_FLOW_BELOW_MINIMUM"]
        }}
    ]
    return sa.build_status_snapshot(result, events, mode="mock", session=session)


def create_scenario_c_sensor_fault() -> Dict[str, Any]:
    """Scenario C: Telemetry sensor failure (hardware disconnection or range fault)."""
    bat = BatteryRecord(battery_id="BAT_DEMO_03", declared_chemistry="LFP", nominal_voltage=3.2, nominal_capacity_ah=50.0)
    session = QualificationSession(
        session_id="SESS_DEMO_C",
        battery_id="BAT_DEMO_03",
        battery_record=bat,
        status=SessionLifecycleStatus.RUNNING.value
    )
    result = {
        "final_decision": "HOLD",
        "actuation_intent": "SAFE_STANDBY",
        "safety_tripped": False,
        "reason": "Telemetry invalid: Voltage reading out of electrochemical bounds"
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 0.12, "current_a": 0.0, "temperature_c": 22.0,
            "sequence_number": 8, "is_valid": False, "quality": "INVALID",
            "errors": ["VOLTAGE_BELOW_PLAUSIBLE_MINIMUM"]
        }},
        {"event_type": "DATA_QUALITY", "data": {
            "sensor_valid": False, "telemetry_valid": False, "inference_admissible": False,
            "quality_state": "INVALID", "reason_codes": ["SENSOR_FAULT"]
        }}
    ]
    return sa.build_status_snapshot(result, events, mode="mock", session=session)


def create_scenario_d_contactor_trip() -> Dict[str, Any]:
    """Scenario D: Hardware supervisor trip (analog interlock or thermal snap)."""
    bat = BatteryRecord(battery_id="BAT_DEMO_04", declared_chemistry="LFP", nominal_voltage=3.2, nominal_capacity_ah=50.0)
    session = QualificationSession(
        session_id="SESS_DEMO_D",
        battery_id="BAT_DEMO_04",
        battery_record=bat,
        status=SessionLifecycleStatus.SAFE_STOP.value
    )
    result = {
        "final_decision": "HOLD",
        "actuation_intent": "OPEN_ALL_CONTACTORS",
        "safety_tripped": True,
        "trip_reason": "HARDWARE_COMPARATOR_TRIP: Cell overvoltage threshold breach",
        "reason": "Hardware trip during test: Testing halted immediately"
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.82, "current_a": 0.0, "temperature_c": 31.0,
            "sequence_number": 88, "is_valid": False, "quality": "INVALID",
            "hardware_state": "TRIPPED"
        }},
        {"event_type": "PULSE_VALIDATION", "data": {
            "pulse_valid": False, "current_flow_valid": False,
            "hardware_tripped": True, "contactor_open": True,
            "delta_v_total": None, "delta_v_ohmic": None,
            "admissibility_reasons": ["HARDWARE_TRIP_DURING_TEST", "CONTACTOR_OPEN_FAULT"]
        }}
    ]
    return sa.build_status_snapshot(result, events, mode="mock", session=session)


def create_scenario_e_insufficient_data() -> Dict[str, Any]:
    """Scenario E: Intake inspection with insufficient history (prior unknown)."""
    bat = BatteryRecord(battery_id="BAT_DEMO_05", declared_chemistry="UNKNOWN")
    session = QualificationSession(
        session_id="SESS_DEMO_E",
        battery_id="BAT_DEMO_05",
        battery_record=bat,
        status=SessionLifecycleStatus.CREATED.value
    )
    result = {
        "final_decision": "HOLD",
        "actuation_intent": "SAFE_STANDBY",
        "safety_tripped": False,
        "recommended_test": "PASSIVE_REST_RELAXATION",
        "reason": "Insufficient degradation history: Requesting diagnostic relaxation"
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.25, "current_a": 0.0, "temperature_c": 21.0,
            "sequence_number": 1, "is_valid": True, "quality": "GOOD"
        }}
    ]
    return sa.build_status_snapshot(result, events, mode="mock", session=session)


def create_scenario_f_distribution_shift() -> Dict[str, Any]:
    """Scenario F: Distribution-shift placeholder (observed polarization outside reference manifold)."""
    bat = BatteryRecord(battery_id="BAT_DEMO_06", declared_chemistry="LFP", nominal_voltage=3.2, nominal_capacity_ah=50.0)
    audit = DecisionAuditRecord(
        battery_id="BAT_DEMO_06",
        test_id="TEST_01",
        timestamp=20.0,
        software_version="SECONDShift-v2.0",
        configuration_version="2.0.0",
        data_quality="VALID",
        sensor_valid=True,
        telemetry_status="VALID",
        chemistry_belief={"LFP": 0.7, "NMC": 0.3},
        epistemic_state=EpistemicState.DISTRIBUTION_SHIFTED,
        operational_decision=OperationalDecision.HOLD,
        information_action=InformationAction.REQUEST_TEST,
        reason_codes=[ReasonCode.DISTRIBUTION_SHIFT_DETECTED]
    )
    session = QualificationSession(
        session_id="SESS_DEMO_F",
        battery_id="BAT_DEMO_06",
        battery_record=bat,
        audit_record=audit,
        status=SessionLifecycleStatus.COMPLETED.value
    )
    result = {
        "final_decision": "HOLD",
        "operational_decision": "HOLD",
        "information_action": "REQUEST_TEST",
        "distribution_shifted": True,
        "epistemic_state": "DISTRIBUTION_SHIFTED",
        "safety_tripped": False,
        "reason": "Feature distribution outside validated population manifold: Prognostic validity uncertain"
    }
    events = [
        {"event_type": "TELEMETRY_EVALUATION", "data": {
            "voltage_v": 3.29, "current_a": 5.0, "temperature_c": 25.0,
            "sequence_number": 33, "is_valid": True, "quality": "GOOD"
        }}
    ]
    return sa.build_status_snapshot(result, events, mode="mock", session=session)
