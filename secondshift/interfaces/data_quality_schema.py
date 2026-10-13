"""
Canonical Data Quality and Scientific Measurement Admissibility Schema (Layer 2 / 3)
Project: RMK-REVOLT / SECONDShift Platform

Defines the non-negotiable separation between:
1. RAW MEASUREMENT: Data physically reported by ADC / telemetry bus.
2. SENSOR VALIDITY: Whether the sensing hardware is electrically healthy and uncorrupted.
3. EVENT VALIDITY: Whether the commanded physical transient actually occurred.
4. INFERENCE VALIDITY: Whether the gathered evidence is mathematically and physically
   admissible for downstream State of Health, internal resistance (R0), or chemistry updates.

PRINCIPLE:
    A sensor reading being technically available does NOT mean that it is valid
    for every scientific inference.
    SensorValidity != MeasurementAdmissibility.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional
import json
import time

from secondshift.interfaces.epistemic_schema import ReasonCode


class DataQualityState(str, Enum):
    """Categorical data quality classification."""
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"


class EventClassification(str, Enum):
    """
    Distinguishes sensor errors from intentional or autonomous system actions.
    Example: Contactor opening due to protection is a SYSTEM_EVENT / HARDWARE_TRIP,
    NOT an INA219 SENSOR_FAULT.
    """
    NORMAL_OPERATION = "NORMAL_OPERATION"
    DIAGNOSTIC_PULSE = "DIAGNOSTIC_PULSE"
    SENSOR_FAULT = "SENSOR_FAULT"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    HARDWARE_TRIP = "HARDWARE_TRIP"
    CONTACTOR_OPEN = "CONTACTOR_OPEN"


@dataclass
class DataQualityRecord:
    """
    Strongly typed record capturing physical, temporal, and sensory validity
    along with downstream scientific inference admissibility.
    """
    timestamp: float = field(default_factory=time.time)
    timestamp_valid: bool = True
    sequence_valid: bool = True
    voltage_valid: bool = True
    current_valid: bool = True
    temperature_valid: bool = True
    sensor_valid: bool = True
    telemetry_complete: bool = True
    stale_data: bool = False
    communication_fault: bool = False
    range_fault: bool = False
    noise_fault: bool = False

    # Inference / Event Admissibility
    current_flow_valid: bool = False
    pulse_valid: bool = False
    admissible_for_r0: bool = False
    admissible_for_chemistry: bool = False
    measurement_admissible: bool = False

    quality_state: str = DataQualityState.VALID.value
    event_classification: str = EventClassification.NORMAL_OPERATION.value

    # Configured margins
    configured_i_min: float = 0.0
    observed_current: float = 0.0
    current_margin: float = 0.0

    reason_codes: List[ReasonCode] = field(default_factory=list)
    validation_details: Dict[str, Any] = field(default_factory=dict)

    def validate_invariants(self) -> List[str]:
        """Validates invariant rules governing data quality and admissibility."""
        errors: List[str] = []

        # Invariant: If sensor_valid is False, measurement_admissible must be False
        if not self.sensor_valid and self.measurement_admissible:
            errors.append("INVARIANT VIOLATION: Measurement cannot be admissible when sensor_valid is False.")

        # Invariant: If pulse_valid is True, current_flow_valid must be True
        if self.pulse_valid and not self.current_flow_valid:
            errors.append("INVARIANT VIOLATION: Diagnostic pulse cannot be valid without verified current flow.")

        # Invariant: If current is below threshold, pulse_valid cannot be True
        if self.observed_current < self.configured_i_min and self.pulse_valid:
            errors.append(
                f"INVARIANT VIOLATION: pulse_valid is True but observed current "
                f"{self.observed_current:.3f}A is below configured I_MIN {self.configured_i_min:.3f}A."
            )

        # Invariant: Admissibility for R0 or chemistry requires pulse_valid
        if (self.admissible_for_r0 or self.admissible_for_chemistry) and not self.pulse_valid:
            errors.append("INVARIANT VIOLATION: Cannot be admissible for R0 or chemistry if pulse_valid is False.")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Serializes record to standard dictionary representation."""
        return {
            "timestamp": self.timestamp,
            "timestamp_valid": self.timestamp_valid,
            "sequence_valid": self.sequence_valid,
            "voltage_valid": self.voltage_valid,
            "current_valid": self.current_valid,
            "temperature_valid": self.temperature_valid,
            "sensor_valid": self.sensor_valid,
            "telemetry_complete": self.telemetry_complete,
            "stale_data": self.stale_data,
            "communication_fault": self.communication_fault,
            "range_fault": self.range_fault,
            "noise_fault": self.noise_fault,
            "current_flow_valid": self.current_flow_valid,
            "pulse_valid": self.pulse_valid,
            "admissible_for_r0": self.admissible_for_r0,
            "admissible_for_chemistry": self.admissible_for_chemistry,
            "measurement_admissible": self.measurement_admissible,
            "quality_state": self.quality_state,
            "event_classification": self.event_classification,
            "configured_i_min": self.configured_i_min,
            "observed_current": self.observed_current,
            "current_margin": self.current_margin,
            "reason_codes": [rc.value if isinstance(rc, ReasonCode) else str(rc) for rc in self.reason_codes],
            "validation_details": self.validation_details
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataQualityRecord":
        """Reconstructs DataQualityRecord from dictionary."""
        def _parse_reasons(raw: Any) -> List[ReasonCode]:
            res = []
            if isinstance(raw, list):
                for c in raw:
                    if isinstance(c, ReasonCode):
                        res.append(c)
                    elif isinstance(c, str):
                        try:
                            res.append(ReasonCode(c))
                        except ValueError:
                            pass
            return res

        return cls(
            timestamp=float(data.get("timestamp", time.time())),
            timestamp_valid=bool(data.get("timestamp_valid", True)),
            sequence_valid=bool(data.get("sequence_valid", True)),
            voltage_valid=bool(data.get("voltage_valid", True)),
            current_valid=bool(data.get("current_valid", True)),
            temperature_valid=bool(data.get("temperature_valid", True)),
            sensor_valid=bool(data.get("sensor_valid", True)),
            telemetry_complete=bool(data.get("telemetry_complete", True)),
            stale_data=bool(data.get("stale_data", False)),
            communication_fault=bool(data.get("communication_fault", False)),
            range_fault=bool(data.get("range_fault", False)),
            noise_fault=bool(data.get("noise_fault", False)),
            current_flow_valid=bool(data.get("current_flow_valid", False)),
            pulse_valid=bool(data.get("pulse_valid", False)),
            admissible_for_r0=bool(data.get("admissible_for_r0", False)),
            admissible_for_chemistry=bool(data.get("admissible_for_chemistry", False)),
            measurement_admissible=bool(data.get("measurement_admissible", False)),
            quality_state=str(data.get("quality_state", DataQualityState.VALID.value)),
            event_classification=str(data.get("event_classification", EventClassification.NORMAL_OPERATION.value)),
            configured_i_min=float(data.get("configured_i_min", 0.0)),
            observed_current=float(data.get("observed_current", 0.0)),
            current_margin=float(data.get("current_margin", 0.0)),
            reason_codes=_parse_reasons(data.get("reason_codes", [])),
            validation_details=dict(data.get("validation_details", {}))
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "DataQualityRecord":
        return cls.from_dict(json.loads(json_str))


@dataclass
class PulseValidationRecord:
    """
    Dedicated validation certificate for transient diagnostic pulses.
    Ensures that current actually flowed, contactors remained closed,
    and voltages/currents were within physical limits throughout the pulse.
    """
    pulse_valid: bool
    admissible_for_r0: bool
    admissible_for_chemistry: bool
    configured_i_min: float
    mean_pulse_current_a: float
    current_margin_a: float
    duration_s: float
    delta_v_ohmic: Optional[float] = None
    delta_v_total: Optional[float] = None
    delta_i: float = 0.0
    hardware_tripped: bool = False
    contactor_open: bool = False
    data_quality: Optional[DataQualityRecord] = None
    reason_codes: List[ReasonCode] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def current_flow_valid(self) -> bool:
        return (not self.contactor_open) and (self.mean_pulse_current_a >= self.configured_i_min) and (self.mean_pulse_current_a > 0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pulse_valid": self.pulse_valid,
            "current_flow_valid": self.current_flow_valid,
            "admissible_for_r0": self.admissible_for_r0,
            "admissible_for_chemistry": self.admissible_for_chemistry,
            "configured_i_min": self.configured_i_min,
            "mean_pulse_current_a": self.mean_pulse_current_a,
            "current_margin_a": self.current_margin_a,
            "duration_s": self.duration_s,
            "delta_v_ohmic": self.delta_v_ohmic,
            "delta_v_total": self.delta_v_total,
            "delta_i": self.delta_i,
            "hardware_tripped": self.hardware_tripped,
            "contactor_open": self.contactor_open,
            "data_quality": self.data_quality.to_dict() if self.data_quality else {},
            "reason_codes": [rc.value if isinstance(rc, ReasonCode) else str(rc) for rc in self.reason_codes],
            "details": self.details
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PulseValidationRecord":
        def _parse_reasons(raw: Any) -> List[ReasonCode]:
            res = []
            if isinstance(raw, list):
                for c in raw:
                    if isinstance(c, ReasonCode):
                        res.append(c)
                    elif isinstance(c, str):
                        try:
                            res.append(ReasonCode(c))
                        except ValueError:
                            pass
            return res

        dq_raw = data.get("data_quality", {})
        dq = DataQualityRecord.from_dict(dq_raw) if isinstance(dq_raw, dict) else dq_raw

        return cls(
            pulse_valid=bool(data.get("pulse_valid", False)),
            admissible_for_r0=bool(data.get("admissible_for_r0", False)),
            admissible_for_chemistry=bool(data.get("admissible_for_chemistry", False)),
            configured_i_min=float(data.get("configured_i_min", 0.0)),
            mean_pulse_current_a=float(data.get("mean_pulse_current_a", 0.0)),
            current_margin_a=float(data.get("current_margin_a", 0.0)),
            duration_s=float(data.get("duration_s", 0.0)),
            delta_v_ohmic=float(data["delta_v_ohmic"]) if data.get("delta_v_ohmic") is not None else None,
            delta_v_total=float(data["delta_v_total"]) if data.get("delta_v_total") is not None else None,
            delta_i=float(data.get("delta_i", 0.0)),
            hardware_tripped=bool(data.get("hardware_tripped", False)),
            contactor_open=bool(data.get("contactor_open", False)),
            data_quality=dq,
            reason_codes=_parse_reasons(data.get("reason_codes", [])),
            details=dict(data.get("details", {}))
        )
