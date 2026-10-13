"""
Telemetry & Scientific Measurement Validation Engine (Layer 2 / 3)
Project: RMK-REVOLT / SECONDShift Platform

Enforces strict, non-negotiable validation of incoming telemetry frames and diagnostic pulses.
Invariants:
- NEVER silently repair or substitute corrupt values.
- Reject NaN, Infinity, physical range violations, and stale frames.
- Distinguish SENSOR VALIDITY from INFERENCE ADMISSIBILITY.
- Require verified current flow (|I| >= I_MIN) before diagnostic pulse inference is permitted.
- Return structured fault diagnostics with explicit error and reason codes.
"""

import math
import time
from dataclasses import dataclass, field, replace
from typing import List, Dict, Any, Optional

from .telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus
)
from .epistemic_schema import ReasonCode
from .data_quality_schema import (
    DataQualityRecord,
    PulseValidationRecord,
    DataQualityState,
    EventClassification
)
from secondshift.config.validation_config import MeasurementValidationConfig


@dataclass
class TelemetryValidationResult:
    """Structured result of telemetry frame validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality: str = TelemetryQuality.VALID.value
    rejected_fields: List[str] = field(default_factory=list)
    validated_frame: Optional[TelemetryFrame] = None
    data_quality_record: Optional[DataQualityRecord] = None


class TelemetryValidator:
    """
    Validates physical feasibility, integrity, and inference admissibility
    of battery telemetry frames and diagnostic pulse events.
    Does NOT modify input data.
    """
    def __init__(
        self,
        v_min_module: Optional[float] = None,
        v_max_module: Optional[float] = None,
        v_min_cell: Optional[float] = None,
        v_max_cell: Optional[float] = None,
        i_min_a: Optional[float] = None,
        i_max_a: Optional[float] = None,
        temp_min_c: Optional[float] = None,
        temp_max_c: Optional[float] = None,
        max_stale_age_s: Optional[float] = None,
        i_min_pulse_a: Optional[float] = None,
        min_pulse_duration_s: Optional[float] = None,
        config: Optional[MeasurementValidationConfig] = None
    ):
        self.config = config or MeasurementValidationConfig()
        self.config_version = self.config.config_version

        self.v_min_mod = v_min_module if v_min_module is not None else self.config.v_min_module_v
        self.v_max_mod = v_max_module if v_max_module is not None else self.config.v_max_module_v
        self.v_min_cell = v_min_cell if v_min_cell is not None else self.config.v_min_cell_v
        self.v_max_cell = v_max_cell if v_max_cell is not None else self.config.v_max_cell_v
        self.i_min = i_min_a if i_min_a is not None else self.config.i_min_a
        self.i_max = i_max_a if i_max_a is not None else self.config.i_max_a
        self.temp_min = temp_min_c if temp_min_c is not None else self.config.temp_min_c
        self.temp_max = temp_max_c if temp_max_c is not None else self.config.temp_max_c
        self.max_stale_age_s = max_stale_age_s if max_stale_age_s is not None else self.config.max_stale_age_s
        self.i_min_pulse = i_min_pulse_a if i_min_pulse_a is not None else self.config.i_min_pulse_a
        self.min_pulse_duration_s = min_pulse_duration_s if min_pulse_duration_s is not None else self.config.min_pulse_duration_s
        self.future_skew_tolerance_s = self.config.future_skew_tolerance_s

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
        reason_codes: List[ReasonCode] = []
        quality = TelemetryQuality.VALID.value

        now = current_time if current_time is not None else time.time()

        # 0. NULL CHECK
        if frame is None:
            reason_codes.append(ReasonCode.MEASUREMENT_INVALID)
            dq = DataQualityRecord(
                timestamp=now,
                timestamp_valid=False,
                sensor_valid=False,
                telemetry_complete=False,
                communication_fault=True,
                measurement_admissible=False,
                quality_state=DataQualityState.INVALID.value,
                event_classification=EventClassification.SENSOR_FAULT.value,
                reason_codes=reason_codes
            )
            return TelemetryValidationResult(
                valid=False,
                errors=["ERR_COMM_01: Telemetry frame is None (Link Disconnected / Dropout)"],
                warnings=[],
                quality=TelemetryQuality.COMMUNICATION_FAULT.value,
                rejected_fields=["frame"],
                validated_frame=None,
                data_quality_record=dq
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
        voltage_valid = True
        current_valid = True
        temperature_valid = True

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
                    if "voltage" in field_name:
                        voltage_valid = False
                    elif "current" in field_name:
                        current_valid = False
                    elif "temperature" in field_name:
                        temperature_valid = False
                elif math.isinf(val):
                    errors.append(f"ERR_NUM_02: Field '{field_name}' contains Infinity")
                    rejected_fields.append(field_name)
                    if "voltage" in field_name:
                        voltage_valid = False
                    elif "current" in field_name:
                        current_valid = False
                    elif "temperature" in field_name:
                        temperature_valid = False

        for idx, cv in enumerate(frame.cell_voltages_v):
            if math.isnan(cv) or math.isinf(cv):
                errors.append(f"ERR_NUM_03: cell_voltages_v[{idx}] contains NaN or Inf ({cv})")
                rejected_fields.append(f"cell_voltages_v[{idx}]")
                voltage_valid = False

        for idx, ct in enumerate(frame.cell_temperatures_c):
            if math.isnan(ct) or math.isinf(ct):
                errors.append(f"ERR_NUM_04: cell_temperatures_c[{idx}] contains NaN or Inf ({ct})")
                rejected_fields.append(f"cell_temperatures_c[{idx}]")
                temperature_valid = False

        # 3. PHYSICAL RANGE VIOLATIONS
        range_fault = False
        if frame.voltage_v is not None and "voltage_v" not in rejected_fields:
            if frame.voltage_v < self.v_min_mod or frame.voltage_v > self.v_max_mod:
                errors.append(f"ERR_RANGE_01: Module voltage {frame.voltage_v:.3f}V outside [{self.v_min_mod}, {self.v_max_mod}]V")
                rejected_fields.append("voltage_v")
                quality = TelemetryQuality.OUT_OF_RANGE.value
                voltage_valid = False
                range_fault = True

        for idx, cv in enumerate(frame.cell_voltages_v):
            if cv < self.v_min_cell or cv > self.v_max_cell:
                errors.append(f"ERR_RANGE_02: Cell {idx} voltage {cv:.3f}V outside [{self.v_min_cell}, {self.v_max_cell}]V")
                rejected_fields.append(f"cell_voltages_v[{idx}]")
                quality = TelemetryQuality.OUT_OF_RANGE.value
                voltage_valid = False
                range_fault = True

        if frame.current_a is not None and "current_a" not in rejected_fields:
            if frame.current_a < self.i_min or frame.current_a > self.i_max:
                errors.append(f"ERR_RANGE_03: Current {frame.current_a:.2f}A outside [{self.i_min}, {self.i_max}]A")
                rejected_fields.append("current_a")
                quality = TelemetryQuality.OUT_OF_RANGE.value
                current_valid = False
                range_fault = True

        if frame.temperature_c is not None and "temperature_c" not in rejected_fields:
            if frame.temperature_c < self.temp_min or frame.temperature_c > self.temp_max:
                errors.append(f"ERR_RANGE_04: Temperature {frame.temperature_c:.1f}°C outside [{self.temp_min}, {self.temp_max}]°C")
                rejected_fields.append("temperature_c")
                quality = TelemetryQuality.OUT_OF_RANGE.value
                temperature_valid = False
                range_fault = True

        # 4. SENSOR HEALTH FLAGS
        sensor_fault = False
        for sens_name, sens_st in frame.sensor_status.items():
            if sens_st in [SensorHealthStatus.FAULT.value, SensorHealthStatus.UNAVAILABLE.value]:
                errors.append(f"ERR_SENS_01: Sensor '{sens_name}' status is {sens_st}")
                rejected_fields.append(f"sensor_status.{sens_name}")
                quality = TelemetryQuality.SENSOR_FAULT.value
                sensor_fault = True
                reason_codes.append(ReasonCode.SENSOR_FAULT)
            elif sens_st == SensorHealthStatus.DEGRADED.value:
                warnings.append(f"WARN_SENS_01: Sensor '{sens_name}' is degraded")
                reason_codes.append(ReasonCode.DATA_QUALITY_DEGRADED)

        # 5. COMMUNICATION STATUS
        comm_fault = False
        if frame.communication_status in [CommunicationStatus.DISCONNECTED.value, CommunicationStatus.DROPOUT.value]:
            errors.append(f"ERR_COMM_01: Communication status indicates fault: {frame.communication_status}")
            quality = TelemetryQuality.COMMUNICATION_FAULT.value
            comm_fault = True
            reason_codes.append(ReasonCode.MEASUREMENT_INVALID)
        elif frame.communication_status == CommunicationStatus.DEGRADED.value:
            warnings.append("WARN_COMM_01: Communication link is degraded")

        # 6. TEMPORAL INTEGRITY (Staleness & Future Drift)
        stale_data = False
        timestamp_valid = True
        if not allow_stale_for_replay:
            age = now - frame.timestamp
            if age > self.max_stale_age_s:
                errors.append(f"ERR_TIME_01: Telemetry frame is STALE (age={age:.2f}s > {self.max_stale_age_s}s)")
                quality = TelemetryQuality.STALE.value
                stale_data = True
                reason_codes.append(ReasonCode.TELEMETRY_STALE)
            elif age < -self.future_skew_tolerance_s: # Future timestamp (Clock Skew)
                errors.append(f"ERR_TIME_02: Telemetry timestamp is in the future by {abs(age):.2f}s (Clock Skew > {self.future_skew_tolerance_s:.1f}s)")
                quality = TelemetryQuality.STALE.value
                timestamp_valid = False
                reason_codes.append(ReasonCode.TIMESTAMP_INVERSION)

        # 7. SEQUENCE NUMBER CONTINUITY
        sequence_valid = True
        if self._last_seq is not None:
            expected_seq = self._last_seq + 1
            if frame.sequence_number == self._last_seq:
                warnings.append(f"WARN_SEQ_01: Duplicate sequence number detected ({frame.sequence_number})")
                reason_codes.append(ReasonCode.DUPLICATE_TIMESTAMP)
            elif frame.sequence_number < self._last_seq:
                errors.append(f"ERR_SEQ_01: Sequence number regression ({frame.sequence_number} < {self._last_seq})")
                quality = TelemetryQuality.COMMUNICATION_FAULT.value
                sequence_valid = False
            elif frame.sequence_number > expected_seq:
                dropped = frame.sequence_number - expected_seq
                warnings.append(f"WARN_SEQ_02: Sequence gap detected (expected {expected_seq}, got {frame.sequence_number}; {dropped} frames dropped)")
                reason_codes.append(ReasonCode.SEQUENCE_GAP_DETECTED)

        self._last_seq = frame.sequence_number
        self._last_seen_time = now

        # 8. FINAL DECISION
        is_valid = len(errors) == 0

        # Create non-mutating copy of frame with updated quality flags
        if not is_valid:
            new_flags = list(set(frame.quality_flags + [quality]))
        else:
            new_flags = [TelemetryQuality.VALID.value]
        validated_frame = replace(frame, quality_flags=new_flags)

        sensor_healthy = (not sensor_fault) and voltage_valid and current_valid and temperature_valid

        dq_record = DataQualityRecord(
            timestamp=frame.timestamp,
            timestamp_valid=timestamp_valid,
            sequence_valid=sequence_valid,
            voltage_valid=voltage_valid,
            current_valid=current_valid,
            temperature_valid=temperature_valid,
            sensor_valid=sensor_healthy,
            telemetry_complete=(len(rejected_fields) == 0),
            stale_data=stale_data,
            communication_fault=comm_fault,
            range_fault=range_fault,
            noise_fault=False,
            current_flow_valid=abs(frame.current_a or 0.0) >= self.i_min_pulse,
            pulse_valid=False, # Single frames are not pulses
            measurement_admissible=is_valid and sensor_healthy,
            quality_state=DataQualityState.VALID.value if is_valid else (
                DataQualityState.DEGRADED.value if len(warnings) > 0 and len(errors) == 0 else DataQualityState.INVALID.value
            ),
            event_classification=EventClassification.NORMAL_OPERATION.value if is_valid else EventClassification.SENSOR_FAULT.value,
            configured_i_min=self.i_min_pulse,
            observed_current=abs(frame.current_a or 0.0),
            current_margin=abs(frame.current_a or 0.0) - self.i_min_pulse,
            reason_codes=reason_codes,
            validation_details={
                "config_version": self.config_version,
                "errors": errors,
                "warnings": warnings,
                "rejected_fields": rejected_fields
            }
        )

        return TelemetryValidationResult(
            valid=is_valid,
            errors=errors,
            warnings=warnings,
            quality=quality if not is_valid else TelemetryQuality.VALID.value,
            rejected_fields=rejected_fields,
            validated_frame=validated_frame,
            data_quality_record=dq_record
        )

    # Alias for convenience
    validate_frame = validate_telemetry

    def validate_diagnostic_pulse(
        self,
        pre_pulse_sample: Any,
        pulse_samples: List[Any],
        post_pulse_sample: Optional[Any] = None,
        required_i_min_a: Optional[float] = None,
        min_duration_s: Optional[float] = None,
        hardware_tripped: bool = False,
        contactor_open: bool = False
    ) -> PulseValidationRecord:
        """
        Validates whether a diagnostic pulse physically occurred and is admissible
        for downstream State of Health, Ohmic R0, or Chemistry updates.

        Enforces:
        - Actual current flow |I| >= I_MIN
        - Positive duration and strictly chronological timestamps
        - Zero hardware trips or unexpected contactor openings during pulse
        - Clean pre-pulse resting condition
        """
        i_min = required_i_min_a if required_i_min_a is not None else self.i_min_pulse
        min_dur = min_duration_s if min_duration_s is not None else self.min_pulse_duration_s

        errors: List[str] = []
        reasons: List[ReasonCode] = []

        def _extract(sample: Any, field_name: str, alt_name: str, default: float = 0.0) -> float:
            if isinstance(sample, dict):
                v = sample.get(field_name, sample.get(alt_name, default))
            elif hasattr(sample, field_name):
                v = getattr(sample, field_name)
            elif hasattr(sample, alt_name):
                v = getattr(sample, alt_name)
            else:
                v = default
            return float(v) if v is not None and math.isfinite(v) else default

        def _is_finite_num(sample: Any, field_name: str, alt_name: str, required: bool = True) -> bool:
            if isinstance(sample, dict):
                v = sample.get(field_name, sample.get(alt_name))
            elif hasattr(sample, field_name):
                v = getattr(sample, field_name)
            elif hasattr(sample, alt_name):
                v = getattr(sample, alt_name)
            else:
                v = None
            if v is None and not required:
                return True
            return v is not None and not math.isnan(v) and not math.isinf(v)

        # 1. PRE-PULSE VALIDATION
        if pre_pulse_sample is None or not _is_finite_num(pre_pulse_sample, "voltage", "voltage_v"):
            errors.append("ERR_PULSE_01: Missing or invalid pre-pulse voltage sample")
            reasons.append(ReasonCode.MEASUREMENT_INVALID)
            v_pre = 0.0
        else:
            v_pre = _extract(pre_pulse_sample, "voltage", "voltage_v")
            if v_pre < self.v_min_mod or v_pre > self.v_max_mod:
                errors.append(f"ERR_PULSE_02: Pre-pulse voltage {v_pre:.3f}V outside limits")
                reasons.append(ReasonCode.MEASUREMENT_INVALID)

        # 2. HARDWARE / CONTACTOR TRIPS
        if hardware_tripped:
            errors.append("ERR_HW_01: Hardware protection layer tripped during diagnostic pulse")
            reasons.append(ReasonCode.HARDWARE_TRIP_DURING_TEST)

        if contactor_open:
            errors.append("ERR_HW_02: Power contactors opened during diagnostic pulse (No Current Flow)")
            reasons.append(ReasonCode.CONTACTOR_OPEN_FAULT)

        # 3. PULSE SAMPLES VALIDATION
        if not pulse_samples or len(pulse_samples) < 2:
            errors.append("ERR_PULSE_03: Insufficient pulse sampling points (need >= 2)")
            reasons.append(ReasonCode.TRANSIENT_DURATION_INSUFFICIENT)
            pulse_samples = pulse_samples or []

        currents: List[float] = []
        voltages: List[float] = []
        timestamps: List[float] = []

        last_t = -1e9
        for idx, s in enumerate(pulse_samples):
            # Check for NaN / Inf
            if not _is_finite_num(s, "voltage", "voltage_v", required=True):
                errors.append(f"ERR_PULSE_04: Pulse sample {idx} contains NaN/Inf voltage")
                reasons.append(ReasonCode.SENSOR_FAULT)
            if not _is_finite_num(s, "current", "current_a", required=True):
                errors.append(f"ERR_PULSE_05: Pulse sample {idx} contains NaN/Inf current")
                reasons.append(ReasonCode.SENSOR_FAULT)
            if not _is_finite_num(s, "temperature", "temperature_c", required=False):
                errors.append(f"ERR_PULSE_06: Pulse sample {idx} contains NaN/Inf temperature")
                reasons.append(ReasonCode.SENSOR_FAULT)

            t_val = _extract(s, "t_rel", "timestamp", default=0.0)
            if idx > 0 and t_val < last_t:
                errors.append(f"ERR_TIME_03: Timestamp inversion detected ({t_val:.4f} < {last_t:.4f})")
                reasons.append(ReasonCode.TIMESTAMP_INVERSION)
            elif idx > 0 and t_val == last_t:
                reasons.append(ReasonCode.DUPLICATE_TIMESTAMP)

            last_t = t_val
            timestamps.append(t_val)
            currents.append(abs(_extract(s, "current", "current_a")))
            voltages.append(_extract(s, "voltage", "voltage_v"))

        # 4. TEMPORAL DURATION
        duration_s = (timestamps[-1] - timestamps[0]) if len(timestamps) >= 2 else 0.0
        if duration_s < min_dur:
            errors.append(f"ERR_PULSE_07: Pulse duration {duration_s:.3f}s is below minimum {min_dur:.3f}s")
            reasons.append(ReasonCode.TRANSIENT_DURATION_INSUFFICIENT)

        # 5. CURRENT FLOW FEASIBILITY
        mean_current_a = (sum(currents) / len(currents)) if currents else 0.0
        current_margin = mean_current_a - i_min

        if mean_current_a < i_min:
            errors.append(
                f"ERR_CURR_01: Observed mean pulse current {mean_current_a:.3f}A is below minimum required {i_min:.3f}A"
            )
            reasons.append(ReasonCode.CURRENT_FLOW_BELOW_MINIMUM)

        # 6. TRANSIENT DELTAS
        # 6. ADMISSIBILITY DETERMINATION
        pulse_valid = (len(errors) == 0) and (not hardware_tripped) and (not contactor_open) and (mean_current_a >= i_min)

        if pulse_valid:
            reasons.append(ReasonCode.PULSE_VALID)
            admissible_for_r0 = True
            admissible_for_chem = True
            v_immediate = voltages[1] if len(voltages) > 1 else (voltages[0] if voltages else v_pre)
            v_end = voltages[-1] if voltages else v_pre
            delta_v_ohmic = abs(v_pre - v_immediate)
            delta_v_total = abs(v_pre - v_end)
        else:
            reasons.append(ReasonCode.PULSE_INVALID)
            admissible_for_r0 = False
            admissible_for_chem = False
            delta_v_ohmic = None
            delta_v_total = None

        delta_i = mean_current_a

        dq = DataQualityRecord(
            timestamp=timestamps[0] if timestamps else time.time(),
            timestamp_valid=ReasonCode.TIMESTAMP_INVERSION not in reasons,
            sequence_valid=True,
            voltage_valid=ReasonCode.SENSOR_FAULT not in reasons,
            current_valid=ReasonCode.SENSOR_FAULT not in reasons,
            temperature_valid=ReasonCode.SENSOR_FAULT not in reasons,
            sensor_valid=ReasonCode.SENSOR_FAULT not in reasons,
            telemetry_complete=(len(pulse_samples) >= 2),
            stale_data=False,
            communication_fault=False,
            range_fault=False,
            noise_fault=False,
            current_flow_valid=mean_current_a >= i_min,
            pulse_valid=pulse_valid,
            admissible_for_r0=admissible_for_r0,
            admissible_for_chemistry=admissible_for_chem,
            measurement_admissible=pulse_valid,
            quality_state=DataQualityState.VALID.value if pulse_valid else DataQualityState.INVALID.value,
            event_classification=EventClassification.DIAGNOSTIC_PULSE.value if not hardware_tripped else EventClassification.HARDWARE_TRIP.value,
            configured_i_min=i_min,
            observed_current=mean_current_a,
            current_margin=current_margin,
            reason_codes=reasons,
            validation_details={
                "config_version": self.config_version,
                "errors": errors,
                "duration_s": duration_s,
                "delta_v_ohmic": delta_v_ohmic,
                "delta_v_total": delta_v_total
            }
        )

        return PulseValidationRecord(
            pulse_valid=pulse_valid,
            admissible_for_r0=admissible_for_r0,
            admissible_for_chemistry=admissible_for_chem,
            configured_i_min=i_min,
            mean_pulse_current_a=mean_current_a,
            current_margin_a=current_margin,
            duration_s=duration_s,
            delta_v_ohmic=delta_v_ohmic,
            delta_v_total=delta_v_total,
            delta_i=delta_i,
            hardware_tripped=hardware_tripped,
            contactor_open=contactor_open,
            data_quality=dq,
            reason_codes=reasons,
            details={
                "config_version": self.config_version,
                "errors": errors,
                "num_samples": len(pulse_samples)
            }
        )
