"""
Relaxation Feature Extractor (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Extracts post-excitation open-circuit relaxation features:
- RELAXATION_DELTA_V
- RELAXATION_SLOPE_DV_DT

Causality Rule:
- Strictly causal: only past and current samples in the relaxation segment are consumed.
"""

from typing import Dict, Any, List, Optional
import math

from secondshift.interfaces.qualification_schema import DerivedFeature
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.software.features.feature_metadata import FeatureDefinition
from secondshift.software.features.extractors.base import BaseFeatureExtractor


class RelaxationFeatureExtractor(BaseFeatureExtractor):
    """Deterministic extractor for open-circuit voltage relaxation dynamics."""

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

        if not samples or len(samples) < definition.min_samples:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Insufficient relaxation samples: {len(samples)} < {definition.min_samples}",
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

        # Check for sensor invalidity
        for s in samples:
            if s.get("is_valid") is False or s.get("sensor_valid") is False:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Relaxation stream contains invalid sensor samples"
                )

        # Check current: must be approximately zero (< 0.1 A) during relaxation
        currents = [_get_float(s, "current_a", "current") for s in samples]
        valid_c = [c for c in currents if c is not None]
        if valid_c and max(abs(c) for c in valid_c) > 0.15:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Active current detected during relaxation: max |I| = {max(abs(c) for c in valid_c):.3f}A > 0.15A"
            )

        voltages = [_get_float(s, "voltage_v", "voltage") for s in samples]
        if any(v is None for v in voltages):
            return self.build_invalid_feature(definition, session_id, segment_id, tp, "Missing voltage in relaxation stream")

        valid_v = [v for v in voltages if v is not None]
        v_start = valid_v[0]
        v_end = valid_v[-1]

        # Timestamp span check
        timestamps = [_get_float(s, "timestamp", "timestamp_s", "t_rel", "timestamp_monotonic") for s in samples]
        if any(t is None for t in timestamps):
            return self.build_invalid_feature(definition, session_id, segment_id, tp, "Missing timestamps in relaxation stream")

        valid_t = [t for t in timestamps if t is not None]
        dt = valid_t[-1] - valid_t[0]

        if dt < definition.min_duration_s:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Relaxation duration insufficient: {dt:.2f}s < {definition.min_duration_s:.2f}s"
            )

        f_id = definition.feature_id

        if f_id == "RELAXATION_DELTA_V":
            computed = abs(v_end - v_start)
        elif f_id == "RELAXATION_SLOPE_DV_DT":
            if dt <= 1e-4:
                return self.build_invalid_feature(definition, session_id, segment_id, tp, "Near-zero time elapsed in slope computation")
            # Causal slope: endpoint differential
            computed = (v_end - v_start) / dt
        else:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Unsupported relaxation feature: {f_id}",
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
