"""
Canonical Hardware-Agnostic Telemetry Schema (Layer 2)
Project: RMK-REVOLT / SECONDShift Platform

Defines strongly typed telemetry contracts for ingestion of battery sensor frames
from real ESP32 microcontrollers, hardware mocks, or recorded replay streams.
All units are explicitly defined and non-negotiable.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional
import time


class TelemetryQuality(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    STALE = "STALE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    SENSOR_FAULT = "SENSOR_FAULT"
    COMMUNICATION_FAULT = "COMMUNICATION_FAULT"
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"


class SensorHealthStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"
    UNAVAILABLE = "UNAVAILABLE"


class CommunicationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    DROPOUT = "DROPOUT"
    DISCONNECTED = "DISCONNECTED"


class CalibrationStatus(str, Enum):
    CALIBRATED = "CALIBRATED"
    UNCALIBRATED = "UNCALIBRATED"
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"


class TelemetrySource(str, Enum):
    REAL_HARDWARE = "REAL_HARDWARE"
    MOCK_HARDWARE = "MOCK_HARDWARE"
    REPLAY_FILE = "REPLAY_FILE"
    SYNTHETIC_BENCH = "SYNTHETIC_BENCH"


@dataclass
class TelemetryFrame:
    """
    Canonical strongly-typed battery telemetry frame.
    All physical units are explicit:
    - voltage_v: Terminal voltage in Volts (V)
    - current_a: String current in Amperes (A) [positive = discharge, negative = charge]
    - temperature_c: Module surface temperature in Celsius (°C)
    - cell_voltages_v: Array of cell series voltages in Volts (V)
    - cell_temperatures_c: Array of cell temperatures in Celsius (°C)
    - timestamp: Monotonic or POSIX epoch timestamp in seconds (s)
    """
    device_id: str
    sequence_number: int
    timestamp: float
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    temperature_c: Optional[float] = None
    cell_voltages_v: List[float] = field(default_factory=list)
    cell_temperatures_c: List[float] = field(default_factory=list)
    estimated_soc: Optional[float] = None
    sensor_status: Dict[str, str] = field(default_factory=lambda: {
        "voltage": SensorHealthStatus.OK.value,
        "current": SensorHealthStatus.OK.value,
        "temperature": SensorHealthStatus.OK.value
    })
    communication_status: str = CommunicationStatus.CONNECTED.value
    calibration_status: str = CalibrationStatus.CALIBRATED.value
    source: str = TelemetrySource.MOCK_HARDWARE.value
    quality_flags: List[str] = field(default_factory=lambda: [TelemetryQuality.VALID.value])
    raw_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes frame to standard dictionary."""
        d = asdict(self)
        # Ensure enums are string values
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryFrame":
        """Constructs a TelemetryFrame from a dictionary with permissive key mapping."""
        def _first_present(*keys, default=None):
            for k in keys:
                if k in data and data[k] is not None:
                    return data[k]
            return default

        # Map common aliases from ESP32 or JSON formats
        seq = _first_present("sequence_number", "seq", default=0)
        ts = _first_present("timestamp", "timestamp_s")
        if ts is None and "timestamp_ms" in data and data["timestamp_ms"] is not None:
            ts = float(data["timestamp_ms"]) / 1000.0
        if ts is None:
            ts = time.time()

        dev_id = str(_first_present("device_id", default="SECONDShift-DEFAULT"))
        v = _first_present("voltage_v", "voltage")
        i = _first_present("current_a", "current")
        t = _first_present("temperature_c", "temperature")
        soc = _first_present("estimated_soc", "soc")

        cell_v = _first_present("cell_voltages_v", "cell_voltages", default=[])
        if isinstance(cell_v, (int, float)):
            cell_v = [float(cell_v)]
        else:
            cell_v = [float(x) for x in cell_v]

        cell_t = _first_present("cell_temperatures_c", "cell_temperatures", default=[])
        if isinstance(cell_t, (int, float)):
            cell_t = [float(cell_t)]
        else:
            cell_t = [float(x) for x in cell_t]

        sensor_st = _first_present("sensor_status", default={
            "voltage": SensorHealthStatus.OK.value,
            "current": SensorHealthStatus.OK.value,
            "temperature": SensorHealthStatus.OK.value
        })

        comm_st = _first_present("communication_status", default=CommunicationStatus.CONNECTED.value)
        calib_st = _first_present("calibration_status", default=CalibrationStatus.CALIBRATED.value)
        src = _first_present("source", default=TelemetrySource.MOCK_HARDWARE.value)
        q_flags = _first_present("quality_flags", default=[TelemetryQuality.VALID.value])

        return cls(
            device_id=dev_id,
            sequence_number=int(seq),
            timestamp=float(ts),
            voltage_v=float(v) if v is not None else None,
            current_a=float(i) if i is not None else None,
            temperature_c=float(t) if t is not None else None,
            cell_voltages_v=cell_v,
            cell_temperatures_c=cell_t,
            estimated_soc=float(soc) if soc is not None else None,
            sensor_status=sensor_st,
            communication_status=str(comm_st),
            calibration_status=str(calib_st),
            source=str(src),
            quality_flags=list(q_flags),
            raw_payload=data
        )

    def is_valid(self) -> bool:
        """Returns True if frame has no critical fault or invalid quality flags."""
        invalid_flags = {
            TelemetryQuality.MISSING.value,
            TelemetryQuality.STALE.value,
            TelemetryQuality.OUT_OF_RANGE.value,
            TelemetryQuality.SENSOR_FAULT.value,
            TelemetryQuality.COMMUNICATION_FAULT.value
        }
        return not any(flag in invalid_flags for flag in self.quality_flags)
