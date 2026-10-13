"""
Thermal Feature Extractor (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Extracts surface thermal state, rise, and rate features:
- T_MEAN
- T_MAX
- DELTA_T
- DT_DT

Special Warning (Section 43):
- Thermal features serve strictly as SAFETY, ANOMALY, and CONTEXT indicators.
- In RMK REVOLT empirical testing, thermal sensing did not improve RUL prediction.
- Therefore, thermal features are NOT promoted to prognostic features without evidence.
"""

from typing import Dict, Any, List, Optional
import math

from secondshift.interfaces.qualification_schema import DerivedFeature
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.software.features.feature_metadata import FeatureDefinition
from secondshift.software.features.extractors.base import BaseFeatureExtractor


class ThermalFeatureExtractor(BaseFeatureExtractor):
    """Deterministic extractor for thermal state and rise rate."""

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
                f"Insufficient thermal samples: {len(samples)} < {definition.min_samples}",
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
                    "Thermal stream contains invalid sensor samples",
                    measurement_scope=scope,
                    context=ctx
                )

        temperatures = [_get_float(s, "temperature_c", "temperature") for s in samples]
        if any(t is None for t in temperatures):
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                "Missing or non-finite temperature sample",
                measurement_scope=scope,
                context=ctx
            )

        valid_t = [t for t in temperatures if t is not None]
        f_id = definition.feature_id

        if f_id == "T_MEAN":
            computed = sum(valid_t) / len(valid_t)
        elif f_id == "T_MAX":
            computed = max(valid_t)
        elif f_id == "DELTA_T":
            computed = valid_t[-1] - valid_t[0]
        elif f_id == "DT_DT":
            timestamps = [_get_float(s, "timestamp", "timestamp_s", "t_rel", "timestamp_monotonic") for s in samples]
            if any(ts is None for ts in timestamps):
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Missing timestamps for thermal derivative",
                    measurement_scope=scope,
                    context=ctx
                )
            
            valid_ts = [ts for ts in timestamps if ts is not None]
            dt = valid_ts[-1] - valid_ts[0]
            if dt < definition.min_duration_s or dt <= 1e-4:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    f"Thermal duration insufficient for dT/dt: {dt:.2f}s < {definition.min_duration_s:.2f}s",
                    measurement_scope=scope,
                    context=ctx
                )
            # Causal slope: endpoint differential
            computed = (valid_t[-1] - valid_t[0]) / dt
        else:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Unsupported thermal feature: {f_id}",
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
