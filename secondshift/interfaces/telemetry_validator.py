"""
Telemetry Validation Engine (Layer 2)
Project: RMK-REVOLT / SECONDShift Platform

Enforces strict, non-negotiable validation of incoming telemetry frames.
Invariants:
- NEVER silently repair or substitute corrupt values.
- Reject NaN, Infinity, physical range violations, and stale frames.
- Return structured fault diagnostics with explicit error codes.
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus
)


@dataclass
class TelemetryValidationResult:
    """Structured result of telemetry frame validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality: str = TelemetryQuality.VALID.value
    rejected_fields: List[str] = field(default_factory=list)
    validated_frame: Optional[TelemetryFrame] = None


class TelemetryValidator:
    """
    Validates physical feasibility and integrity of battery telemetry frames.
    Does NOT modify input data.
    """
    def __init__(
        self,
        v_min_module: float = 1.0,
        v_max_module: float = 60.0,
        v_min_cell: float = 1.0,
        v_max_cell: float = 4.5,
        i_min_a: float = -50.0,
        i_max_a: float = 50.0,
        temp_min_c: float = -20.0,
        temp_max_c: float = 85.0,
        max_stale_age_s: float = 2.0
    ):
        self.v_min_mod = v_min_module
        self.v_max_mod = v_max_module
        self.v_min_cell = v_min_cell
        self.v_max_cell = v_max_cell
        self.i_min = i_min_a
        self.i_max = i_max_a
        self.temp_min = temp_min_c
        self.temp_max = temp_max_c
        self.max_stale_age_s = max_stale_age_s
        self._last_seq: Optional[int] = None
        self._last_seen_time: Optional[float] = None

    def reset_sequence_tracking(self):
        """Resets sequence tracking state."""
        self._last_seq = None
        self._last_seen_time = None

    def validate_telemetry(
        self,
        frame: TelemetryFrame,
        current_time: Optional[float] = None,
        allow_stale_for_replay: bool = False
    ) -> TelemetryValidationResult:
        """
        Validates a TelemetryFrame against structural, physical, and temporal rules.
        """
        errors: List[str] = []
        warnings: List[str] = []
        rejected_fields: List[str] = []
        quality = TelemetryQuality.VALID.value

        now = current_time if current_time is not None else time.time()

        # 0. NULL CHECK
        if frame is None:
            return TelemetryValidationResult(
                valid=False,
                errors=["ERR_COMM_01: Telemetry frame is None (Link Disconnected / Dropout)"],
                warnings=[],
                quality=TelemetryQuality.COMMUNICATION_FAULT.value,
                rejected_fields=["frame"],
                validated_frame=None
            )

        # 1. STRUCTURAL CHECKS
        if not frame.device_id or not isinstance(frame.device_id, str):
            errors.append("ERR_STRUCT_01: Missing or invalid device_id")
            rejected_fields.append("device_id")

        if frame.sequence_number is None or not isinstance(frame.sequence_number, int):
            errors.append("ERR_STRUCT_02: Missing or invalid sequence_number")
            rejected_fields.append("sequence_number")

        if frame.timestamp is None or not isinstance(frame.timestamp, (int, float)):
            errors.append("ERR_STRUCT_03: Missing or invalid timestamp")
            rejected_fields.append("timestamp")

        # 2. NUMERIC SANITY CHECKS (NaN / Infinity)
        for field_name, val in [
            ("voltage_v", frame.voltage_v),
            ("current_a", frame.current_a),
            ("temperature_c", frame.temperature_c),
            ("estimated_soc", frame.estimated_soc)
        ]:
            if val is not None:
                if math.isnan(val):
                    errors.append(f"ERR_NUM_01: Field '{field_name}' contains NaN")
                    rejected_fields.append(field_name)
                elif math.isinf(val):
                    errors.append(f"ERR_NUM_02: Field '{field_name}' contains Infinity")
                    rejected_fields.append(field_name)

        for idx, cv in enumerate(frame.cell_voltages_v):
            if math.isnan(cv) or math.isinf(cv):
                errors.append(f"ERR_NUM_03: cell_voltages_v[{idx}] contains NaN or Inf ({cv})")
                rejected_fields.append(f"cell_voltages_v[{idx}]")

        for idx, ct in enumerate(frame.cell_temperatures_c):
            if math.isnan(ct) or math.isinf(ct):
                errors.append(f"ERR_NUM_04: cell_temperatures_c[{idx}] contains NaN or Inf ({ct})")
                rejected_fields.append(f"cell_temperatures_c[{idx}]")

        # 3. PHYSICAL RANGE VIOLATIONS
        if frame.voltage_v is not None and "voltage_v" not in rejected_fields:
            if frame.voltage_v < self.v_min_mod or frame.voltage_v > self.v_max_mod:
                errors.append(f"ERR_RANGE_01: Module voltage {frame.voltage_v:.3f}V outside [{self.v_min_mod}, {self.v_max_mod}]V")
                rejected_fields.append("voltage_v")
                quality = TelemetryQuality.OUT_OF_RANGE.value

        for idx, cv in enumerate(frame.cell_voltages_v):
            if cv < self.v_min_cell or cv > self.v_max_cell:
                errors.append(f"ERR_RANGE_02: Cell {idx} voltage {cv:.3f}V outside [{self.v_min_cell}, {self.v_max_cell}]V")
                rejected_fields.append(f"cell_voltages_v[{idx}]")
                quality = TelemetryQuality.OUT_OF_RANGE.value

        if frame.current_a is not None and "current_a" not in rejected_fields:
            if frame.current_a < self.i_min or frame.current_a > self.i_max:
                errors.append(f"ERR_RANGE_03: Current {frame.current_a:.2f}A outside [{self.i_min}, {self.i_max}]A")
                rejected_fields.append("current_a")
                quality = TelemetryQuality.OUT_OF_RANGE.value

        if frame.temperature_c is not None and "temperature_c" not in rejected_fields:
            if frame.temperature_c < self.temp_min or frame.temperature_c > self.temp_max:
                errors.append(f"ERR_RANGE_04: Temperature {frame.temperature_c:.1f}°C outside [{self.temp_min}, {self.temp_max}]°C")
                rejected_fields.append("temperature_c")
                quality = TelemetryQuality.OUT_OF_RANGE.value

        # 4. SENSOR HEALTH FLAGS
        for sens_name, sens_st in frame.sensor_status.items():
            if sens_st in [SensorHealthStatus.FAULT.value, SensorHealthStatus.UNAVAILABLE.value]:
                errors.append(f"ERR_SENS_01: Sensor '{sens_name}' status is {sens_st}")
                rejected_fields.append(f"sensor_status.{sens_name}")
                quality = TelemetryQuality.SENSOR_FAULT.value
            elif sens_st == SensorHealthStatus.DEGRADED.value:
                warnings.append(f"WARN_SENS_01: Sensor '{sens_name}' is degraded")

        # 5. COMMUNICATION STATUS
        if frame.communication_status in [CommunicationStatus.DISCONNECTED.value, CommunicationStatus.DROPOUT.value]:
            errors.append(f"ERR_COMM_01: Communication status indicates fault: {frame.communication_status}")
            quality = TelemetryQuality.COMMUNICATION_FAULT.value
        elif frame.communication_status == CommunicationStatus.DEGRADED.value:
            warnings.append("WARN_COMM_01: Communication link is degraded")

        # 6. TEMPORAL INTEGRITY (Staleness & Future Drift)
        if not allow_stale_for_replay:
            age = now - frame.timestamp
            if age > self.max_stale_age_s:
                errors.append(f"ERR_TIME_01: Telemetry frame is STALE (age={age:.2f}s > {self.max_stale_age_s}s)")
                quality = TelemetryQuality.STALE.value
            elif age < -5.0: # Future timestamp (> 5s ahead)
                errors.append(f"ERR_TIME_02: Telemetry timestamp is in the future by {abs(age):.2f}s (Clock Skew)")
                quality = TelemetryQuality.STALE.value

        # 7. SEQUENCE NUMBER CONTINUITY
        if self._last_seq is not None:
            expected_seq = self._last_seq + 1
            if frame.sequence_number == self._last_seq:
                warnings.append(f"WARN_SEQ_01: Duplicate sequence number detected ({frame.sequence_number})")
            elif frame.sequence_number < self._last_seq:
                errors.append(f"ERR_SEQ_01: Sequence number regression ({frame.sequence_number} < {self._last_seq})")
                quality = TelemetryQuality.COMMUNICATION_FAULT.value
            elif frame.sequence_number > expected_seq:
                dropped = frame.sequence_number - expected_seq
                warnings.append(f"WARN_SEQ_02: Sequence gap detected (expected {expected_seq}, got {frame.sequence_number}; {dropped} frames dropped)")

        self._last_seq = frame.sequence_number
        self._last_seen_time = now

        # 8. FINAL DECISION
        is_valid = len(errors) == 0

        # Update quality flags in frame copy if valid
        validated_frame = frame
        if not is_valid:
            validated_frame.quality_flags = list(set(frame.quality_flags + [quality]))
        else:
            validated_frame.quality_flags = [TelemetryQuality.VALID.value]

        return TelemetryValidationResult(
            valid=is_valid,
            errors=errors,
            warnings=warnings,
            quality=quality if not is_valid else TelemetryQuality.VALID.value,
            rejected_fields=rejected_fields,
            validated_frame=validated_frame
        )

    # Alias for convenience
    validate_frame = validate_telemetry

