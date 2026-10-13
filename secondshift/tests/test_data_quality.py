"""
Phase 2 Comprehensive Test Suite: Data Quality & Scientific Measurement Admissibility
Project: RMK-REVOLT / SECONDShift Platform

Validates:
1. Valid telemetry frames and diagnostic pulses
2. NaN handling in voltage, current, temperature
3. Temporal integrity (staleness, timestamp inversion, clock skew)
4. Sequence continuity (gaps, regressions, duplicates)
5. Current-flow feasibility (|I| >= I_MIN)
6. Zero-current pulse rejection
7. Contactor opening vs. sensor fault separation
8. Hardware protection trips (LM393 analog comparator, thermal snaps)
9. Transient validation (dt, dI, dV, sampling density)
10. Scientific admissibility isolation: invalid pulses rejected by R0 estimator and chemistry engine
11. Hostile Adversarial "FALSE PULSE" scenario
12. Strict epistemic ground-truth isolation
13. Separation of SensorValidity from MeasurementAdmissibility
14. Deterministic validation reproducibility
15. Invariant enforcement in DataQualityRecord
16. Externalized versioned configuration thresholds
"""

import time
import math
import copy
import pytest
import numpy as np

from secondshift.interfaces.telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus
)
from secondshift.interfaces.epistemic_schema import ReasonCode
from secondshift.interfaces.data_quality_schema import (
    DataQualityRecord,
    PulseValidationRecord,
    DataQualityState,
    EventClassification
)
from secondshift.config.validation_config import MeasurementValidationConfig
from secondshift.interfaces.telemetry_validator import TelemetryValidator, TelemetryValidationResult
from secondshift.software.hermes.hermes_driver import MockHermesHardware
from secondshift.software.hermes.measurement_primitives import HermesMeasurementEngine
from secondshift.software.secondshift.closed_loop_runner import ClosedLoopRunner
from secondshift.software.estimators.bayesian_state_estimator import BayesianStateEstimator
from secondshift.software.chemistry.chemistry_engine import ChemistryDisambiguationEngine


@pytest.fixture
def validator():
    """Provides a fresh TelemetryValidator with standard configuration."""
    cfg = MeasurementValidationConfig(
        i_min_pulse_a=1.0,
        min_pulse_duration_s=0.05,
        max_stale_age_s=2.0,
        future_skew_tolerance_s=5.0
    )
    return TelemetryValidator(config=cfg)


@pytest.fixture
def clean_frame():
    """Provides a known-good TelemetryFrame."""
    return TelemetryFrame(
        device_id="ESP32_HERMES_01",
        sequence_number=100,
        timestamp=time.time(),
        voltage_v=3.350,
        current_a=2.50,
        temperature_c=25.2,
        estimated_soc=0.60,
        cell_voltages_v=[3.350],
        cell_temperatures_c=[25.2],
        sensor_status={"ADS1115": SensorHealthStatus.OK.value, "INA219": SensorHealthStatus.OK.value},
        communication_status=CommunicationStatus.CONNECTED.value
    )


# ==============================================================================
# 1. VALID TELEMETRY
# ==============================================================================
def test_valid_telemetry(validator, clean_frame):
    """Verifies that flawless telemetry produces an admissible DataQualityRecord."""
    res = validator.validate_telemetry(clean_frame)
    assert res.valid is True
    assert res.quality == TelemetryQuality.VALID.value
    assert len(res.errors) == 0

    dq = res.data_quality_record
    assert dq is not None
    assert dq.sensor_valid is True
    assert dq.voltage_valid is True
    assert dq.current_valid is True
    assert dq.temperature_valid is True
    assert dq.measurement_admissible is True
    assert dq.quality_state == DataQualityState.VALID.value
    assert dq.event_classification == EventClassification.NORMAL_OPERATION.value
    assert dq.validation_details["config_version"] == "2.0.0"


# ==============================================================================
# 2. NaN VOLTAGE
# ==============================================================================
def test_nan_voltage(validator, clean_frame):
    """Verifies that NaN in voltage is flagged as sensor invalid and inadmissible."""
    clean_frame.voltage_v = float("nan")
    res = validator.validate_telemetry(clean_frame)
    assert res.valid is False
    assert any("voltage_v" in f for f in res.rejected_fields)
    assert any("ERR_NUM_01" in err for err in res.errors)

    dq = res.data_quality_record
    assert dq.voltage_valid is False
    assert dq.sensor_valid is False
    assert dq.measurement_admissible is False
    assert dq.quality_state == DataQualityState.INVALID.value


# ==============================================================================
# 3. NaN CURRENT
# ==============================================================================
def test_nan_current(validator, clean_frame):
    """Verifies that NaN in current is flagged and rejects measurement admissibility."""
    clean_frame.current_a = float("nan")
    res = validator.validate_telemetry(clean_frame)
    assert res.valid is False
    assert any("current_a" in f for f in res.rejected_fields)

    dq = res.data_quality_record
    assert dq.current_valid is False
    assert dq.sensor_valid is False
    assert dq.measurement_admissible is False


# ==============================================================================
# 4. NaN TEMPERATURE
# ==============================================================================
def test_nan_temperature(validator, clean_frame):
    """Verifies that NaN in temperature rejects sensor validity."""
    clean_frame.temperature_c = float("nan")
    res = validator.validate_telemetry(clean_frame)
    assert res.valid is False
    assert any("temperature_c" in f for f in res.rejected_fields)

    dq = res.data_quality_record
    assert dq.temperature_valid is False
    assert dq.sensor_valid is False
    assert dq.measurement_admissible is False


# ==============================================================================
# 5. STALE TIMESTAMP
# ==============================================================================
def test_stale_timestamp(validator, clean_frame):
    """Verifies that telemetry older than max_stale_age_s is rejected."""
    now = time.time()
    clean_frame.timestamp = now - 5.0  # 5 seconds old, threshold is 2.0s
    res = validator.validate_telemetry(clean_frame, current_time=now)
    assert res.valid is False
    assert res.quality == TelemetryQuality.STALE.value
    assert any("ERR_TIME_01" in err for err in res.errors)

    dq = res.data_quality_record
    assert dq.stale_data is True
    assert dq.measurement_admissible is False
    assert ReasonCode.TELEMETRY_STALE in dq.reason_codes


# ==============================================================================
# 6. SEQUENCE GAP
# ==============================================================================
def test_sequence_gap(validator, clean_frame):
    """Verifies sequence jump detection and dropped frame tracking."""
    validator.reset_sequence_tracking()
    clean_frame.sequence_number = 10
    validator.validate_telemetry(clean_frame)

    # Now deliver sequence number 15 (gap of 4 dropped frames)
    gap_frame = copy.copy(clean_frame)
    gap_frame.sequence_number = 15
    res = validator.validate_telemetry(gap_frame)

    assert any("WARN_SEQ_02" in w for w in res.warnings)
    assert ReasonCode.SEQUENCE_GAP_DETECTED in res.data_quality_record.reason_codes


# ==============================================================================
# 7. DUPLICATE TIMESTAMP / SEQUENCE
# ==============================================================================
def test_duplicate_sequence(validator, clean_frame):
    """Verifies duplicate sequence reception is flagged."""
    validator.reset_sequence_tracking()
    clean_frame.sequence_number = 42
    validator.validate_telemetry(clean_frame)

    dup_frame = copy.copy(clean_frame)
    dup_frame.sequence_number = 42
    res = validator.validate_telemetry(dup_frame)

    assert any("WARN_SEQ_01" in w for w in res.warnings)
    assert ReasonCode.DUPLICATE_TIMESTAMP in res.data_quality_record.reason_codes


# ==============================================================================
# 8. CURRENT BELOW THRESHOLD
# ==============================================================================
def test_current_below_threshold(validator):
    """Verifies that a pulse with current below I_MIN is marked invalid."""
    pre_sample = {"voltage": 3.35, "current": 0.0, "timestamp": 0.0}
    pulse_samples = [
        {"voltage": 3.34, "current": 0.40, "t_rel": 0.00},
        {"voltage": 3.34, "current": 0.45, "t_rel": 0.10},
        {"voltage": 3.33, "current": 0.42, "t_rel": 0.20}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        required_i_min_a=1.0  # Requires 1.0A, but observed is ~0.42A
    )

    assert record.pulse_valid is False
    assert record.admissible_for_r0 is False
    assert record.admissible_for_chemistry is False
    assert record.current_margin_a < 0.0
    assert ReasonCode.CURRENT_FLOW_BELOW_MINIMUM in record.reason_codes
    assert ReasonCode.PULSE_INVALID in record.reason_codes


# ==============================================================================
# 9. ZERO-CURRENT PULSE
# ==============================================================================
def test_zero_current_pulse(validator):
    """Verifies that a commanded pulse with zero current flow is rejected."""
    pre_sample = {"voltage": 3.35, "current": 0.0}
    pulse_samples = [
        {"voltage": 3.349, "current": 0.001, "t_rel": 0.00},
        {"voltage": 3.348, "current": 0.000, "t_rel": 0.10},
        {"voltage": 3.349, "current": 0.000, "t_rel": 0.20}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        required_i_min_a=1.0
    )

    assert record.pulse_valid is False
    assert record.admissible_for_r0 is False
    assert record.mean_pulse_current_a < 0.01
    assert ReasonCode.CURRENT_FLOW_BELOW_MINIMUM in record.reason_codes


# ==============================================================================
# 10. CONTACTOR OPENED
# ==============================================================================
def test_contactor_opened(validator):
    """Verifies that contactor open condition during pulse triggers explicit fault."""
    pre_sample = {"voltage": 3.35, "current": 0.0}
    pulse_samples = [
        {"voltage": 3.35, "current": 0.0, "t_rel": 0.0},
        {"voltage": 3.35, "current": 0.0, "t_rel": 0.1}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        contactor_open=True
    )

    assert record.pulse_valid is False
    assert record.contactor_open is True
    assert ReasonCode.CONTACTOR_OPEN_FAULT in record.reason_codes


# ==============================================================================
# 11. HARDWARE TRIP
# ==============================================================================
def test_hardware_trip(validator):
    """Verifies that hardware protection trips classify event as HARDWARE_TRIP."""
    pre_sample = {"voltage": 3.75, "current": 0.0}
    pulse_samples = [
        {"voltage": 3.75, "current": 0.0, "t_rel": 0.0},
        {"voltage": 3.75, "current": 0.0, "t_rel": 0.1}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        hardware_tripped=True
    )

    assert record.pulse_valid is False
    assert record.hardware_tripped is True
    assert record.data_quality.event_classification == EventClassification.HARDWARE_TRIP.value
    assert ReasonCode.HARDWARE_TRIP_DURING_TEST in record.reason_codes


# ==============================================================================
# 12. SENSOR FAULT
# ==============================================================================
def test_sensor_fault(validator, clean_frame):
    """Verifies distinction between sensor fault and system events."""
    clean_frame.sensor_status["INA219"] = SensorHealthStatus.FAULT.value
    res = validator.validate_telemetry(clean_frame)

    assert res.valid is False
    assert res.quality == TelemetryQuality.SENSOR_FAULT.value
    assert res.data_quality_record.sensor_valid is False
    assert ReasonCode.SENSOR_FAULT in res.data_quality_record.reason_codes
    assert res.data_quality_record.event_classification == EventClassification.SENSOR_FAULT.value


# ==============================================================================
# 13. INVALID PRE-PULSE SAMPLE
# ==============================================================================
def test_invalid_pre_pulse_sample(validator):
    """Verifies that missing or corrupt pre-pulse resting voltage is rejected."""
    pulse_samples = [
        {"voltage": 3.30, "current": 5.0, "t_rel": 0.0},
        {"voltage": 3.28, "current": 5.0, "t_rel": 0.1}
    ]

    # Pre-pulse is None
    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=None,
        pulse_samples=pulse_samples
    )
    assert record.pulse_valid is False
    assert ReasonCode.MEASUREMENT_INVALID in record.reason_codes

    # Pre-pulse contains NaN
    record_nan = validator.validate_diagnostic_pulse(
        pre_pulse_sample={"voltage": float("nan")},
        pulse_samples=pulse_samples
    )
    assert record_nan.pulse_valid is False
    assert ReasonCode.MEASUREMENT_INVALID in record_nan.reason_codes


# ==============================================================================
# 14. INVALID POST-PULSE / TRANSIENT SAMPLE
# ==============================================================================
def test_invalid_pulse_sample_nan(validator):
    """Verifies that NaN inside pulse array triggers sensor fault reason."""
    pre_sample = {"voltage": 3.35, "current": 0.0}
    pulse_samples = [
        {"voltage": 3.30, "current": 5.0, "t_rel": 0.0},
        {"voltage": float("nan"), "current": 5.0, "t_rel": 0.1}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples
    )
    assert record.pulse_valid is False
    assert ReasonCode.SENSOR_FAULT in record.reason_codes


# ==============================================================================
# 15. INSUFFICIENT PULSE DURATION
# ==============================================================================
def test_insufficient_pulse_duration(validator):
    """Verifies rejection when pulse duration is below configured min_pulse_duration_s."""
    pre_sample = {"voltage": 3.35, "current": 0.0}
    # Samples span only 0.01 seconds (threshold is 0.05s)
    pulse_samples = [
        {"voltage": 3.30, "current": 5.0, "t_rel": 0.00},
        {"voltage": 3.29, "current": 5.0, "t_rel": 0.01}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        min_duration_s=0.05
    )
    assert record.pulse_valid is False
    assert ReasonCode.TRANSIENT_DURATION_INSUFFICIENT in record.reason_codes


# ==============================================================================
# 16. INVALID DELTA-I
# ==============================================================================
def test_invalid_delta_i(validator):
    """Verifies that delta_i below configured minimum is rejected."""
    pre_sample = {"voltage": 3.35, "current": 0.0}
    pulse_samples = [
        {"voltage": 3.34, "current": 0.10, "t_rel": 0.0},
        {"voltage": 3.34, "current": 0.10, "t_rel": 0.1}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        required_i_min_a=2.0
    )
    assert record.pulse_valid is False
    assert record.delta_i < 2.0
    assert ReasonCode.CURRENT_FLOW_BELOW_MINIMUM in record.reason_codes


# ==============================================================================
# 17. INVALID DELTA-V / SENSOR CORRUPTION
# ==============================================================================
def test_invalid_delta_v(validator):
    """Verifies that infinite voltage spike in transient is rejected."""
    pre_sample = {"voltage": 3.35, "current": 0.0}
    pulse_samples = [
        {"voltage": 3.30, "current": 5.0, "t_rel": 0.0},
        {"voltage": float("inf"), "current": 5.0, "t_rel": 0.1}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples
    )
    assert record.pulse_valid is False
    assert ReasonCode.SENSOR_FAULT in record.reason_codes


# ==============================================================================
# 18. VALID DIAGNOSTIC PULSE
# ==============================================================================
def test_valid_diagnostic_pulse(validator):
    """Verifies that a compliant physical pulse is certified as admissible."""
    pre_sample = {"voltage": 3.350, "current": 0.0}
    pulse_samples = [
        {"voltage": 3.330, "current": 10.0, "t_rel": 0.00},
        {"voltage": 3.328, "current": 10.0, "t_rel": 0.05},
        {"voltage": 3.320, "current": 10.0, "t_rel": 0.10}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        required_i_min_a=1.0,
        min_duration_s=0.05
    )

    assert record.pulse_valid is True
    assert record.admissible_for_r0 is True
    assert record.admissible_for_chemistry is True
    assert record.mean_pulse_current_a == 10.0
    assert record.current_margin_a == 9.0
    assert record.delta_v_ohmic > 0.0
    assert ReasonCode.PULSE_VALID in record.reason_codes


# ==============================================================================
# 19. INVALID PULSE REJECTED BY R0 ESTIMATOR
# ==============================================================================
def test_invalid_pulse_rejected_by_r0_estimator():
    """
    Verifies that when a pulse is invalid (e.g. zero current),
    r0_ohms is None and the Bayesian state estimator's R0 belief remains unchanged.
    """
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.85], cell_r0_mohm=[2.5])
    # Trip the hardware to prevent current flow
    hw.hardware_tripped = True
    hw.relay_enabled = False

    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    pulse_resp = meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=5.0)

    assert pulse_resp["pulse_valid"] is False
    assert pulse_resp["r0_ohms"] is None
    assert pulse_resp["admissible_for_r0"] is False

    # Simulate downstream estimator
    est = BayesianStateEstimator("SPECIMEN_01", prior_mu_r0=0.0025, prior_sigma_r0=0.001)
    orig_mu = est.mu_r0
    orig_sigma = est.sigma_r0

    # Downstream propagation rule: if r0_ohms is None or not admissible, DO NOT UPDATE
    if pulse_resp.get("pulse_valid") and pulse_resp.get("r0_ohms") is not None:
        est.update_r0_from_ohmic_jump(pulse_resp["r0_ohms"])

    # Confirm estimator was NOT corrupted by invalid event
    assert est.mu_r0 == orig_mu
    assert est.sigma_r0 == orig_sigma


# ==============================================================================
# 20. INVALID PULSE REJECTED BY CHEMISTRY ENGINE
# ==============================================================================
def test_invalid_pulse_rejected_by_chemistry_engine():
    """
    Verifies that an invalid pulse is NOT consumed by the chemistry engine.
    The posterior belief must remain completely identical.
    """
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.85], cell_r0_mohm=[2.5])
    hw.hardware_tripped = True

    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    chem_engine = ChemistryDisambiguationEngine()
    prior_post = {"LFP": 0.50, "NMC": 0.50, "UNKNOWN": 0.0}

    pulse_resp = meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=15.0)
    assert pulse_resp["pulse_valid"] is False
    assert pulse_resp["admissible_for_chemistry"] is False

    post = copy.copy(prior_post)
    if pulse_resp.get("pulse_valid") and pulse_resp.get("admissible_for_chemistry"):
        post = chem_engine.update_from_pulse_slope(pulse_resp["delta_v_total"], 10.0, 15.0, post)

    # Posterior must be untouched
    assert post == prior_post


# ==============================================================================
# 21. STRICT GROUND-TRUTH ISOLATION
# ==============================================================================
def test_ground_truth_isolation_data_quality():
    """
    Verifies that DataQualityRecord and TelemetryValidator do not reference
    or import ground_truth_registry.json.
    """
    import inspect
    import secondshift.interfaces.data_quality_schema as dqs
    import secondshift.interfaces.telemetry_validator as tv
    import secondshift.config.validation_config as vc

    for mod in [dqs, tv, vc]:
        src = inspect.getsource(mod)
        assert "ground_truth_registry.json" not in src
        assert "battery.soh" not in src


# ==============================================================================
# 22. DETERMINISTIC VALIDATION
# ==============================================================================
def test_deterministic_validation(validator, clean_frame):
    """Verifies that validating identical frames yields byte-for-byte identical records."""
    frame1 = copy.deepcopy(clean_frame)
    frame2 = copy.deepcopy(clean_frame)

    validator.reset_sequence_tracking()
    res1 = validator.validate_telemetry(frame1, current_time=1000.0)

    validator.reset_sequence_tracking()
    res2 = validator.validate_telemetry(frame2, current_time=1000.0)

    assert res1.valid == res2.valid
    assert res1.quality == res2.quality
    assert res1.data_quality_record.to_dict() == res2.data_quality_record.to_dict()


# ==============================================================================
# 23. ADVERSARIAL "FALSE PULSE" SCENARIO (Section 17)
# ==============================================================================
def test_adversarial_false_pulse_scenario():
    """
    Hostile Adversarial Scenario: 'FALSE PULSE'
    Scenario:
    1. Specimen is connected.
    2. Software commands a 10A diagnostic pulse.
    3. Hardware protection layer snaps open (e.g. comparator trips, contactor opens) before current flows.
    4. Telemetry reports I ≈ 0, but voltage may slightly drift or fluctuate.
    5. Software receives telemetry.

    Expected:
    - pulse_valid = FALSE
    - R0 estimate must NOT be generated (r0_ohms is None)
    - Chemistry engine must NOT update posterior
    - Closed loop runner must NOT conclude:
      'battery has high R0' or 'battery chemistry is X' or 'battery health is degraded'
    - Correct reason code: CURRENT_FLOW_BELOW_MINIMUM and/or HARDWARE_TRIP_DURING_TEST
    """
    # 1. Specimen connected, but simulate comparator trip right before pulse
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.90], cell_r0_mohm=[2.0])
    # Trip protection
    hw.hardware_tripped = True
    hw.trip_reason = "LM393_ANALOG_COMPARATOR_OVP_TRIP"
    hw.relay_enabled = False

    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    runner = ClosedLoopRunner(meas)

    # 2. Command pulse directly through measurement engine
    pulse_resp = meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=10.0)

    # 3. Assert measurement admissibility layer correctly catches false pulse
    assert pulse_resp["pulse_valid"] is False, "False pulse was incorrectly marked valid!"
    assert pulse_resp["r0_ohms"] is None, "R0 must NOT be computed when current did not flow!"
    assert pulse_resp["admissible_for_r0"] is False
    assert pulse_resp["admissible_for_chemistry"] is False
    assert pulse_resp["hardware_tripped"] is True
    assert (
        ReasonCode.HARDWARE_TRIP_DURING_TEST.value in pulse_resp["reason_codes"]
        or ReasonCode.CURRENT_FLOW_BELOW_MINIMUM.value in pulse_resp["reason_codes"]
    )

    # 4. Run closed-loop qualification on specimen with tripped hardware
    res = runner.run_qualification_pipeline(
        cell_id="SPECIMEN_FALSE_PULSE_01",
        prior_source="UNKNOWN",
        prior_soh=0.75,
        prior_r0_mohm=2.5
    )

    # Invariant: Must safely RETIRE/REJECT due to hardware trip, NOT fabricate degraded SOH/R0
    assert res["final_decision"] == "RETIRE"
    assert "HARDWARE_TRIP_DETECTED" in res["final_reason"]
    # Chemistry must remain UNKNOWN (never falsely classified as LFP or NMC)
    assert res["final_chemistry"] == "UNKNOWN"
    # R0 must remain prior (not inflated artificially to infinity or zero)
    assert res["final_r0_mohm"] == 2.5


# ==============================================================================
# 24. SENSOR VALIDITY SEPARATED FROM INFERENCE ADMISSIBILITY (Section 3)
# ==============================================================================
def test_sensor_validity_separated_from_inference_admissibility(validator):
    """
    Proves that SensorValidity and MeasurementAdmissibility are decoupled:
    A sensor can be 100% healthy, yet the measurement is completely inadmissible
    for diagnostic inference.

    Example:
    INA219 reports V = 7.4V, I = 0.01A.
    Sensor is healthy (sensor_valid = True).
    Pulse current did not flow (current_flow_valid = False).
    Therefore: pulse_valid = False, measurement_admissible = False.
    """
    pre_sample = {"voltage": 7.4, "current": 0.0}
    pulse_samples = [
        {"voltage": 7.40, "current": 0.01, "t_rel": 0.0},
        {"voltage": 7.40, "current": 0.01, "t_rel": 0.1}
    ]

    record = validator.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples,
        required_i_min_a=1.0
    )

    dq = record.data_quality
    # Mandated distinction:
    assert dq.sensor_valid is True, "Sensor itself is healthy"
    assert dq.current_flow_valid is False, "Current flow was not achieved"
    assert dq.pulse_valid is False, "Pulse is not valid"
    assert dq.measurement_admissible is False, "Measurement is NOT admissible for inference"
    assert dq.admissible_for_r0 is False
    assert dq.admissible_for_chemistry is False


# ==============================================================================
# 25. DATA QUALITY RECORD INVARIANTS
# ==============================================================================
def test_data_quality_record_invariants():
    """Verifies that logical invariant violations in DataQualityRecord are detected."""
    # 1. Invariant: If sensor_valid is False, measurement_admissible cannot be True
    invalid_record = DataQualityRecord(
        sensor_valid=False,
        measurement_admissible=True
    )
    errors = invalid_record.validate_invariants()
    assert any("sensor_valid is False" in e for e in errors)

    # 2. Invariant: If pulse_valid is True, current_flow_valid must be True
    invalid_pulse = DataQualityRecord(
        sensor_valid=True,
        pulse_valid=True,
        current_flow_valid=False,
        observed_current=0.1,
        configured_i_min=1.0
    )
    errors_pulse = invalid_pulse.validate_invariants()
    assert any("verified current flow" in e for e in errors_pulse)

    # 3. Clean record has zero invariant violations
    clean = DataQualityRecord(
        sensor_valid=True,
        current_flow_valid=True,
        pulse_valid=True,
        observed_current=5.0,
        configured_i_min=1.0,
        admissible_for_r0=True,
        measurement_admissible=True
    )
    assert len(clean.validate_invariants()) == 0


# ==============================================================================
# 26. VERSIONED CONFIGURATION EXTERNALIZATION
# ==============================================================================
def test_versioned_configuration_externalization():
    """
    Verifies that changing versioned configuration thresholds alters validation
    decisions dynamically without code changes, and records version tag.
    """
    config_v2 = MeasurementValidationConfig(
        config_version="2.0.0",
        i_min_pulse_a=5.0  # Require strict 5.0A
    )
    validator_v2 = TelemetryValidator(config=config_v2)

    pre_sample = {"voltage": 3.35, "current": 0.0}
    # Provide 3.0A pulse (valid under 1.0A default, but invalid under 5.0A config)
    pulse_samples = [
        {"voltage": 3.30, "current": 3.0, "t_rel": 0.0},
        {"voltage": 3.30, "current": 3.0, "t_rel": 0.1}
    ]

    record = validator_v2.validate_diagnostic_pulse(
        pre_pulse_sample=pre_sample,
        pulse_samples=pulse_samples
    )

    assert record.pulse_valid is False
    assert record.configured_i_min == 5.0
    assert record.mean_pulse_current_a == 3.0
    assert record.current_margin_a == -2.0
    assert record.details["config_version"] == "2.0.0"


# ==============================================================================
# 27. CORRECTION A REGRESSION TEST: INVALID PULSE DELTA_V IS NONE (NOT ZERO)
# ==============================================================================
def test_invalid_pulse_delta_v_is_none():
    """
    Regression Test for Phase 2 Correction A:
    Rule: UNKNOWN / INVALID != ZERO.
    When a diagnostic pulse is invalid (e.g. current did not flow or hardware tripped):
    - delta_v_total must be None (NOT 0.0)
    - delta_v_ohmic must be None (NOT 0.0)
    When a diagnostic pulse is valid:
    - delta_v_total must be float (e.g. delta_v_total >= 0.0)
    """
    hw = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.85], cell_r0_mohm=[2.5])
    # Case 1: Tripped hardware -> invalid pulse
    hw.hardware_tripped = True
    meas = HermesMeasurementEngine(hw, active_cell_idx=0)
    pulse_resp_invalid = meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=5.0)

    assert pulse_resp_invalid["pulse_valid"] is False
    assert pulse_resp_invalid["r0_ohms"] is None
    assert pulse_resp_invalid["delta_v_total"] is None, "Correction A violation: invalid delta_v_total must be None, not 0.0!"

    # Case 2: Clean untripped hardware -> valid pulse
    hw.reset_hardware_trip()
    hw.hardware_tripped = False
    hw.relay_enabled = True
    pulse_resp_valid = meas.measure_voltage_response(pulse_current_a=10.0, pulse_duration_s=5.0)

    assert pulse_resp_valid["pulse_valid"] is True
    assert pulse_resp_valid["delta_v_total"] is not None
    assert isinstance(pulse_resp_valid["delta_v_total"], float)
    assert pulse_resp_valid["delta_v_total"] >= 0.0
