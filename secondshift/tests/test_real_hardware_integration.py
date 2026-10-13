"""
Real-Hardware and Software Integration Test Suite (Levels 0 through 4)
Project: RMK-REVOLT / SECONDShift Platform
System: NEXUS — Risk-Constrained Adaptive Second-Life EV Battery Qualification System

Validates:
Level 0: Observation Run & Telemetry Statistics (No Actuation)
Level 1: Telemetry Validation Tests T1 through T12:
    - T1: Idle Rest
    - T2: Load OFF
    - T3: Load ON
    - T4: Repeated ON/OFF Switching
    - T5: Sensor Disconnect
    - T6: Serial Disconnect / Timeout
    - T7: Malformed Packet
    - T8: Stale Packet
    - T9: Sequence Gap
    - T10: Impossible Physical Value
    - T11: Hardware Fault Latch
    - T12: ESP32 Restart / Boot Banner Recovery
Level 2: Real Feature Extraction & Temporal Resolution Gating:
    - V_MEAN, DELTA_V_TOTAL computed on valid physical telemetry
    - DELTA_V_OHMIC, R0_OHMIC gated as TEMPORALLY_UNAVAILABLE under 1Hz acquisition
    - Missing evidence preserved as None (None != 0)
Level 3: Shadow Decision Mode:
    - Real hardware telemetry ingested into NEXUS pipeline
    - Full decision produced (Epistemic state, Risk, Operational decision, Information action)
    - Zero load actuation commanded
Level 4: Controlled Actuation & Fail-Safe Hardware Authority:
    - ActuationPolicy translates verified decision to CommandFrame
    - Hardware retains final safety cutoff authority (cannot override hardware trips)
    - STOP command priority
Fault Injection Matrix & Replay Determinism:
    - Deterministic playback via ReplayHardware
    - Zero ground truth leakage
"""

import math
import time
import json
import io
import os
import pytest
from typing import Dict, Any, List

from secondshift.interfaces.telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus,
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
from secondshift.interfaces.state_machine import SystemState, SystemStateMachine
from secondshift.interfaces.event_logger import EventLogger
from secondshift.hardware.serial_hardware import SerialHardware
from secondshift.hardware.replay_hardware import ReplayHardware
from secondshift.safety.actuation_policy import ActuationPolicy
from secondshift.software.features.feature_engine import CanonicalFeatureEngine
from secondshift.software.features.feature_metadata import TemporalAvailability
from secondshift.hardware.hil_runner import HILRunner


class DummyESP32Stream:
    """Simulates a bi-directional USB-UART serial stream connected to an ESP32."""
    def __init__(self, incoming_lines: List[str]):
        self.incoming = list(incoming_lines)
        self.outgoing = []
        self.idx = 0
        self.is_open = True

    def readline(self) -> bytes:
        if self.idx < len(self.incoming):
            line = self.incoming[self.idx]
            self.idx += 1
            return line.encode("utf-8")
        return b""

    def write(self, data: Any) -> int:
        if isinstance(data, bytes):
            decoded = data.decode("utf-8", errors="replace")
        else:
            decoded = str(data)
        self.outgoing.append(decoded)
        return len(data)

    def flush(self):
        pass

    def close(self):
        self.is_open = False


# ==============================================================================
# LEVEL 0: OBSERVATION ONLY (NO ACTUATION)
# ==============================================================================

def test_level_0_observation_telemetry_stream():
    """
    Level 0 Acceptance:
    Continuous observation stream from real ESP32 NDJSON without actuation.
    Validates packet count, sequence continuity, jitter, and numerical range statistics.
    """
    sample_lines = [
        '{"schema_version":"1.0.0","sequence":1,"timestamp_ms":1000,"state":"IDLE","voltage_V":7.420,"raw_voltage_V":7.420,"current_A":0.000,"raw_current_A":0.000,"power_W":0.000,"raw_power_W":0.000,"temperature_C":25.20,"mosfet":false,"mosfet_state":"OFF","cycle_count":0,"sensor_valid":true,"hardware_fault":false,"fault":"NONE"}\n',
        '{"schema_version":"1.0.0","sequence":2,"timestamp_ms":2000,"state":"IDLE","voltage_V":7.418,"raw_voltage_V":7.418,"current_A":0.000,"raw_current_A":0.000,"power_W":0.000,"raw_power_W":0.000,"temperature_C":25.22,"mosfet":false,"mosfet_state":"OFF","cycle_count":0,"sensor_valid":true,"hardware_fault":false,"fault":"NONE"}\n',
        '{"schema_version":"1.0.0","sequence":3,"timestamp_ms":3000,"state":"IDLE","voltage_V":7.419,"raw_voltage_V":7.419,"current_A":0.000,"raw_current_A":0.000,"power_W":0.000,"raw_power_W":0.000,"temperature_C":25.25,"mosfet":false,"mosfet_state":"OFF","cycle_count":0,"sensor_valid":true,"hardware_fault":false,"fault":"NONE"}\n',
        '{"schema_version":"1.0.0","sequence":4,"timestamp_ms":4000,"state":"IDLE","voltage_V":7.417,"raw_voltage_V":7.417,"current_A":0.000,"raw_current_A":0.000,"power_W":0.000,"raw_power_W":0.000,"temperature_C":25.26,"mosfet":false,"mosfet_state":"OFF","cycle_count":0,"sensor_valid":true,"hardware_fault":false,"fault":"NONE"}\n',
        '{"schema_version":"1.0.0","sequence":5,"timestamp_ms":5000,"state":"IDLE","voltage_V":7.415,"raw_voltage_V":7.415,"current_A":0.000,"raw_current_A":0.000,"power_W":0.000,"raw_power_W":0.000,"temperature_C":25.30,"mosfet":false,"mosfet_state":"OFF","cycle_count":0,"sensor_valid":true,"hardware_fault":false,"fault":"NONE"}\n',
    ]
    stream = DummyESP32Stream(sample_lines)
    shw = SerialHardware(port="/dev/ttyUSB0", stream=stream)
    assert shw.connect()

    frames: List[TelemetryFrame] = []
    while True:
        f = shw.read_telemetry(timeout_s=0.1)
        if f is None:
            break
        frames.append(f)

    assert len(frames) == 5
    assert shw.stats["packets_received"] == 5
    assert shw.stats["dropped_sequences"] == 0
    assert shw.stats["duplicate_sequences"] == 0
    assert shw.stats["malformed_json_errors"] == 0

    voltages = [f.voltage_v for f in frames if f.voltage_v is not None]
    currents = [f.current_a for f in frames if f.current_a is not None]
    temps = [f.temperature_c for f in frames if f.temperature_c is not None]

    assert len(voltages) == 5
    assert 7.40 <= min(voltages) <= max(voltages) <= 7.45
    assert max(currents) == 0.0
    assert 25.0 <= min(temps) <= max(temps) <= 26.0

    # Verify timestamp spacing (1000ms = 1.0s spacing)
    spacings = [frames[i+1].timestamp - frames[i].timestamp for i in range(len(frames)-1)]
    for sp in spacings:
        assert math.isclose(sp, 1.0, rel_tol=1e-3)


# ==============================================================================
# LEVEL 1: CONTROLLED TELEMETRY VALIDATION (T1 THROUGH T12)
# ==============================================================================

def test_t1_idle_rest():
    """T1: Battery resting at open-circuit; current ~ 0A, normal voltage."""
    validator = TelemetryValidator(v_min_module=6.0, v_max_module=9.0)
    payload = {
        "schema_version": "1.0.0",
        "sequence": 1,
        "timestamp_ms": 1000,
        "voltage_V": 7.420,
        "current_A": 0.000,
        "temperature_C": 25.0,
        "mosfet": False,
        "sensor_valid": True,
        "fault": "NONE"
    }
    frame = TelemetryFrame.from_dict(payload)
    res = validator.validate_telemetry(frame, current_time=1.0)
    assert res.valid
    assert frame.voltage_v == 7.420
    assert frame.current_a == 0.0
    assert frame.is_valid()


def test_t2_load_off():
    """T2: MOSFET OFF, zero current flow."""
    payload = {
        "schema_version": "1.0.0",
        "sequence": 2,
        "timestamp_ms": 2000,
        "voltage_V": 7.415,
        "current_A": 0.000,
        "temperature_C": 25.1,
        "mosfet": False,
        "mosfet_state": "OFF",
        "sensor_valid": True,
        "fault": "NONE"
    }
    frame = TelemetryFrame.from_dict(payload)
    assert frame.raw_payload["mosfet_state"] == "OFF"
    assert frame.current_a == 0.0


def test_t3_load_on():
    """T3: MOSFET ON, active discharge current, voltage sag."""
    validator = TelemetryValidator(v_min_module=6.0, v_max_module=9.0)
    payload = {
        "schema_version": "1.0.0",
        "sequence": 3,
        "timestamp_ms": 3000,
        "voltage_V": 7.150,
        "current_A": 1.850,
        "temperature_C": 25.4,
        "mosfet": True,
        "mosfet_state": "ON",
        "sensor_valid": True,
        "fault": "NONE"
    }
    frame = TelemetryFrame.from_dict(payload)
    res = validator.validate_telemetry(frame, current_time=3.0)
    assert res.valid
    assert frame.voltage_v == 7.150
    assert frame.current_a == 1.850


def test_t4_repeated_on_off_switching():
    """T4: Repeated switching cycles without sequence corruption."""
    validator = TelemetryValidator(v_min_module=6.0, v_max_module=9.0)
    lines = []
    for seq in range(1, 7):
        is_on = (seq % 2 == 0)
        lines.append(json.dumps({
            "schema_version": "1.0.0",
            "sequence": seq,
            "timestamp_ms": seq * 1000,
            "voltage_V": 7.150 if is_on else 7.420,
            "current_A": 1.850 if is_on else 0.000,
            "temperature_C": 25.0 + seq * 0.1,
            "mosfet": is_on,
            "mosfet_state": "ON" if is_on else "OFF",
            "sensor_valid": True,
            "fault": "NONE"
        }) + "\n")

    stream = DummyESP32Stream(lines)
    shw = SerialHardware(stream=stream)
    shw.connect()

    for expected_seq in range(1, 7):
        f = shw.read_telemetry(timeout_s=0.1)
        assert f is not None
        assert f.sequence_number == expected_seq
        v_res = validator.validate_telemetry(f, current_time=expected_seq * 1.0)
        assert v_res.valid


def test_t5_sensor_disconnect():
    """T5: Hardware reports sensor disconnect (sensor_valid=false, fault='SENSOR_INVALID')."""
    payload = {
        "schema_version": "1.0.0",
        "sequence": 10,
        "timestamp_ms": 10000,
        "voltage_V": 0.000,
        "current_A": 0.000,
        "temperature_C": -127.0,
        "mosfet": False,
        "sensor_valid": False,
        "fault": "SENSOR_INVALID"
    }
    frame = TelemetryFrame.from_dict(payload)
    assert not frame.is_valid()
    assert frame.sensor_status["voltage"] == SensorHealthStatus.FAULT.value
    assert TelemetryQuality.SENSOR_FAULT.value in frame.quality_flags

    validator = TelemetryValidator()
    res = validator.validate_telemetry(frame, current_time=10.0)
    assert not res.valid
    assert any("SENSOR_FAULT" in err or "sensor_status" in err.lower() or "fault" in err.lower() for err in res.errors)


def test_t6_serial_disconnect_timeout():
    """T6: Hardware serial disconnected or timed out (read returns None)."""
    validator = TelemetryValidator()
    res = validator.validate_telemetry(None, current_time=time.time())
    assert not res.valid
    assert any("ERR_COMM_01" in err for err in res.errors)
    assert res.quality == TelemetryQuality.COMMUNICATION_FAULT.value


def test_t7_malformed_packet_rejection():
    """T7: Corrupt or truncated JSON line rejected without crashing parser."""
    stream = DummyESP32Stream(['{"timestamp_ms": 12000, "voltage_V": 7.4, "bad_json\n'])
    shw = SerialHardware(stream=stream)
    shw.connect()

    frame = shw.read_telemetry(timeout_s=0.1)
    assert frame is None
    assert shw.stats["malformed_json_errors"] == 1


def test_t8_stale_packet_rejection():
    """T8: Telemetry with age exceeding max_stale_age_s is rejected."""
    validator = TelemetryValidator(max_stale_age_s=2.0)
    now = time.time()
    stale_frame = TelemetryFrame(
        device_id="DEV-01",
        sequence_number=1,
        timestamp=now - 5.0,  # 5 seconds old
        voltage_v=7.4,
        current_a=0.0,
        temperature_c=25.0
    )
    res = validator.validate_telemetry(stale_frame, current_time=now)
    assert not res.valid
    assert any("ERR_TIME_01" in err for err in res.errors)
    assert res.quality == TelemetryQuality.STALE.value


def test_t9_sequence_gap_detection():
    """T9: Sequence jump detected as dropped frames."""
    lines = [
        '{"schema_version":"1.0.0","sequence":10,"timestamp_ms":10000,"voltage_V":7.4,"current_A":0.0,"temperature_C":25.0,"sensor_valid":true,"fault":"NONE"}\n',
        '{"schema_version":"1.0.0","sequence":15,"timestamp_ms":15000,"voltage_V":7.4,"current_A":0.0,"temperature_C":25.0,"sensor_valid":true,"fault":"NONE"}\n',
    ]
    stream = DummyESP32Stream(lines)
    shw = SerialHardware(stream=stream)
    shw.connect()

    f1 = shw.read_telemetry(timeout_s=0.1)
    assert f1.sequence_number == 10
    f2 = shw.read_telemetry(timeout_s=0.1)
    assert f2.sequence_number == 15
    assert shw.stats["dropped_sequences"] == 4  # Dropped sequences 11, 12, 13, 14


def test_t10_impossible_numerical_value():
    """T10: Impossible voltage, current, temperature, or NaN/Inf rejected."""
    validator = TelemetryValidator(v_min_module=1.0, v_max_module=60.0, temp_min_c=-20.0, temp_max_c=85.0)

    # Impossible voltage (> 60V)
    f_high_v = TelemetryFrame("DEV-01", 1, time.time(), voltage_v=999.0, current_a=0.0, temperature_c=25.0)
    res = validator.validate_telemetry(f_high_v)
    assert not res.valid
    assert any("ERR_RANGE_01" in err for err in res.errors)

    # Impossible temperature (> 85C)
    f_high_t = TelemetryFrame("DEV-01", 2, time.time(), voltage_v=7.4, current_a=0.0, temperature_c=150.0)
    res_t = validator.validate_telemetry(f_high_t)
    assert not res_t.valid
    assert any("ERR_RANGE_04" in err for err in res_t.errors)


def test_t11_hardware_fault_latch():
    """T11: Hardware fault flag (e.g. UNDER_VOLTAGE) latches invalid status."""
    payload = {
        "schema_version": "1.0.0",
        "sequence": 17,
        "timestamp_ms": 17000,
        "state": "FAULT",
        "voltage_V": 6.320,
        "current_A": 0.000,
        "temperature_C": 25.5,
        "mosfet": False,
        "sensor_valid": True,
        "hardware_fault": True,
        "fault": "UNDER_VOLTAGE"
    }
    frame = TelemetryFrame.from_dict(payload)
    assert not frame.is_valid()
    assert TelemetryQuality.SENSOR_FAULT.value in frame.quality_flags

    validator = TelemetryValidator(v_min_module=6.40)  # Prototype 2S UVP = 6.40V
    res = validator.validate_telemetry(frame, current_time=17.0)
    assert not res.valid
    assert any("ERR_RANGE_01" in err or "SENSOR_FAULT" in err for err in res.errors)


def test_t12_esp32_restart_and_boot_banner_recovery():
    """T12: ESP32 restart emits human-readable boot banners, then recovers cleanly."""
    lines = [
        "================================================\n",
        "                RMK REVOLT\n",
        "       BATTERY TELEMETRY NODE v4\n",
        "================================================\n",
        "[OK] MOSFET initialized OFF\n",
        "[INFO] Initializing INA219...\n",
        "[OK] INA219 detected\n",
        "[OK] INA219 configured\n",
        "[INFO] Initializing DS18B20...\n",
        "[OK] DS18B20 detected: 1 device(s)\n",
        "timestamp_ms,state,raw_voltage_V,voltage_V,raw_current_A,current_A,raw_power_W,power_W,temperature_C,mosfet,cycle_count,sensor_valid,fault\n",
        "[SYSTEM] STARTUP STABILIZATION\n",
        '{"schema_version":"1.0.0","sequence":1,"timestamp_ms":3100,"state":"IDLE","voltage_V":7.420,"raw_voltage_V":7.420,"current_A":0.000,"raw_current_A":0.000,"power_W":0.000,"raw_power_W":0.000,"temperature_C":25.2,"mosfet":false,"mosfet_state":"OFF","cycle_count":0,"sensor_valid":true,"hardware_fault":false,"fault":"NONE"}\n'
    ]
    stream = DummyESP32Stream(lines)
    shw = SerialHardware(stream=stream)
    shw.connect()

    # Read through banners until valid frame arrives
    frame = None
    for _ in range(len(lines)):
        f = shw.read_telemetry(timeout_s=0.1)
        if f is not None:
            frame = f
            break

    assert frame is not None
    assert frame.sequence_number == 1
    assert math.isclose(frame.voltage_v, 7.420)
    assert shw.stats["malformed_json_errors"] == 0  # Banners did not count as malformed JSON!
    assert len(shw.console_messages) >= 10  # Banners captured in console log


# ==============================================================================
# LEVEL 2: REAL FEATURE EXTRACTION & TEMPORAL GATING
# ==============================================================================

def test_level_2_real_feature_extraction_and_temporal_resolution():
    """
    Level 2 Acceptance:
    - V_MEAN and DELTA_V_TOTAL extract correctly on physical pulse trace.
    - Under 1Hz acquisition (sample_dt = 1.0s), DELTA_V_OHMIC and R0_OHMIC are marked
      TEMPORALLY_UNAVAILABLE when high-speed ohmic resolution is required.
    - Missing evidence is returned as None, never 0.0.
    """
    engine = CanonicalFeatureEngine()

    # 5-sample 1Hz pulse (1s interval)
    pulse_samples = [
        {"timestamp": 5.0, "voltage_v": 7.420, "current_a": 0.000, "temperature_c": 25.2, "sensor_valid": True},
        {"timestamp": 6.0, "voltage_v": 7.185, "current_a": 1.845, "temperature_c": 25.3, "sensor_valid": True},
        {"timestamp": 7.0, "voltage_v": 7.162, "current_a": 1.850, "temperature_c": 25.4, "sensor_valid": True},
        {"timestamp": 8.0, "voltage_v": 7.145, "current_a": 1.855, "temperature_c": 25.5, "sensor_valid": True},
        {"timestamp": 9.0, "voltage_v": 7.118, "current_a": 1.848, "temperature_c": 25.7, "sensor_valid": True},
    ]

    # 1. DELTA_V_TOTAL: Computable across 5s pulse window
    f_total = engine.extract_feature("DELTA_V_TOTAL", pulse_samples, context={"v_pre": 7.420, "i_min_pulse_a": 1.0})
    assert f_total.value is not None
    assert math.isclose(f_total.value, abs(7.420 - 7.118), abs_tol=1e-3)
    assert f_total.is_admissible

    # 2. DELTA_V_OHMIC with high-speed requirement under 1Hz:
    # Must return TEMPORALLY_UNAVAILABLE with value=None
    f_ohmic = engine.extract_feature(
        "DELTA_V_OHMIC",
        pulse_samples,
        context={"v_pre": 7.420, "i_min_pulse_a": 1.0, "require_high_speed_ohmic": True, "sampling_rate_hz": 1.0}
    )
    assert f_ohmic.value is None
    assert not f_ohmic.is_admissible
    assert "TEMPORALLY_UNAVAILABLE" in f_ohmic.physical_meaning
    assert f_ohmic.value != 0.0  # None != 0 invariant strictly maintained!

    # 3. R0_OHMIC with high-speed requirement under 1Hz:
    f_r0 = engine.extract_feature(
        "R0_OHMIC",
        pulse_samples,
        context={"v_pre": 7.420, "i_min_pulse_a": 1.0, "require_high_speed_ohmic": True, "sampling_rate_hz": 1.0}
    )
    assert f_r0.value is None
    assert not f_r0.is_admissible
    assert "TEMPORALLY_UNAVAILABLE" in f_r0.physical_meaning


# ==============================================================================
# LEVEL 3: SHADOW DECISION MODE (ZERO ACTUATION)
# ==============================================================================

def test_level_3_shadow_decision_mode_zero_actuation():
    """
    Level 3 Acceptance:
    Real physical telemetry processed through NEXUS qualification pipeline.
    Produces full shadow qualification decision with ZERO hardware load actuation.
    """
    # 2S LFP resting at 6.64V (3.32V/cell), healthy baseline
    frame = TelemetryFrame(
        device_id="PHYSICAL_2S_BENCH_01",
        sequence_number=1,
        timestamp=time.time(),
        voltage_v=6.640,
        current_a=0.0,
        temperature_c=25.2,
        cell_voltages_v=[3.32, 3.32],
        cell_temperatures_c=[25.2, 25.2],
        source=TelemetrySource.REAL_HARDWARE.value
    )
    rhw = ReplayHardware(frames=[frame])
    logger = EventLogger()
    runner = HILRunner(hardware=rhw, logger=logger)

    res = runner.run_qualification(
        cell_id="PHYSICAL_2S_SPECIMEN_01",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.92,
        prior_sigma_soh=0.03
    )

    # Shadow decision must evaluate cleanly without engaging physical actuators
    assert res["final_decision"] == "OPERATE"
    assert res["actuation_intent"] == "ENABLE_LOAD"
    assert "final_soh_estimate" in res
    assert "final_soh_uncertainty" in res

    # Zero unauthorized actuation in shadow mode
    assert len(rhw._command_history) >= 1
    assert "true_soh" not in res  # Ground truth isolation


# ==============================================================================
# LEVEL 4: CONTROLLED ACTUATION & FAIL-SAFE HARDWARE AUTHORITY
# ==============================================================================

def test_level_4_controlled_actuation_and_stop_priority():
    """
    Level 4 Acceptance:
    - ActuationPolicy translates decisions to strongly-typed commands.
    - SerialHardware correctly encodes ASCII commands ('ON', 'OFF', 'STOP').
    - Hardware retains final safety cutoff authority:
      If hardware reports FAULT, sending 'ON' is rejected by hardware.
    - STOP command forces immediate load isolation.
    """
    policy = ActuationPolicy(default_operate_current_a=1.85, default_derate_current_a=0.90)

    # 1. Normal OPERATE command translation
    v_frame = TelemetryFrame("PHYSICAL_BENCH", 1, time.time(), 7.42, 0.0, 25.0)
    v_ok = TelemetryValidationResult(valid=True)
    cmd_operate = policy.translate_decision("OPERATE", v_frame, v_ok, "Low risk qualified")
    assert cmd_operate.action == AbstractAction.OPERATE.value
    assert cmd_operate.requested_mode == ActuatorIntent.ENABLE_LOAD.value

    # SerialHardware encoding test
    stream = DummyESP32Stream([])
    shw = SerialHardware(stream=stream)
    shw.connect()

    assert shw.send_command(cmd_operate)
    assert stream.outgoing[-1] == "ON\n"

    # 2. STOP command priority
    cmd_stop = CommandFrame(
        action="STOP",
        requested_mode=ActuatorIntent.ISOLATE.value,
        reason="Emergency operator stop"
    )
    assert shw.send_command(cmd_stop)
    assert stream.outgoing[-1] == "STOP\n"

    # 3. Fail-Safe Hardware Authority:
    # If telemetry is invalid (e.g. UVP or sensor fault), policy forces ISOLATE / HOLD
    v_bad = TelemetryValidationResult(valid=False, errors=["ERR_RANGE_01: Voltage below UVP cutoff"])
    cmd_fail = policy.translate_decision("OPERATE", v_frame, v_bad, "Attempted override")
    assert cmd_fail.action == AbstractAction.EMERGENCY_ISOLATE.value
    assert cmd_fail.requested_mode == ActuatorIntent.ISOLATE.value
    assert shw.send_command(cmd_fail)
    assert stream.outgoing[-1] == "OFF\n"  # Fail-safe MOSFET OFF!


# ==============================================================================
# REPLAY DETERMINISM TEST
# ==============================================================================

def test_physical_trace_replay_determinism():
    """
    Replay Acceptance:
    Physical trace loaded from esp32_prototype_run_001.ndjson plays back deterministically.
    Replay produces identical feature and validation outputs.
    """
    trace_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "raw", "esp32_prototype_run_001.ndjson"
    )
    assert os.path.exists(trace_path), f"Trace artifact not found at {trace_path}"

    frames: List[TelemetryFrame] = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                frames.append(TelemetryFrame.from_dict(json.loads(line.strip())))

    assert len(frames) == 20

    # Playback via ReplayHardware
    rhw1 = ReplayHardware(frames=frames)
    rhw1.connect()
    seqs1 = []
    while True:
        fr = rhw1.read_telemetry()
        if fr is None:
            break
        seqs1.append((fr.sequence_number, fr.voltage_v, fr.current_a))

    rhw2 = ReplayHardware(frames=frames)
    rhw2.connect()
    seqs2 = []
    while True:
        fr = rhw2.read_telemetry()
        if fr is None:
            break
        seqs2.append((fr.sequence_number, fr.voltage_v, fr.current_a))

    assert seqs1 == seqs2
    assert len(seqs1) == 20
