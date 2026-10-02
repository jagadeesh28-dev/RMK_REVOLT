"""
Mock Hardware Adapter (Layer 1)
Project: RMK-REVOLT / SECONDShift Platform

Emulates battery pack behavior and sensor telemetry conforming to the
canonical TelemetryFrame contract. Supports comprehensive failure modes:
- Normal battery (Healthy LFP)
- Degraded battery
- High resistance
- Low SOH
- Elevated / fault temperature
- Missing sensor data
- Stale telemetry
- Communication dropout
- Malformed telemetry
- Voltage fault (UVP / OVP)
- Current overload fault
"""

import time
import math
from typing import Dict, Any, List, Optional

try:
    from secondshift.interfaces.hardware_interface import HardwareInterface
    from secondshift.interfaces.telemetry_schema import (
        TelemetryFrame,
        TelemetryQuality,
        SensorHealthStatus,
        CommunicationStatus,
        TelemetrySource
    )
except ImportError:
    from interfaces.hardware_interface import HardwareInterface
    from interfaces.telemetry_schema import (
        TelemetryFrame,
        TelemetryQuality,
        SensorHealthStatus,
        CommunicationStatus,
        TelemetrySource
    )


class MockHardware(HardwareInterface):
    """
    Mock battery testbed hardware adapter.
    Produces TelemetryFrames conforming to canonical schema.
    """
    def __init__(
        self,
        device_id: str = "SECONDShift-MOCK-01",
        chemistry: str = "LFP",
        soh: float = 0.92,
        r0_mohm: float = 2.0,
        nominal_voltage_v: float = 12.8,
        ambient_temp_c: float = 25.0,
        n_cells: int = 4
    ):
        self.device_id = device_id
        self.chemistry = chemistry
        self.soh = soh
        self.r0_ohms = r0_mohm / 1000.0
        self.nominal_v = nominal_voltage_v
        self.ambient_temp_c = ambient_temp_c
        self.n_cells = n_cells

        # Link state
        self._connected = False
        self._seq = 0
        self._load_current_a = 0.0
        self._contactors_closed = False
        self._command_history: List[Dict[str, Any]] = []

        # Fault injection modes
        self.fault_mode: Optional[str] = None
        self._stale_timestamp: Optional[float] = None
        self._dropout_active = False

        # Internal thermal & electrical state
        self._temp_c = ambient_temp_c
        self._soc = 0.60 # Default resting SOC

    def set_fault_mode(self, mode: Optional[str]):
        """
        Injects a specific simulated failure mode:
        - "DEGRADED": SOH=0.72, R0=3.4mOhm
        - "HIGH_RESISTANCE": R0=6.5mOhm
        - "LOW_SOH": SOH=0.45
        - "HIGH_TEMP": T=48.0°C (triage violation)
        - "CRITICAL_OTP": T=63.0°C (thermal trip)
        - "MISSING_SENSOR": Temperature sensor set to None / FAULT
        - "STALE_TELEMETRY": Timestamps freeze in the past
        - "COMM_DROPOUT": read_telemetry returns None
        - "MALFORMED_TELEMETRY": Emits NaN / unparseable numbers
        - "UVP_FAULT": Cell voltage drops to 1.85V
        - "OVP_FAULT": Cell voltage spikes to 3.80V
        - "CURRENT_FAULT": Current exceeds 45A
        """
        self.fault_mode = mode
        if mode == "DEGRADED":
            self.soh = 0.72
            self.r0_ohms = 0.0034
        elif mode == "HIGH_RESISTANCE":
            self.r0_ohms = 0.0065
        elif mode == "LOW_SOH":
            self.soh = 0.45
        elif mode == "HIGH_TEMP":
            self._temp_c = 48.0
        elif mode == "CRITICAL_OTP":
            self._temp_c = 63.5
        elif mode == "STALE_TELEMETRY":
            self._stale_timestamp = time.time() - 30.0
        elif mode == "COMM_DROPOUT":
            self._dropout_active = True
        elif mode == "UVP_FAULT":
            self._soc = -0.1
        elif mode == "OVP_FAULT":
            self._soc = 1.2
        elif mode is None:
            self._dropout_active = False
            self._stale_timestamp = None

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._contactors_closed = False
        self._load_current_a = 0.0

    def is_connected(self) -> bool:
        return self._connected and not self._dropout_active

    def _compute_cell_ocv(self, soc_fraction: float) -> float:
        """Thermodynamic OCV model."""
        s = max(0.0, min(1.0, soc_fraction))
        if self.chemistry == "LFP":
            if s < 0.05:
                return 2.50 + 11.0 * s
            elif s < 0.15:
                return 3.05 + 1.9 * (s - 0.05)
            elif s < 0.85:
                return 3.24 + 0.12857 * (s - 0.15)
            elif s < 0.95:
                return 3.33 + 0.9 * (s - 0.85)
            else:
                return 3.42 + 4.6 * (s - 0.95)
        else: # NMC
            if s < 0.10:
                return 3.00 + 4.5 * s
            elif s < 0.80:
                return 3.45 + 0.6714 * (s - 0.10)
            else:
                return 3.92 + 1.40 * (s - 0.80)

    def read_telemetry(self, timeout_s: float = 1.0) -> Optional[TelemetryFrame]:
        if not self._connected or self._dropout_active:
            return None

        self._seq += 1
        now = time.time()

        # Handle stale fault
        if self.fault_mode == "STALE_TELEMETRY" and self._stale_timestamp is not None:
            ts = self._stale_timestamp
        else:
            ts = now

        # Handle UVP / OVP faults
        if self.fault_mode == "UVP_FAULT":
            cell_v_base = 1.850
        elif self.fault_mode == "OVP_FAULT":
            cell_v_base = 3.820
        else:
            cell_v_base = self._compute_cell_ocv(self._soc)

        # Current calculation
        if self._contactors_closed:
            cur = self._load_current_a
        else:
            cur = 0.0

        if self.fault_mode == "CURRENT_FAULT":
            cur = 48.5

        # Ohmic drop
        cell_voltages = []
        for c in range(self.n_cells):
            v_c = cell_v_base - (cur * self.r0_ohms)
            cell_voltages.append(float(v_c))

        total_v = sum(cell_voltages)

        # Thermal calculation
        if self._contactors_closed and cur > 0:
            self._temp_c += (cur**2 * self.r0_ohms * 0.05) - 0.01 * (self._temp_c - self.ambient_temp_c)

        temp_out = float(self._temp_c)

        # Sensor status dictionary
        sensor_status = {
            "voltage": SensorHealthStatus.OK.value,
            "current": SensorHealthStatus.OK.value,
            "temperature": SensorHealthStatus.OK.value
        }

        # Handle missing sensor fault
        if self.fault_mode == "MISSING_SENSOR":
            temp_out = None
            sensor_status["temperature"] = SensorHealthStatus.FAULT.value

        # Handle malformed telemetry fault
        if self.fault_mode == "MALFORMED_TELEMETRY":
            total_v = float("nan")
            cell_voltages[0] = float("inf")

        frame = TelemetryFrame(
            device_id=self.device_id,
            sequence_number=self._seq,
            timestamp=ts,
            voltage_v=total_v if not math.isnan(total_v) else float("nan"),
            current_a=cur,
            temperature_c=temp_out,
            cell_voltages_v=cell_voltages,
            cell_temperatures_c=[temp_out if temp_out is not None else 25.0] * self.n_cells,
            estimated_soc=self._soc,
            sensor_status=sensor_status,
            communication_status=CommunicationStatus.CONNECTED.value if not self._dropout_active else CommunicationStatus.DROPOUT.value,
            calibration_status="CALIBRATED",
            source=TelemetrySource.MOCK_HARDWARE.value,
            quality_flags=[TelemetryQuality.VALID.value] if self.fault_mode is None else [TelemetryQuality.SENSOR_FAULT.value]
        )
        return frame

    def send_command(self, command: Dict[str, Any]) -> bool:
        if not self._connected:
            return False

        self._command_history.append(command)
        action = command.get("action")
        req_mode = command.get("requested_mode")

        if action == "OPERATE" or req_mode == "ENABLE_LOAD":
            self._contactors_closed = True
            current_setpoint = command.get("current_a", 5.0)
            self._load_current_a = float(current_setpoint)
            return True
        elif action == "DERATE" or req_mode == "LIMIT_LOAD":
            self._contactors_closed = True
            self._load_current_a = float(command.get("current_a", 2.5))
            return True
        elif action in ["RETIRE", "EMERGENCY_ISOLATE"] or req_mode == "ISOLATE":
            self._contactors_closed = False
            self._load_current_a = 0.0
            return True
        elif action == "HOLD" or req_mode == "KEEP_ISOLATED":
            self._contactors_closed = False
            self._load_current_a = 0.0
            return True
        elif action == "REQUEST_MEASUREMENT":
            self._load_current_a = float(command.get("pulse_current_a", 0.0))
            return True

        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "connected": self._connected,
            "contactors_closed": self._contactors_closed,
            "load_current_a": self._load_current_a,
            "sequence_count": self._seq,
            "fault_mode": self.fault_mode,
            "commands_received_count": len(self._command_history)
        }
