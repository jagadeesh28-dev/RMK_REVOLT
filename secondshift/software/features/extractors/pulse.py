"""
Pulse Response Feature Extractor (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Extracts transient impedance and voltage response features:
- DELTA_V_TOTAL
- DELTA_V_OHMIC
- R0_OHMIC

Strict Invariant (Phase 2 & 3):
- Invalid pulse, zero current, or hardware trip MUST return value=None, NEVER 0.0 or R0=0.
- Unknown != Zero.
"""

from typing import Dict, Any, List, Optional
import math

from secondshift.interfaces.qualification_schema import DerivedFeature
from secondshift.interfaces.data_quality_schema import DataQualityState, PulseValidationRecord
from secondshift.software.features.feature_metadata import FeatureDefinition
from secondshift.software.features.extractors.base import BaseFeatureExtractor


class PulseFeatureExtractor(BaseFeatureExtractor):
    """Deterministic extractor for pulse impedance and transient polarization features."""

    def extract(
        self,
        definition: FeatureDefinition,
        samples: List[Dict[str, Any]],
        session_id: str = "QUAL_SESSION_DEFAULT",
        segment_id: Optional[str] = None,
        decision_timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> DerivedFeature:
        tp = self.build_provenance(samples, decision_timestamp)
        ctx = context or {}
        scope = ctx.get("measurement_scope", "CELL")
        series_cells = int(ctx.get("series_cells", 1))

        # Check for pre-attached validation record
        val_rec: Optional[PulseValidationRecord] = ctx.get("validation_record")
        if val_rec is not None and not val_rec.pulse_valid:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Diagnostic pulse rejected by Layer 2 validator: {', '.join(rc.value for rc in val_rec.reason_codes)}",
                measurement_scope=scope,
                context=ctx
            )

        # Check direct pulse validity flag in context
        if ctx.get("pulse_valid") is False:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                "Pulse marked invalid in execution context (e.g. current below minimum or contactor open)",
                measurement_scope=scope,
                context=ctx
            )

        if not samples or len(samples) < definition.min_samples:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Insufficient pulse samples: {len(samples)} < {definition.min_samples}",
                measurement_scope=scope,
                context=ctx
            )

        def _get_float(s: Dict[str, Any], *keys) -> Optional[float]:
            for k in keys:
                if k in s and s[k] is not None:
                    try:
                        v = float(s[k])
                        if not math.isnan(v) and not math.isinf(v):
                            return v
                    except (ValueError, TypeError):
                        pass
            return None

        # Check for sensor invalidity in stream
        for s in samples:
            if s.get("is_valid") is False or s.get("sensor_valid") is False:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Pulse stream contains invalid or corrupted sensor samples",
                    measurement_scope=scope,
                    context=ctx
                )

        # Pre-pulse voltage extraction
        v_pre = None
        pre_sample = ctx.get("pre_pulse_sample")
        if pre_sample:
            v_pre = _get_float(pre_sample, "voltage_v", "voltage")
        elif "v_pre" in ctx:
            v_pre = _get_float(ctx, "v_pre")
        else:
            # Fall back to first sample if representing step
            v_pre = _get_float(samples[0], "voltage_v", "voltage")

        if v_pre is None:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                "Pre-pulse baseline voltage unavailable",
                measurement_scope=scope,
                context=ctx
            )

        # Pulse samples
        voltages = [_get_float(s, "voltage_v", "voltage") for s in samples]
        currents = [_get_float(s, "current_a", "current") for s in samples]

        if any(v is None for v in voltages) or any(c is None for c in currents):
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                "Missing or non-finite voltage/current in pulse",
                measurement_scope=scope,
                context=ctx
            )

        valid_v = [v for v in voltages if v is not None]
        valid_c = [c for c in currents if c is not None]

        mean_abs_current = sum(abs(c) for c in valid_c) / len(valid_c)
        min_required_i = float(ctx.get("i_min_pulse_a", 1.0))

        # Extract temperature for contextual provenance
        temps = [_get_float(s, "temperature_c", "temperature") for s in samples]
        valid_temps = [t for t in temps if t is not None]
        mean_temp = (sum(valid_temps) / len(valid_temps)) if valid_temps else ctx.get("temperature_c")

        t_start = samples[0].get("timestamp", 0.0) if samples else 0.0
        t_end = samples[-1].get("timestamp", 0.0) if samples else 0.0
        pulse_dur = abs(t_end - t_start) if (t_end and t_start) else ctx.get("pulse_duration_s")

        mean_raw_i = (sum(valid_c) / len(valid_c)) if valid_c else 0.0
        direction = "CHARGE" if mean_raw_i > 0 else ("DISCHARGE" if mean_raw_i < 0 else "REST")

        # Contextual provenance preserving conditioning parameters
        provenance_ctx = {
            "soc": ctx.get("soc"),
            "temperature_c": mean_temp,
            "pulse_amplitude_a": mean_abs_current,
            "pulse_duration_s": pulse_dur,
            "pre_pulse_rest_s": ctx.get("pre_pulse_rest_s"),
            "post_pulse_rest_s": ctx.get("post_pulse_rest_s"),
            "direction": direction,
            "chemistry_hypothesis": ctx.get("chemistry_hypothesis", "UNKNOWN"),
            "measurement_scope": scope,
            "series_cells": series_cells
        }

        # Strict current flow check: if |I| < I_MIN, pulse is invalid!
        if mean_abs_current < min_required_i:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Current flow below minimum: {mean_abs_current:.3f}A < {min_required_i:.3f}A",
                measurement_scope=scope,
                context=provenance_ctx
            )

        v_end = valid_v[-1]
        v_immediate = valid_v[1] if len(valid_v) > 1 else valid_v[0]

        f_id = definition.feature_id

        # Check temporal resolution for sub-second ohmic features
        if f_id in ["DELTA_V_OHMIC", "R0_OHMIC"]:
            if len(samples) >= 2:
                t0 = samples[0].get("timestamp", 0.0)
                t1 = samples[1].get("timestamp", 0.0)
                sample_dt = abs(t1 - t0)
                if (sample_dt > 0.2 or ctx.get("sampling_rate_hz", 10.0) < 5.0) and ctx.get("require_high_speed_ohmic", False):
                    return self.build_invalid_feature(
                        definition, session_id, segment_id, tp,
                        f"TEMPORALLY_UNAVAILABLE: Sampling interval ({sample_dt:.2f}s) insufficient for sub-second ohmic resolution (requires >= 5Hz)",
                        measurement_scope=scope,
                        context=provenance_ctx
                    )

        if f_id == "DELTA_V_TOTAL":
            computed = abs(v_pre - v_end)
        elif f_id == "DELTA_V_OHMIC":
            computed = abs(v_pre - v_immediate)
        elif f_id == "R0_OHMIC":
            delta_v_ohmic = abs(v_pre - v_immediate)
            if mean_abs_current < 1e-4:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Division by near-zero current for R0",
                    measurement_scope=scope,
                    context=provenance_ctx
                )
            computed = delta_v_ohmic / mean_abs_current
        else:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Unsupported pulse feature: {f_id}",
                measurement_scope=scope,
                context=provenance_ctx
            )

        # Physical bounds check (scope-aware)
        ok, reason = definition.physical_bounds.validate(computed, scope=scope, series_cells=series_cells)
        if not ok:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Physical bounds violation: {reason}",
                measurement_scope=scope,
                context=provenance_ctx
            )

        quality = DataQualityState.VALID.value
        if tp.leakage_status != "AVAILABLE_AT_DECISION_TIME":
            quality = DataQualityState.INVALID.value

        return DerivedFeature(
            feature_name=definition.feature_id,
            feature_version=definition.feature_version,
            value=float(computed),
            unit=definition.units,
            source_session=session_id,
            source_segment=segment_id,
            source_measurements=list(definition.source_measurements),
            temporal_provenance=tp,
            physical_meaning=definition.description,
            expected_direction=definition.directionality.value,
            quality_status=quality,
            configuration_version=definition.configuration_version,
            measurement_scope=scope,
            context=provenance_ctx
        )
