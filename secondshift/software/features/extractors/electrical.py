"""
Electrical Instantaneous Feature Extractor (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Extracts fundamental electrical features from validated telemetry:
- V_MEAN, V_MIN, V_MAX
- I_MEAN, I_ABS_MEAN, I_PEAK
- P_MEAN, P_PEAK
"""

from typing import Dict, Any, List, Optional
import math

from secondshift.interfaces.qualification_schema import DerivedFeature
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.software.features.feature_metadata import FeatureDefinition
from secondshift.software.features.extractors.base import BaseFeatureExtractor


class ElectricalFeatureExtractor(BaseFeatureExtractor):
    """Deterministic extractor for electrical voltage, current, and power quantities."""

    def extract(
        self,
        definition: FeatureDefinition,
        samples: List[Dict[str, Any]],
        session_id: str = "QUAL_SESSION_DEFAULT",
        segment_id: Optional[str] = None,
        decision_timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> DerivedFeature:
        ctx = context or {}
        scope = ctx.get("measurement_scope", "CELL")
        series_cells = int(ctx.get("series_cells", 1))
        calc_ts = ctx.get("calculation_timestamp")
        tp = self.build_provenance(samples, decision_timestamp, calculation_timestamp=calc_ts)

        if not samples or len(samples) < definition.min_samples:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Insufficient samples: {len(samples)} < {definition.min_samples}",
                measurement_scope=scope,
                context=ctx
            )

        # Helper to extract channels with alias handling
        def _get_val(s: Dict[str, Any], *keys) -> Optional[float]:
            for k in keys:
                if k in s and s[k] is not None:
                    v = s[k]
                    if isinstance(v, (int, float)):
                        fv = float(v)
                        if math.isnan(fv) or math.isinf(fv):
                            return None
                        return fv
            return None

        # Check for sensor corruption or invalid flags in stream
        for s in samples:
            if s.get("is_valid") is False or s.get("sensor_valid") is False:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Observation stream contains flagged invalid sensor samples"
                )

        f_id = definition.feature_id

        # ---------------------------------------------------------------------
        # VOLTAGE FEATURES
        # ---------------------------------------------------------------------
        if f_id in ("V_MEAN", "V_MIN", "V_MAX"):
            voltages = [_get_val(s, "voltage_v", "voltage") for s in samples]
            if any(v is None for v in voltages):
                return self.build_invalid_feature(definition, session_id, segment_id, tp, "Missing or non-finite voltage sample")
            
            valid_v = [v for v in voltages if v is not None]
            if f_id == "V_MEAN":
                computed = sum(valid_v) / len(valid_v)
            elif f_id == "V_MIN":
                computed = min(valid_v)
            else:
                computed = max(valid_v)

        # ---------------------------------------------------------------------
        # CURRENT FEATURES
        # ---------------------------------------------------------------------
        elif f_id in ("I_MEAN", "I_ABS_MEAN", "I_PEAK"):
            currents = [_get_val(s, "current_a", "current") for s in samples]
            if any(c is None for c in currents):
                return self.build_invalid_feature(definition, session_id, segment_id, tp, "Missing or non-finite current sample")
            
            valid_c = [c for c in currents if c is not None]
            if f_id == "I_MEAN":
                computed = sum(valid_c) / len(valid_c)
            elif f_id == "I_ABS_MEAN":
                computed = sum(abs(c) for c in valid_c) / len(valid_c)
            else:
                computed = max(abs(c) for c in valid_c)

        # ---------------------------------------------------------------------
        # POWER FEATURES
        # ---------------------------------------------------------------------
        elif f_id in ("P_MEAN", "P_PEAK"):
            voltages = [_get_val(s, "voltage_v", "voltage") for s in samples]
            currents = [_get_val(s, "current_a", "current") for s in samples]
            if any(v is None for v in voltages) or any(c is None for c in currents):
                return self.build_invalid_feature(definition, session_id, segment_id, tp, "Missing or non-finite voltage/current pair for power")

            powers = [v * c for v, c in zip(voltages, currents) if v is not None and c is not None]
            if f_id == "P_MEAN":
                computed = sum(powers) / len(powers)
            else:
                computed = max(abs(p) for p in powers)

        else:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Unsupported electrical feature: {f_id}",
                measurement_scope=scope,
                context=ctx
            )

        # Physical Bounds Validation (scope-aware)
        ok, reason = definition.physical_bounds.validate(computed, scope=scope, series_cells=series_cells)
        if not ok:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Physical bounds violation: {reason}",
                measurement_scope=scope,
                context=ctx
            )

        quality = DataQualityState.VALID.value
        # If temporal provenance shows future information, transition to INVALID
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
