"""
Unit & Simulation Verification Suite for ESP32 Firmware Fault Recovery State Machine
Project: RMK REVOLT / SECONDShift Platform
System: NEXUS — Risk-Constrained Adaptive Second-Life EV Battery Qualification System

Covers tests:
- TEST-FR-01: Healthy IDLE remains IDLE.
- TEST-FR-02: IDLE -> FAULT on valid fault.
- TEST-FR-03: FAULT remains FAULT while fault persists.
- TEST-FR-04: FAULT recovers after fault clears and recovery criteria are satisfied.
- TEST-FR-05: One good sample does NOT prematurely recover if N samples are required.
- TEST-FR-06: Fault returns during recovery qualification -> resets and remains FAULT.
- TEST-FR-07: Recovering from FAULT does not turn MOSFET ON (Safe state invariant).
- TEST-FR-08: CLEAR cannot override an active fault.
- TEST-FR-09: Latched fault cannot automatically recover.
- TEST-FR-10: Recoverable fault can recover.
- TEST-FR-11: Sensor-invalid state prevents recovery.
- TEST-FR-12: Multiple faults are handled correctly.
- TEST-FR-13: Fault reason remains available after recovery (Auditability).
- TEST-FR-14: FAULT -> IDLE transition is logged.
- TEST-FR-15: Repeated fault/recovery cycles behave deterministically.
- REGRESSION: Verified fix for the exact bug reported in the prompt.
"""

import pytest
from typing import Dict, Any

from secondshift.hardware.fault_recovery_fsm import (
    ESP32FaultRecoveryFSM,
    SystemState,
)


@pytest.fixture
def fsm() -> ESP32FaultRecoveryFSM:
    """Fixture providing a freshly initialized ESP32 FSM in IDLE state."""
    return ESP32FaultRecoveryFSM(device_id="NEXUS-ESP32-TEST")


# ===========================================================================
# TEST-FR-01: Healthy IDLE remains IDLE
# ===========================================================================
def test_fr_01_healthy_idle_remains_idle(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-01: Under nominal sensor readings, IDLE state remains in IDLE and MOSFET remains OFF."""
    assert fsm.system_state == SystemState.STATE_IDLE
    assert fsm.mosfet_state is False

    for t in range(10):
        # Nominal 2S Li-ion pack: 7.4V, 0.0A, 25.0°C, sensor valid
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=t * 1000)
        assert fsm.system_state == SystemState.STATE_IDLE
        assert fsm.mosfet_state is False
        assert fsm.fault_reason == "NONE"


# ===========================================================================
# TEST-FR-02: IDLE -> FAULT on valid fault
# ===========================================================================
def test_fr_02_idle_to_fault_on_valid_fault(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-02: Confirmed fault threshold violation triggers transition to FAULT."""
    # Under-voltage trip requires 3 consecutive samples < 6.40V
    fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000)
    assert fsm.system_state == SystemState.STATE_IDLE  # Sample 1: debouncing
    assert fsm.undervoltage_count == 1

    fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=2000)
    assert fsm.system_state == SystemState.STATE_IDLE  # Sample 2: debouncing
    assert fsm.undervoltage_count == 2

    fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=3000)
    assert fsm.system_state == SystemState.STATE_FAULT # Sample 3: trip confirmed
    assert fsm.fault_reason == "UNDER_VOLTAGE"
    assert fsm.mosfet_state is False


# ===========================================================================
# TEST-FR-03: FAULT remains FAULT while fault persists
# ===========================================================================
def test_fr_03_fault_remains_fault_while_fault_persists(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-03: While physical fault persists, FSM never leaves FAULT."""
    fsm.enter_fault("UNDER_VOLTAGE", now_ms=1000)
    assert fsm.system_state == SystemState.STATE_FAULT

    for t in range(20):
        fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=2000 + t * 1000)
        assert fsm.system_state == SystemState.STATE_FAULT
        assert fsm.recovery_sample_count == 0
        assert fsm.mosfet_state is False


# ===========================================================================
# TEST-FR-04: FAULT recovers after fault clears and recovery criteria satisfied
# ===========================================================================
def test_fr_04_fault_recovers_after_criteria_satisfied(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-04: Satisfying N=5 consecutive healthy samples with hysteresis transitions FAULT -> IDLE."""
    fsm.enter_fault("UNDER_VOLTAGE", now_ms=1000)
    assert fsm.system_state == SystemState.STATE_FAULT

    # Healthy pack: 7.40V (well above hysteresis threshold 6.55V)
    for i in range(1, 5):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000 + i * 1000)
        assert fsm.system_state == SystemState.STATE_FAULT
        assert fsm.recovery_sample_count == i

    # 5th sample satisfies qualification
    fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=6000)
    assert fsm.system_state == SystemState.STATE_IDLE
    assert fsm.recovery_sample_count == 0
    assert fsm.fault_reason == "NONE"
    assert fsm.last_fault_reason == "UNDER_VOLTAGE"
    assert fsm.fault_recovered is True
    assert fsm.mosfet_state is False


# ===========================================================================
# TEST-FR-05: One good sample does NOT prematurely recover
# ===========================================================================
def test_fr_05_one_good_sample_does_not_prematurely_recover(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-05: A single good sample does not clear FAULT."""
    fsm.enter_fault("UNDER_VOLTAGE", now_ms=1000)
    fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=2000)

    assert fsm.system_state == SystemState.STATE_FAULT
    assert fsm.recovery_sample_count == 1
    assert fsm.fault_reason == "UNDER_VOLTAGE"


# ===========================================================================
# TEST-FR-06: Fault returns during recovery qualification
# ===========================================================================
def test_fr_06_fault_returns_during_recovery_resets_counter(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-06: If fault reoccurs during qualification, counter resets to 0 and state remains FAULT."""
    fsm.enter_fault("UNDER_VOLTAGE", now_ms=1000)

    # 3 healthy samples
    for i in range(1, 4):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000 + i * 1000)
        assert fsm.recovery_sample_count == i
        assert fsm.system_state == SystemState.STATE_FAULT

    # Voltage drops again (< 6.55V)
    fsm.step(voltage=6.30, current=0.0, temp=25.0, sensor_valid=True, now_ms=5000)
    assert fsm.system_state == SystemState.STATE_FAULT
    assert fsm.recovery_sample_count == 0  # Counter reset to 0!


# ===========================================================================
# TEST-FR-07: Recovering from FAULT does not turn MOSFET ON
# ===========================================================================
def test_fr_07_recovery_does_not_turn_mosfet_on(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-07: Recovery strictly restores SAFE IDLE; MOSFET must NEVER be turned ON."""
    fsm.enter_fault("OVER_CURRENT", now_ms=1000)
    assert fsm.mosfet_state is False

    # Complete recovery qualification
    for i in range(1, 6):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000 + i * 1000)

    assert fsm.system_state == SystemState.STATE_IDLE
    assert fsm.mosfet_state is False  # Load remains safe & de-energized!


# ===========================================================================
# TEST-FR-08: CLEAR cannot override an active fault
# ===========================================================================
def test_fr_08_clear_cannot_override_active_fault(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-08: Manual CLEAR command is rejected if physical fault condition persists."""
    fsm.enter_fault("OVER_TEMPERATURE", now_ms=1000)
    assert fsm.system_state == SystemState.STATE_FAULT

    # Physical temperature is 62.0°C (well above threshold)
    success = fsm.command("CLEAR", voltage=7.40, current=0.0, temp=62.0, sensor_valid=True, now_ms=2000)
    assert success is False
    assert fsm.system_state == SystemState.STATE_FAULT
    assert fsm.fault_reason == "OVER_TEMPERATURE"


# ===========================================================================
# TEST-FR-09: Latched fault cannot automatically recover
# ===========================================================================
def test_fr_09_latched_fault_cannot_auto_recover(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-09: Non-recoverable hardware fault remains in FAULT regardless of sensor readings."""
    fsm.enter_fault("INA219_NOT_DETECTED", now_ms=1000)
    assert fsm.is_fault_recoverable("INA219_NOT_DETECTED") is False

    for t in range(10):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=2000 + t * 1000)
        assert fsm.system_state == SystemState.STATE_FAULT
        assert fsm.recovery_sample_count == 0
        assert fsm.fault_reason == "INA219_NOT_DETECTED"


# ===========================================================================
# TEST-FR-10: Recoverable fault can recover
# ===========================================================================
def test_fr_10_recoverable_fault_can_recover(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-10: All classes in RECOVERABLE taxonomy successfully qualify and recover."""
    recoverable_reasons = ["UNDER_VOLTAGE", "OVER_VOLTAGE", "OVER_CURRENT", "OVER_TEMPERATURE", "SENSOR_INVALID"]
    for reason in recoverable_reasons:
        fsm.enter_fault(reason, now_ms=1000)
        assert fsm.is_fault_recoverable(reason) is True

        for i in range(1, 6):
            fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000 + i * 1000)

        assert fsm.system_state == SystemState.STATE_IDLE
        assert fsm.fault_reason == "NONE"
        assert fsm.last_fault_reason == reason
        assert fsm.mosfet_state is False


# ===========================================================================
# TEST-FR-11: Sensor-invalid state prevents recovery
# ===========================================================================
def test_fr_11_sensor_invalid_state_prevents_recovery(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-11: If sensor is invalid/corrupt, recovery qualification is blocked."""
    fsm.enter_fault("UNDER_VOLTAGE", now_ms=1000)

    # Sensors invalid (I2C bus disconnect or CRC error)
    for t in range(5):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=False, now_ms=2000 + t * 1000)
        assert fsm.system_state == SystemState.STATE_FAULT
        assert fsm.recovery_sample_count == 0


# ===========================================================================
# TEST-FR-12: Multiple faults are handled correctly
# ===========================================================================
def test_fr_12_multiple_faults_handled_correctly(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-12: If multiple faults exist simultaneously, recovery requires all to be clear."""
    fsm.enter_fault("UNDER_VOLTAGE", now_ms=1000)

    # Voltage clears (7.40V), but temperature is simultaneously too high (58.0°C > 55.0°C hysteresis limit)
    for t in range(5):
        fsm.step(voltage=7.40, current=0.0, temp=58.0, sensor_valid=True, now_ms=2000 + t * 1000)
        assert fsm.system_state == SystemState.STATE_FAULT
        assert fsm.recovery_sample_count == 0


# ===========================================================================
# TEST-FR-13: Fault reason remains available after recovery
# ===========================================================================
def test_fr_13_fault_reason_remains_available_after_recovery(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-13: After recovery to IDLE, last_fault_reason and fault_recovered retain historical audit trail."""
    fsm.enter_fault("OVER_CURRENT", now_ms=1000)
    for i in range(1, 6):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000 + i * 1000)

    assert fsm.system_state == SystemState.STATE_IDLE
    assert fsm.fault_reason == "NONE"
    assert fsm.last_fault_reason == "OVER_CURRENT"
    assert fsm.fault_recovered is True

    telemetry = fsm.build_telemetry(now_ms=7000)
    assert telemetry["state"] == "IDLE"
    assert telemetry["fault"] == "NONE"
    assert telemetry["last_fault"] == "OVER_CURRENT"
    assert telemetry["fault_recovered"] is True
    assert telemetry["hardware_fault"] is False
    assert telemetry["mosfet_state"] == "OFF"


# ===========================================================================
# TEST-FR-14: FAULT -> IDLE transition is logged
# ===========================================================================
def test_fr_14_transition_is_logged(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-14: Every state change generates an auditable structured event."""
    fsm.enter_fault("OVER_TEMPERATURE", now_ms=1000)
    for i in range(1, 6):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=1000 + i * 1000)

    events = [e for e in fsm.event_log if e["event"] == "STATE_TRANSITION"]
    assert len(events) >= 2
    # Event 1: IDLE -> FAULT
    assert events[0]["data"]["to"] == "FAULT"
    assert events[0]["data"]["reason"] == "OVER_TEMPERATURE"
    # Event 2: FAULT -> IDLE
    assert events[1]["data"]["from"] == "FAULT"
    assert events[1]["data"]["to"] == "IDLE"
    assert events[1]["data"]["prior_fault"] == "OVER_TEMPERATURE"
    assert events[1]["data"]["mosfet_state"] == "OFF"


# ===========================================================================
# TEST-FR-15: Repeated fault/recovery cycles behave deterministically
# ===========================================================================
def test_fr_15_repeated_fault_recovery_cycles_deterministic(fsm: ESP32FaultRecoveryFSM):
    """TEST-FR-15: Performing multiple fault/recovery cycles executes deterministically without drift."""
    for cycle in range(5):
        # 1. Start in IDLE
        assert fsm.system_state == SystemState.STATE_IDLE
        assert fsm.mosfet_state is False

        # 2. Trip on under-voltage (3 samples < 6.40V)
        fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=cycle * 10000 + 1000)
        fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=cycle * 10000 + 2000)
        fsm.step(voltage=6.20, current=0.0, temp=25.0, sensor_valid=True, now_ms=cycle * 10000 + 3000)
        assert fsm.system_state == SystemState.STATE_FAULT
        assert fsm.fault_reason == "UNDER_VOLTAGE"
        assert fsm.mosfet_state is False

        # 3. Qualify recovery (5 samples >= 6.55V)
        for i in range(1, 6):
            fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=cycle * 10000 + 3000 + i * 1000)

        # 4. Restored to safe IDLE
        assert fsm.system_state == SystemState.STATE_IDLE
        assert fsm.mosfet_state is False
        assert fsm.fault_reason == "NONE"
        assert fsm.last_fault_reason == "UNDER_VOLTAGE"


# ===========================================================================
# REGRESSION TEST: Exact reported defect
# ===========================================================================
def test_regression_idle_fault_disappears_recovers_to_idle_mosfet_off(fsm: ESP32FaultRecoveryFSM):
    """
    REGRESSION TEST:
    OBSERVED DEFECT:
    If the ESP32 system enters FAULT while currently in IDLE,
    and the physical fault condition subsequently disappears,
    the firmware previously remained in FAULT forever.

    EXPECTED BEHAVIOR WITH FIX:
    IDLE -> fault -> FAULT -> fault condition disappears ->
    recovery qualification (5 samples) -> IDLE with MOSFET OFF.
    """
    # 1. START: IDLE
    assert fsm.system_state == SystemState.STATE_IDLE
    assert fsm.mosfet_state is False

    # 2. ACTION: Trigger recoverable fault (over-current trip)
    fsm.step(voltage=7.40, current=3.00, temp=25.0, sensor_valid=True, now_ms=1000)
    fsm.step(voltage=7.40, current=3.00, temp=25.0, sensor_valid=True, now_ms=2000)
    fsm.step(voltage=7.40, current=3.00, temp=25.0, sensor_valid=True, now_ms=3000)

    # EXPECTED: FAULT
    assert fsm.system_state == SystemState.STATE_FAULT
    assert fsm.fault_reason == "OVER_CURRENT"
    assert fsm.mosfet_state is False

    # 3. ACTION: Remove fault condition (current drops to 0.0A, pack is nominal)
    # EXPECTED: Qualifies across 5 consecutive samples
    for i in range(1, 5):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=3000 + i * 1000)
        assert fsm.system_state == SystemState.STATE_FAULT  # Debouncing dwell time
        assert fsm.recovery_sample_count == i

    # 5th sample completes qualification
    fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=8000)

    # ASSERT: state != FAULT, state == IDLE
    assert fsm.system_state != SystemState.STATE_FAULT
    assert fsm.system_state == SystemState.STATE_IDLE

    # ASSERT: MOSFET == OFF
    assert fsm.mosfet_state is False

    # ASSERT: Fault history remains recorded
    assert fsm.last_fault_reason == "OVER_CURRENT"
    assert fsm.fault_recovered is True
    assert fsm.fault_reason == "NONE"
