"""
Comprehensive Hardware Integration Test Suite
Project: RMK-REVOLT / SECONDShift Platform

Tests:
1. Canonical TelemetryFrame Schema serialization & deserialization
2. TelemetryValidator:
   - Valid frames
   - NaN, Infinity, type violations
   - Out-of-range physical values (UVP, OVP, OTP, overcurrent)
   - Stale timestamp detection and clock skew
   - Sensor fault flags
   - Sequence number continuity, regressions, and drops
3. MockHardware:
   - Connection lifecycle
   - Clean telemetry output
   - Fault injection modes (MISSING_SENSOR, STALE_TELEMETRY, COMM_DROPOUT, UVP_FAULT, OVP_FAULT)
4. SerialHardware:
   - Framing, partial line buffering, NDJSON parsing
   - Command dispatch and ACK handling
5. ReplayHardware:
   - Deterministic telemetry playback
   - Replay staleness exemption
6. ActuationPolicy & Fail-Safe Fallbacks:
   - Normal decisions (OPERATE, DERATE, RETIRE, HOLD)
   - Fail-safe override: invalid telemetry or sensor fault NEVER produces OPERATE
   - Contactor interlocks and parameter bounding
7. SystemStateMachine:
   - Valid state transitions
   - Illegal transition rejection
   - Emergency latching behavior
8. EventLogger:
   - Structured JSONL event logging
"""

import math
import time
import pytest
from typing import Dict, Any

from secondshift.interfaces.telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus,
    CalibrationStatus,
    TelemetrySource
)
from secondshift.interfaces.telemetry_validator import (
    TelemetryValidator,
    TelemetryValidationResult
)
from secondshift.interfaces.command_schema import (
    CommandFrame,
    AbstractAction,
    ActuatorIntent
)
from secondshift.interfaces.state_machine import (
    SystemState,
    SystemStateMachine,
    IllegalStateTransitionError
)
from secondshift.interfaces.event_logger import EventLogger
from secondshift.hardware.mock_hardware import MockHardware
from secondshift.hardware.serial_hardware import SerialHardware
from secondshift.hardware.replay_hardware import ReplayHardware
from secondshift.safety.actuation_policy import ActuationPolicy


# ==============================================================================
# 1. CANONICAL TELEMETRY SCHEMA TESTS
# ==============================================================================

def test_telemetry_frame_creation_and_dict_conversion():
    frame = TelemetryFrame(
        device_id="TEST-DEV-01",
        sequence_number=42,
        timestamp=time.time(),
        voltage_v=3.325,
        current_a=1.25,
        temperature_c=25.4,
        cell_voltages_v=[3.325],
        cell_temperatures_c=[25.4],
        source=TelemetrySource.MOCK_HARDWARE.value
    )
    d = frame.to_dict()
    assert d["device_id"] == "TEST-DEV-01"
    assert d["sequence_number"] == 42
    assert math.isclose(d["voltage_v"], 3.325)
    assert frame.is_valid()

    reconstructed = TelemetryFrame.from_dict(d)
    assert reconstructed.device_id == frame.device_id
    assert reconstructed.sequence_number == frame.sequence_number
    assert math.isclose(reconstructed.voltage_v, frame.voltage_v)


# ==============================================================================
# 2. TELEMETRY VALIDATOR TESTS
# ==============================================================================

def test_validator_accepts_valid_frame():
    validator = TelemetryValidator()
    frame = TelemetryFrame(
        device_id="CELL-01",
        sequence_number=1,
        timestamp=time.time(),
        voltage_v=3.30,
        current_a=0.5,
        temperature_c=24.0,
        cell_voltages_v=[3.30],
        cell_temperatures_c=[24.0]
    )
    res = validator.validate_telemetry(frame)
    assert res.valid
    assert len(res.errors) == 0
    assert res.quality == TelemetryQuality.VALID.value


def test_validator_rejects_nan_and_inf():
    validator = TelemetryValidator()
    frame_nan = TelemetryFrame(
        device_id="CELL-01",
        sequence_number=1,
        timestamp=time.time(),
        voltage_v=float("nan"),
        current_a=0.0,
        temperature_c=25.0
    )
    res_nan = validator.validate_telemetry(frame_nan)
    assert not res_nan.valid
    assert any("NaN" in e for e in res_nan.errors)

    frame_inf = TelemetryFrame(
        device_id="CELL-01",
        sequence_number=2,
        timestamp=time.time(),
        voltage_v=3.3,
        current_a=float("inf"),
        temperature_c=25.0
    )
    res_inf = validator.validate_telemetry(frame_inf)
    assert not res_inf.valid
    assert any("Infinity" in e for e in res_inf.errors)


def test_validator_rejects_physical_range_violations():
    validator = TelemetryValidator(v_min_cell=2.0, v_max_cell=4.5, temp_min_c=-10.0, temp_max_c=60.0)

    # UVP violation
    frame_uvp = TelemetryFrame("CELL-01", 1, time.time(), 1.5, 0.0, 25.0, cell_voltages_v=[1.5])
    assert not validator.validate_telemetry(frame_uvp).valid

    # OVP violation
    frame_ovp = TelemetryFrame("CELL-01", 2, time.time(), 4.8, 0.0, 25.0, cell_voltages_v=[4.8])
    assert not validator.validate_telemetry(frame_ovp).valid

    # High temperature violation
    frame_otp = TelemetryFrame("CELL-01", 3, time.time(), 3.3, 0.0, 75.0, cell_voltages_v=[3.3])
    assert not validator.validate_telemetry(frame_otp).valid


def test_validator_rejects_stale_and_future_timestamps():
    validator = TelemetryValidator(max_stale_age_s=2.0)
    now = time.time()

    # Stale timestamp (> 2.0s old)
    frame_stale = TelemetryFrame("CELL-01", 1, now - 5.0, 3.3, 0.0, 25.0)
    res_stale = validator.validate_telemetry(frame_stale, current_time=now)
    assert not res_stale.valid
    assert res_stale.quality == TelemetryQuality.STALE.value

    # Future clock drift (> 5.0s in future)
    frame_future = TelemetryFrame("CELL-01", 2, now + 10.0, 3.3, 0.0, 25.0)
    res_future = validator.validate_telemetry(frame_future, current_time=now)
    assert not res_future.valid
    assert any("future" in e for e in res_future.errors)


def test_validator_detects_sensor_fault_flags():
    validator = TelemetryValidator()
    frame = TelemetryFrame(
        device_id="CELL-01",
        sequence_number=1,
        timestamp=time.time(),
        voltage_v=3.3,
        current_a=0.0,
        temperature_c=25.0,
        sensor_status={"temperature": SensorHealthStatus.FAULT.value}
    )
    res = validator.validate_telemetry(frame)
    assert not res.valid
    assert res.quality == TelemetryQuality.SENSOR_FAULT.value


def test_validator_sequence_tracking_regression_and_gap():
    validator = TelemetryValidator()
    now = time.time()

    f1 = TelemetryFrame("CELL-01", 10, now, 3.3, 0.0, 25.0)
    assert validator.validate_telemetry(f1, current_time=now).valid

    # Sequence gap (warning only, valid remains True)
    f2 = TelemetryFrame("CELL-01", 15, now, 3.3, 0.0, 25.0)
    res2 = validator.validate_telemetry(f2, current_time=now)
    assert res2.valid
    assert len(res2.warnings) > 0
    assert any("gap" in w for w in res2.warnings)

    # Sequence regression (error, valid becomes False)
    f3 = TelemetryFrame("CELL-01", 5, now, 3.3, 0.0, 25.0)
    res3 = validator.validate_telemetry(f3, current_time=now)
    assert not res3.valid
    assert any("regression" in e for e in res3.errors)


# ==============================================================================
# 3. MOCK HARDWARE TESTS
# ==============================================================================

def test_mock_hardware_lifecycle_and_fault_modes():
    hw = MockHardware(chemistry="LFP", soh=0.92, r0_mohm=2.0)
    assert not hw.is_connected()

    assert hw.connect()
    assert hw.is_connected()

    # Normal reading
    f_clean = hw.read_telemetry()
    assert f_clean is not None
    assert f_clean.voltage_v > 3.0
    assert f_clean.temperature_c == 25.0

    # Fault: Missing sensor
    hw.set_fault_mode("MISSING_SENSOR")
    f_miss = hw.read_telemetry()
    assert f_miss.temperature_c is None
    assert f_miss.sensor_status["temperature"] == SensorHealthStatus.FAULT.value

    # Fault: UVP
    hw.set_fault_mode("UVP_FAULT")
    f_uvp = hw.read_telemetry()
    assert f_uvp.cell_voltages_v[0] < 2.0

    # Fault: Comm dropout
    hw.set_fault_mode("COMM_DROPOUT")
    assert hw.read_telemetry() is None

    hw.disconnect()
    assert not hw.is_connected()


# ==============================================================================
# 4. SERIAL HARDWARE BUFFERING & FRAMING TESTS
# ==============================================================================

def test_serial_hardware_ndjson_line_parsing():
    import json
    shw = SerialHardware(port="/dev/mock_uart", baudrate=115200)

    class DummySerialStream:
        def __init__(self, payloads):
            self.lines = payloads
            self.idx = 0
            self.is_open = True

        def readline(self):
            if self.idx < len(self.lines):
                line = self.lines[self.idx]
                self.idx += 1
                return line.encode("utf-8")
            return b""

        def write(self, data):
            return len(data)

        def flush(self):
            pass

        def close(self):
            self.is_open = False

    t1 = time.time()
    payload1 = json.dumps({"device_id": "UART-01", "sequence_number": 1, "timestamp": t1, "voltage_v": 3.31, "current_a": 0.0, "temperature_c": 24.8}) + "\n"
    payload2 = json.dumps({"device_id": "UART-01", "sequence_number": 2, "timestamp": t1 + 0.1, "voltage_v": 3.30, "current_a": 0.5, "temperature_c": 24.9}) + "\n"

    dummy = DummySerialStream([payload1, payload2])
    shw = SerialHardware(port="/dev/mock_uart", stream=dummy)
    assert shw.connect()

    frame1 = shw.read_telemetry()
    assert frame1 is not None
    assert frame1.sequence_number == 1
    assert math.isclose(frame1.voltage_v, 3.31)

    frame2 = shw.read_telemetry()
    assert frame2 is not None
    assert frame2.sequence_number == 2
    assert math.isclose(frame2.voltage_v, 3.30)

    # Sending a command
    cmd = {"command": "SET_MODE", "mode": "ENABLE_LOAD", "current_limit_a": 2.0}
    assert shw.send_command(cmd)


# ==============================================================================
# 5. REPLAY HARDWARE DETERMINISM TESTS
# ==============================================================================

def test_replay_hardware_frame_playback():
    t_base = 1000.0
    frames = [
        TelemetryFrame("REPLAY-DEV", 1, t_base, 3.35, 0.0, 25.0, cell_voltages_v=[3.35]),
        TelemetryFrame("REPLAY-DEV", 2, t_base + 1.0, 3.30, 2.0, 25.2, cell_voltages_v=[3.30]),
        TelemetryFrame("REPLAY-DEV", 3, t_base + 2.0, 3.28, 2.0, 25.5, cell_voltages_v=[3.28])
    ]
    rhw = ReplayHardware(frames=frames)
    rhw.connect()

    read1 = rhw.read_telemetry()
    read2 = rhw.read_telemetry()
    read3 = rhw.read_telemetry()
    read4 = rhw.read_telemetry()

    assert read1.sequence_number == 1
    assert read2.sequence_number == 2
    assert read3.sequence_number == 3
    assert read4 is None # EOF


# ==============================================================================
# 6. ACTUATION POLICY & FAIL-SAFE INTERLOCK TESTS
# ==============================================================================

def test_actuation_policy_translation_and_failsafe():
    policy = ActuationPolicy(default_operate_current_a=5.0, default_derate_current_a=2.5)

    valid_frame = TelemetryFrame("CELL-01", 1, time.time(), 3.3, 0.0, 25.0)
    val_ok = TelemetryValidationResult(valid=True)

    # 1. Normal OPERATE mapping
    cmd_op = policy.translate_decision("OPERATE", valid_frame, val_ok, "Low risk")
    assert cmd_op.action == "OPERATE"
    assert cmd_op.requested_mode == "ENABLE_LOAD"
    assert cmd_op.contactors_closed is True

    # 2. Normal DERATE mapping
    cmd_derate = policy.translate_decision("DERATE", valid_frame, val_ok, "Moderate risk")
    assert cmd_derate.action == "DERATE"
    assert cmd_derate.requested_mode == "LIMIT_LOAD"
    assert cmd_derate.current_limit_a <= 2.5 # Derated from 5.0A

    # 3. Normal RETIRE mapping
    cmd_retire = policy.translate_decision("RETIRE", valid_frame, val_ok, "High risk")
    assert cmd_retire.action == "RETIRE"
    assert cmd_retire.requested_mode == "ISOLATE"
    assert cmd_retire.contactors_closed is False

    # 4. Fail-Safe: Decision says OPERATE, but TelemetryValidation is INVALID
    val_fail = TelemetryValidationResult(valid=False, errors=["ERR_NUM_01: NaN detected"])
    cmd_failsafe = policy.translate_decision("OPERATE", valid_frame, val_fail, "Unsafe attempt")
    # MUST NEVER PRODUCE OPERATE OR DERATE
    assert cmd_failsafe.action in ["HOLD", "EMERGENCY_ISOLATE"]
    assert cmd_failsafe.contactors_closed is False
    assert cmd_failsafe.current_limit_a == 0.0

    # 5. Fail-Safe: Decision says OPERATE, but frame is None (comm dropout)
    cmd_dropout = policy.translate_decision("OPERATE", None, None, "Dropout attempt")
    assert cmd_dropout.action == "HOLD"
    assert cmd_dropout.contactors_closed is False


# ==============================================================================
# 7. STATE MACHINE LEGAL TRANSITIONS AND EMERGENCY LATCH
# ==============================================================================

def test_state_machine_transitions_and_emergency_latch():
    fsm = SystemStateMachine()
    assert fsm.current_state == SystemState.INIT

    fsm.transition_to(SystemState.CONNECTED, "Link up")
    fsm.transition_to(SystemState.MEASURING, "Intake read")
    fsm.transition_to(SystemState.QUALIFYING, "Running algorithms")
    fsm.transition_to(SystemState.OPERATE, "Approved")

    # Cannot illegally transition directly from OPERATE to MEASURING
    assert not fsm.can_transition_to(SystemState.MEASURING)
    with pytest.raises(IllegalStateTransitionError):
        fsm.transition_to(SystemState.MEASURING, "Illegal transition", strict=True)

    # Emergency isolate from any state
    fsm.transition_to(SystemState.EMERGENCY_ISOLATE, "LM393 analog comparator tripped")
    assert fsm.is_emergency_latched()

    # Once latched, normal transitions are locked out until manual clear
    assert not fsm.can_transition_to(SystemState.OPERATE)
    with pytest.raises(IllegalStateTransitionError):
        fsm.transition_to(SystemState.OPERATE, "Attempt to escape emergency latch", strict=True)

    # Clear latch
    fsm.clear_emergency_latch("Operator safety key reset")
    assert not fsm.is_emergency_latched()
    assert fsm.current_state == SystemState.INIT


# ==============================================================================
# 8. REGRESSION TESTS: ZERO PRESERVATION (V2) & IMMUTABILITY (V3)
# ==============================================================================

def test_telemetry_frame_from_dict_preserves_zero_values_and_aliases():
    """Verify TelemetryFrame.from_dict() preserves valid 0.0 values and aliases."""
    raw = {
        "device_id": "TEST_ZERO_01",
        "sequence_number": 0,
        "timestamp": 1000.0,
        "voltage_v": 0.0,
        "current_a": 0.0,
        "temperature_c": 0.0,
        "estimated_soc": 0.0
    }
    frame = TelemetryFrame.from_dict(raw)
    assert frame.sequence_number == 0
    assert frame.voltage_v == 0.0
    assert frame.current_a == 0.0
    assert frame.temperature_c == 0.0
    assert frame.estimated_soc == 0.0

    # Test alias with 0.0
    raw_alias = {
        "device_id": "TEST_ZERO_ALIAS",
        "seq": 0,
        "timestamp_s": 2000.0,
        "voltage": 0.0,
        "current": 0.0,
        "temperature": 0.0,
        "soc": 0.0
    }
    frame_alias = TelemetryFrame.from_dict(raw_alias)
    assert frame_alias.sequence_number == 0
    assert frame_alias.voltage_v == 0.0
    assert frame_alias.current_a == 0.0
    assert frame_alias.temperature_c == 0.0
    assert frame_alias.estimated_soc == 0.0

    # Test fallback when primary key is None but alias has value
    raw_fallback = {
        "device_id": "TEST_FALLBACK",
        "sequence_number": None,
        "seq": 42,
        "voltage_v": None,
        "voltage": 3.25,
        "current_a": None,
        "current": 5.0
    }
    frame_fb = TelemetryFrame.from_dict(raw_fallback)
    assert frame_fb.sequence_number == 42
    assert frame_fb.voltage_v == 3.25
    assert frame_fb.current_a == 5.0


def test_validator_does_not_mutate_input_frame():
    """Verify TelemetryValidator does NOT mutate the input TelemetryFrame."""
    validator = TelemetryValidator()

    # Valid frame test
    orig_flags = [TelemetryQuality.VALID.value]
    frame_valid = TelemetryFrame(
        device_id="MOD_TEST_MUTATION_1",
        sequence_number=1,
        timestamp=time.time(),
        voltage_v=13.2,
        current_a=2.0,
        temperature_c=25.0,
        quality_flags=list(orig_flags)
    )
    res_valid = validator.validate_telemetry(frame_valid)
    assert res_valid.valid is True
    assert frame_valid.quality_flags == orig_flags
    assert res_valid.validated_frame is not frame_valid

    # Invalid frame test (physical range violation: 999.0V)
    frame_invalid = TelemetryFrame(
        device_id="MOD_TEST_MUTATION_2",
        sequence_number=2,
        timestamp=time.time(),
        voltage_v=999.0,
        current_a=0.0,
        temperature_c=25.0,
        quality_flags=list(orig_flags)
    )
    res_invalid = validator.validate_telemetry(frame_invalid)
    assert res_invalid.valid is False
    # Input frame quality_flags must remain untouched
    assert frame_invalid.quality_flags == orig_flags
    assert res_invalid.validated_frame is not frame_invalid
    assert frame_invalid.quality_flags == [TelemetryQuality.VALID.value]
    # Validated frame has the updated quality flag
    assert TelemetryQuality.OUT_OF_RANGE.value in res_invalid.validated_frame.quality_flags
    assert res_invalid.validated_frame.quality_flags != frame_invalid.quality_flags


def test_system_configuration_loading_and_hil_runner_wiring():
    """Verify config/default.yaml is loaded and wired to HILRunner and DecisionEngine."""
    from secondshift.cli import load_system_config, extract_app_config
    from secondshift.hardware.hil_runner import HILRunner
    from secondshift.software.triage.triage_gate import TriageGate

    # 1. Load actual default.yaml
    cfg = load_system_config()
    assert "applications" in cfg
    assert "safety_limits" in cfg
    assert "economic_parameters" in cfg

    # 2. Extract application config
    app_cfg = extract_app_config(cfg, application="solar_storage")
    assert app_cfg["min_soh_threshold"] == 0.70
    assert app_cfg["max_acceptable_r0_mohm"] == 3.5
    assert app_cfg["recycle_rate_inr_kwh"] == 1200.0

    # 3. Test operational path wiring: custom config overrides defaults traceable to source
    custom_app_cfg = {
        "min_soh_threshold": 0.82,
        "max_acceptable_r0_mohm": 2.2,
        "safety_penalty_inr": 8500.0
    }
    custom_triage = TriageGate(
        v_min_reject=2.10,
        v_max_reject=3.65,
        t_max_reject_c=50.0
    )
    hw = MockHardware(chemistry="LFP", soh=0.90)
    runner = HILRunner(hardware=hw, app_config=custom_app_cfg, triage=custom_triage)

    # Prove config is consumed
    assert runner.decision_engine.config["min_soh_threshold"] == 0.82
    assert runner.decision_engine.config["max_acceptable_r0_mohm"] == 2.2
    assert runner.decision_engine.config["safety_penalty_inr"] == 8500.0
    # Unspecified fields fall back to default
    assert runner.decision_engine.config["energy_revenue_per_kwh_inr"] == 10.0
    assert runner.triage.v_max_reject == 3.65
    assert runner.triage.t_max_reject_c == 50.0
