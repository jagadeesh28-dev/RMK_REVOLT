"""
Data Quality & Meta-Feature Extractor (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Extracts measurement reliability and completeness indicators:
- VALID_SAMPLE_FRACTION
- INVALID_SAMPLE_FRACTION
- CURRENT_FLOW_VALID
- PULSE_VALID
- TIMESTAMP_INTEGRITY
- MEASUREMENT_DURATION

Strict Principle (Section 15):
- Feature quality quantifies sensor and measurement reliability ONLY.
- It is NEVER model confidence or probability that RUL is correct.
"""

from typing import Dict, Any, List, Optional
import math

from secondshift.interfaces.qualification_schema import DerivedFeature
from secondshift.interfaces.data_quality_schema import DataQualityState, PulseValidationRecord
from secondshift.software.features.feature_metadata import FeatureDefinition
from secondshift.software.features.extractors.base import BaseFeatureExtractor


class DataQualityFeatureExtractor(BaseFeatureExtractor):
    """Deterministic extractor for telemetry data quality and completeness."""

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

        if not samples and definition.feature_id != "PULSE_VALID":
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                "No samples in observation window",
                measurement_scope=scope,
                context=ctx
            )

        f_id = definition.feature_id

        # VALID_SAMPLE_FRACTION / INVALID_SAMPLE_FRACTION
        if f_id in ("VALID_SAMPLE_FRACTION", "INVALID_SAMPLE_FRACTION"):
            n_total = len(samples)
            if n_total == 0:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Window is empty",
                    measurement_scope=scope,
                    context=ctx
                )

            n_valid = 0
            for s in samples:
                is_val = s.get("is_valid", True) and s.get("sensor_valid", True)
                # Check for NaNs
                for v in s.values():
                    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                        is_val = False
                        break
                if is_val:
                    n_valid += 1

            if f_id == "VALID_SAMPLE_FRACTION":
                computed = float(n_valid) / float(n_total)
            else:
                computed = float(n_total - n_valid) / float(n_total)

        # CURRENT_FLOW_VALID
        elif f_id == "CURRENT_FLOW_VALID":
            min_i = float(ctx.get("i_min_pulse_a", 1.0))
            currents = []
            for s in samples:
                for k in ("current_a", "current"):
                    if k in s and s[k] is not None:
                        currents.append(abs(float(s[k])))
                        break
            if not currents:
                computed = 0.0
            else:
                mean_i = sum(currents) / len(currents)
                computed = 1.0 if mean_i >= min_i else 0.0

        # PULSE_VALID
        elif f_id == "PULSE_VALID":
            val_rec: Optional[PulseValidationRecord] = ctx.get("validation_record")
            if val_rec is not None:
                computed = 1.0 if val_rec.pulse_valid else 0.0
            elif "pulse_valid" in ctx:
                computed = 1.0 if ctx["pulse_valid"] else 0.0
            else:
                # If no pulse validation record, check if samples satisfy current step
                min_i = float(ctx.get("i_min_pulse_a", 1.0))
                currents = [abs(float(s.get("current_a", s.get("current", 0.0)))) for s in samples]
                computed = 1.0 if (currents and (sum(currents) / len(currents)) >= min_i) else 0.0

        # TIMESTAMP_INTEGRITY
        elif f_id == "TIMESTAMP_INTEGRITY":
            if len(samples) < 2:
                computed = 1.0
            else:
                timestamps = []
                for s in samples:
                    for k in ("timestamp", "timestamp_s", "t_rel", "timestamp_monotonic"):
                        if k in s and s[k] is not None:
                            timestamps.append(float(s[k]))
                            break
                if len(timestamps) < len(samples):
                    computed = 0.0
                else:
                    monotonic = all(timestamps[i] < timestamps[i + 1] for i in range(len(timestamps) - 1))
                    computed = 1.0 if monotonic else 0.0

        # MEASUREMENT_DURATION
        elif f_id == "MEASUREMENT_DURATION":
            timestamps = []
            for s in samples:
                for k in ("timestamp", "timestamp_s", "t_rel", "timestamp_monotonic"):
                    if k in s and s[k] is not None:
                        timestamps.append(float(s[k]))
                        break
            if not timestamps:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "No timestamps available for duration",
                    measurement_scope=scope,
                    context=ctx
                )
            dt = timestamps[-1] - timestamps[0]
            if dt < 0.0:
                # Strict: NO silent clipping of inverted timestamps to 0.0!
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    f"Non-physical negative duration: dt={dt:.4f}s (inverted timestamps)",
                    measurement_scope=scope,
                    context=ctx
                )
            computed = dt

        else:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Unsupported data quality feature: {f_id}",
                measurement_scope=scope,
                context=ctx
            )

        ok, reason = definition.physical_bounds.validate(computed, scope=scope, series_cells=series_cells)
        if not ok:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Physical bounds violation: {reason}",
                measurement_scope=scope,
                context=ctx
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
            context=dict(ctx)
        )
