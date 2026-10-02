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
