"""
Deterministic State Machine & Fault Recovery Simulator for ESP32 Firmware
Project: RMK REVOLT / SECONDShift Platform
System: NEXUS — Risk-Constrained Adaptive Second-Life EV Battery Qualification System

Directly mirrors the physical C++ state machine in ESP32_CODE/sketch_oct5a/sketch_oct5a.ino:
- Safe fault detection, latching, and recovery qualification.
- Debounced confirmation counts for entering fault.
- Multi-sample dwell time and hysteresis for recovery.
- Strict functional safety property: FAULT recovery NEVER enables MOSFET actuation.
- Preservation of historical fault telemetry for auditability.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
import time


class SystemState(str, Enum):
    STATE_IDLE = "IDLE"
    STATE_RUNNING = "RUNNING"
    STATE_COOLDOWN = "COOLDOWN"
    STATE_FAULT = "FAULT"


class ESP32FaultRecoveryFSM:
    """
    Deterministic Python model of the NEXUS ESP32 battery telemetry &
    load control supervisor firmware state machine.
    """

    # Safety limits (Trip thresholds)
    BATTERY_UNDERVOLTAGE: float = 6.40
    BATTERY_OVERVOLTAGE: float = 8.50
    MAX_TEMPERATURE_C: float = 60.0
    MAX_CURRENT_A: float = 2.50

    # Recovery thresholds with hysteresis
    BATTERY_UNDERVOLTAGE_RECOVERY: float = 6.55  # 150 mV hysteresis
    BATTERY_OVERVOLTAGE_RECOVERY: float = 8.35   # 150 mV hysteresis
    MAX_TEMPERATURE_RECOVERY_C: float = 55.0   # 5.0 °C hysteresis
    MAX_CURRENT_RECOVERY_A: float = 0.10       # Load must be de-energized
    RECOVERY_CONFIRM_COUNT: int = 5            # 5 consecutive valid samples

    # Confirmation counts
    UV_CONFIRM_COUNT: int = 3
    OV_CONFIRM_COUNT: int = 3
    OC_CONFIRM_COUNT: int = 3
    OT_CONFIRM_COUNT: int = 3
    SENSOR_INVALID_CONFIRM_COUNT: int = 3

    # Load test timing (ms)
    LOAD_ON_TIME_MS: int = 5000
    LOAD_OFF_TIME_MS: int = 3000

    def __init__(self, device_id: str = "NEXUS-ESP32-01"):
        self.device_id: str = device_id

        # State machine
        self.system_state: SystemState = SystemState.STATE_IDLE
        self.mosfet_state: bool = False
        self.sensor_valid: bool = True
        self.fault_sensor: bool = False

        # Fault tracking & audit history
        self.fault_reason: str = "NONE"
        self.last_fault_reason: str = "NONE"
        self.fault_recovered: bool = False
        self.fault_entry_time_ms: float = 0.0
        self.fault_clear_time_ms: float = 0.0
        self.recovery_sample_count: int = 0

        # Trip counters
        self.undervoltage_count: int = 0
        self.overvoltage_count: int = 0
        self.overcurrent_count: int = 0
        self.overtemp_count: int = 0
        self.sensor_invalid_count: int = 0

        # Timers & cycles
        self.state_start_time_ms: float = 0.0
        self.test_cycle_count: int = 0
        self.telemetry_sequence: int = 0

        # Accepted measurements
        self.battery_voltage: float = 7.40
        self.current_a: float = 0.0
        self.temperature_c: float = 25.0

        # Audit event ledger
        self.event_log: List[Dict[str, Any]] = []

    def log_event(self, event_type: str, data: Dict[str, Any]):
        entry = {
            "event": event_type,
            "timestamp": time.time(),
            "state": self.system_state.value,
            "mosfet": self.mosfet_state,
            "data": data,
        }
        self.event_log.append(entry)

    def set_mosfet(self, state: bool):
        """Hardware actuator control with safety barrier."""
        if state and self.system_state == SystemState.STATE_FAULT:
            # Safety invariant: Cannot turn MOSFET ON during FAULT
            self.mosfet_state = False
            self.log_event("ACTUATION_BLOCKED_FAULT", {"attempted": True})
            return
        self.mosfet_state = state

    @classmethod
    def is_fault_recoverable(cls, reason: str) -> bool:
        """
        Derives recoverable vs latched taxonomy:
        Recoverable: transient electrical/thermal/sensor anomalies.
        Latched: physical absent hardware, comparator trips, emergency stops.
        """
        recoverable_set = {
            "UNDER_VOLTAGE",
            "OVER_VOLTAGE",
            "OVER_CURRENT",
            "OVER_TEMPERATURE",
            "SENSOR_INVALID",
        }
        return reason in recoverable_set

    def is_physical_condition_healthy(
        self,
        voltage: float,
        current: float,
        temp: float,
        sensor_valid: bool = True
    ) -> bool:
        """Evaluates whether instantaneous sensor measurements satisfy recovery hysteresis."""
        if not sensor_valid or self.fault_sensor:
            return False
        if voltage < self.BATTERY_UNDERVOLTAGE_RECOVERY or voltage > self.BATTERY_OVERVOLTAGE_RECOVERY:
            return False
        if abs(current) > self.MAX_CURRENT_RECOVERY_A:
            return False
        if temp > self.MAX_TEMPERATURE_RECOVERY_C:
            return False
        return True

    def enter_fault(self, reason: str, now_ms: float = 0.0):
        """Trips system into STATE_FAULT with fail-safe MOSFET de-energization."""
        prev_state = self.system_state.value
        self.set_mosfet(False)
        self.system_state = SystemState.STATE_FAULT

        self.fault_reason = reason
        self.last_fault_reason = reason
        self.fault_recovered = False
        self.fault_entry_time_ms = now_ms
        self.recovery_sample_count = 0

        # Reset trip counters
        self.undervoltage_count = 0
        self.overvoltage_count = 0
        self.overcurrent_count = 0
        self.overtemp_count = 0

        self.log_event("STATE_TRANSITION", {
            "from": prev_state,
            "to": SystemState.STATE_FAULT.value,
            "reason": reason,
            "mosfet_forced_off": True,
        })

    def check_safety(self, voltage: float, current: float, temp: float, sensor_valid: bool, now_ms: float):
        """Evaluates fault trip thresholds when not in FAULT."""
        if not sensor_valid:
            self.sensor_invalid_count += 1
            if self.sensor_invalid_count >= self.SENSOR_INVALID_CONFIRM_COUNT:
                self.sensor_valid = False
                self.fault_sensor = True
                self.enter_fault("SENSOR_INVALID", now_ms)
                return
        else:
            self.sensor_invalid_count = 0
            self.sensor_valid = True
            self.fault_sensor = False

        if voltage < 0.1:
            # Near-zero transient ignored
            return

        # Under voltage
        if voltage < self.BATTERY_UNDERVOLTAGE:
            self.undervoltage_count += 1
        else:
            self.undervoltage_count = 0

        if self.undervoltage_count >= self.UV_CONFIRM_COUNT:
            self.enter_fault("UNDER_VOLTAGE", now_ms)
            return

        # Over voltage
        if voltage > self.BATTERY_OVERVOLTAGE:
            self.overvoltage_count += 1
        else:
            self.overvoltage_count = 0

        if self.overvoltage_count >= self.OV_CONFIRM_COUNT:
            self.enter_fault("OVER_VOLTAGE", now_ms)
            return

        # Over current
        if current > self.MAX_CURRENT_A:
            self.overcurrent_count += 1
        else:
            self.overcurrent_count = 0

        if self.overcurrent_count >= self.OC_CONFIRM_COUNT:
            self.enter_fault("OVER_CURRENT", now_ms)
            return

        # Over temperature
        if temp >= self.MAX_TEMPERATURE_C:
            self.overtemp_count += 1
        else:
            self.overtemp_count = 0

        if self.overtemp_count >= self.OT_CONFIRM_COUNT:
            self.enter_fault("OVER_TEMPERATURE", now_ms)
            return

    def check_fault_recovery(self, voltage: float, current: float, temp: float, sensor_valid: bool, now_ms: float):
        """Evaluates recovery qualification when in STATE_FAULT."""
        if self.system_state != SystemState.STATE_FAULT:
            return

        # Latched faults cannot auto-recover
        if not self.is_fault_recoverable(self.fault_reason):
            self.recovery_sample_count = 0
            return

        if self.is_physical_condition_healthy(voltage, current, temp, sensor_valid):
            self.recovery_sample_count += 1
            self.log_event("RECOVERY_SAMPLE_QUALIFIED", {
                "sample_count": self.recovery_sample_count,
                "target": self.RECOVERY_CONFIRM_COUNT,
                "fault": self.fault_reason,
            })

            if self.recovery_sample_count >= self.RECOVERY_CONFIRM_COUNT:
                # Qualified! Safe transition: FAULT -> IDLE
                self.last_fault_reason = self.fault_reason
                self.fault_reason = "NONE"
                self.fault_recovered = True
                self.fault_clear_time_ms = now_ms
                self.recovery_sample_count = 0

                # CRITICAL INVARIANT: MOSFET MUST REMAIN OFF
                self.set_mosfet(False)

                self.system_state = SystemState.STATE_IDLE
                self.state_start_time_ms = now_ms

                # Reset all counters
                self.undervoltage_count = 0
                self.overvoltage_count = 0
                self.overcurrent_count = 0
                self.overtemp_count = 0
                self.sensor_invalid_count = 0

                self.log_event("STATE_TRANSITION", {
                    "from": SystemState.STATE_FAULT.value,
                    "to": SystemState.STATE_IDLE.value,
                    "reason": "FAULT_RECOVERY_QUALIFIED",
                    "prior_fault": self.last_fault_reason,
                    "mosfet_state": "OFF",
                })
        else:
            if self.recovery_sample_count > 0:
                self.log_event("RECOVERY_QUALIFICATION_RESET", {
                    "previous_count": self.recovery_sample_count,
                    "fault": self.fault_reason,
                })
                self.recovery_sample_count = 0

    def step(
        self,
        voltage: float,
        current: float,
        temp: float,
        sensor_valid: bool = True,
        now_ms: float = 0.0
    ):
        """Simulates one sensor sample interval loop tick."""
        self.telemetry_sequence += 1
        self.battery_voltage = voltage
        self.current_a = current
        self.temperature_c = temp

        if self.system_state != SystemState.STATE_FAULT:
            self.check_safety(voltage, current, temp, sensor_valid, now_ms)
        else:
            # Continuous fail-safe enforcement
            if self.mosfet_state:
                self.set_mosfet(False)
            self.check_fault_recovery(voltage, current, temp, sensor_valid, now_ms)

        # Handle RUNNING / COOLDOWN test timing
        if self.system_state == SystemState.STATE_RUNNING:
            elapsed = now_ms - self.state_start_time_ms
            if elapsed >= self.LOAD_ON_TIME_MS:
                self.set_mosfet(False)
                self.system_state = SystemState.STATE_COOLDOWN
                self.state_start_time_ms = now_ms
                self.test_cycle_count += 1
                self.log_event("CYCLE_COMPLETED", {"cycle": self.test_cycle_count})

        elif self.system_state == SystemState.STATE_COOLDOWN:
            elapsed = now_ms - self.state_start_time_ms
            if elapsed >= self.LOAD_OFF_TIME_MS:
                self.set_mosfet(True)
                self.system_state = SystemState.STATE_RUNNING
                self.state_start_time_ms = now_ms

    def clear_fault(
        self,
        voltage: float,
        current: float,
        temp: float,
        sensor_valid: bool = True,
        now_ms: float = 0.0
    ) -> bool:
        """
        Manual CLEAR command handler.
        Rejects clearance if physical fault condition remains active!
        """
        if not self.is_physical_condition_healthy(voltage, current, temp, sensor_valid):
            self.log_event("CLEAR_REJECTED", {
                "reason": "PHYSICAL_FAULT_ACTIVE",
                "fault": self.fault_reason,
            })
            return False

        self.last_fault_reason = self.fault_reason
        self.fault_reason = "NONE"
        self.fault_recovered = True
        self.fault_clear_time_ms = now_ms
        self.recovery_sample_count = 0

        self.set_mosfet(False)
        self.system_state = SystemState.STATE_IDLE
        self.state_start_time_ms = now_ms

        self.undervoltage_count = 0
        self.overvoltage_count = 0
        self.overcurrent_count = 0
        self.overtemp_count = 0
        self.sensor_invalid_count = 0

        self.log_event("STATE_TRANSITION", {
            "from": SystemState.STATE_FAULT.value,
            "to": SystemState.STATE_IDLE.value,
            "reason": "MANUAL_CLEAR",
            "prior_fault": self.last_fault_reason,
            "mosfet_state": "OFF",
        })
        return True

    def command(
        self,
        cmd: str,
        voltage: float = 7.40,
        current: float = 0.0,
        temp: float = 25.0,
        sensor_valid: bool = True,
        now_ms: float = 0.0
    ) -> bool:
        """Processes high-level operator / supervisory commands."""
        c = cmd.strip().upper()
        if c == "ON":
            if self.system_state == SystemState.STATE_FAULT:
                self.log_event("COMMAND_REJECTED", {"command": "ON", "state": "FAULT"})
                return False
            self.set_mosfet(True)
            self.system_state = SystemState.STATE_RUNNING
            self.state_start_time_ms = now_ms
            return True

        elif c == "OFF":
            self.set_mosfet(False)
            self.system_state = SystemState.STATE_IDLE
            self.state_start_time_ms = now_ms
            return True

        elif c == "AUTO":
            if self.system_state == SystemState.STATE_FAULT:
                self.log_event("COMMAND_REJECTED", {"command": "AUTO", "state": "FAULT"})
                return False
            self.set_mosfet(True)
            self.system_state = SystemState.STATE_RUNNING
            self.state_start_time_ms = now_ms
            return True

        elif c == "STOP":
            self.set_mosfet(False)
            self.system_state = SystemState.STATE_IDLE
            self.state_start_time_ms = now_ms
            return True

        elif c == "CLEAR":
            return self.clear_fault(voltage, current, temp, sensor_valid, now_ms)

        return False

    def build_telemetry(self, now_ms: float = 0.0) -> Dict[str, Any]:
        """Produces canonical telemetry dictionary mirroring ESP32 NDJSON."""
        return {
            "schema_version": "1.0.0",
            "device_id": self.device_id,
            "sequence": self.telemetry_sequence,
            "timestamp_ms": now_ms,
            "state": self.system_state.value,
            "voltage_V": self.battery_voltage,
            "current_A": self.current_a,
            "power_W": round(self.battery_voltage * self.current_a, 3),
            "temperature_C": self.temperature_c,
            "mosfet": self.mosfet_state,
            "mosfet_state": "ON" if self.mosfet_state else "OFF",
            "cycle_count": self.test_cycle_count,
            "sensor_valid": self.sensor_valid,
            "fault": self.fault_reason,
            "last_fault": self.last_fault_reason,
            "fault_recovered": self.fault_recovered,
            "recovery_count": self.recovery_sample_count,
            "fault_entry_ms": self.fault_entry_time_ms,
            "fault_clear_ms": self.fault_clear_time_ms,
            "hardware_fault": self.fault_reason != "NONE",
            "uv_count": self.undervoltage_count,
            "ov_count": self.overvoltage_count,
            "oc_count": self.overcurrent_count,
            "ot_count": self.overtemp_count,
            "sensor_error_count": self.sensor_invalid_count,
        }
