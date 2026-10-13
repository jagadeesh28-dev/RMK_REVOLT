"""
Coulometric Feature Extractor (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Extracts coulometric charge and capacity features:
- CHARGE_AH
- DISCHARGE_AH
- COULOMBIC_EFFICIENCY

Sign Convention (matching TelemetryFrame):
- Positive current = discharge
- Negative current = charge
"""

from typing import Dict, Any, List, Optional
import math

from secondshift.interfaces.qualification_schema import DerivedFeature
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.software.features.feature_metadata import FeatureDefinition
from secondshift.software.features.extractors.base import BaseFeatureExtractor


class CoulometricFeatureExtractor(BaseFeatureExtractor):
    """Deterministic extractor for coulometric integration and capacity efficiency."""

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

        f_id = definition.feature_id

        # COULOMBIC_EFFICIENCY: Ratio of discharge Ah to charge Ah
        if f_id == "COULOMBIC_EFFICIENCY":
            charge_ah = ctx.get("charge_ah")
            discharge_ah = ctx.get("discharge_ah")

            # If not in context, attempt to integrate from samples if labeled
            if charge_ah is None or discharge_ah is None:
                charge_ah, discharge_ah = self._integrate_cycle(samples)

            if charge_ah is None or discharge_ah is None:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Incomplete cycle data: requires both charge and discharge segments for coulombic efficiency",
                    measurement_scope=scope,
                    context=ctx
                )

            if charge_ah <= 0.05:  # Denominator threshold
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    f"Denominator near-zero or insufficient charge capacity: {charge_ah:.4f} Ah <= 0.05 Ah",
                    measurement_scope=scope,
                    context=ctx
                )

            computed = discharge_ah / charge_ah

        # CHARGE_AH or DISCHARGE_AH: Trapezoidal integration over stream
        elif f_id in ("CHARGE_AH", "DISCHARGE_AH"):
            if not samples or len(samples) < definition.min_samples:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    f"Insufficient samples for integration: {len(samples)} < {definition.min_samples}",
                    measurement_scope=scope,
                    context=ctx
                )

            ch_ah, dis_ah = self._integrate_cycle(samples)
            if f_id == "CHARGE_AH":
                computed = ch_ah
            else:
                computed = dis_ah

            if computed is None:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Coulometric integration failed",
                    measurement_scope=scope,
                    context=ctx
                )
        else:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Unsupported coulometric feature: {f_id}",
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

    @staticmethod
    def _integrate_cycle(samples: List[Dict[str, Any]]) -> Tuple_OptFloat_OptFloat:
        """
        Integrates charge and discharge Ampere-hours using trapezoidal rule.
        Returns (charge_ah, discharge_ah).
        """
        if len(samples) < 2:
            return None, None

        def _get_ts(s: Dict[str, Any]) -> Optional[float]:
            for k in ("timestamp", "timestamp_s", "t_rel", "timestamp_monotonic"):
                if k in s and s[k] is not None:
                    return float(s[k])
            return None

        def _get_i(s: Dict[str, Any]) -> Optional[float]:
            for k in ("current_a", "current"):
                if k in s and s[k] is not None:
                    v = float(s[k])
                    if not math.isnan(v) and not math.isinf(v):
                        return v
            return None

        charge_as = 0.0
        discharge_as = 0.0

        for idx in range(len(samples) - 1):
            s0, s1 = samples[idx], samples[idx + 1]
            t0, t1 = _get_ts(s0), _get_ts(s1)
            i0, i1 = _get_i(s0), _get_i(s1)

            if t0 is None or t1 is None or i0 is None or i1 is None:
                continue

            dt = t1 - t0
            if dt <= 0 or dt > 3600.0:  # Inverted or anomalous time step (> 1 hr)
                continue

            # Average current over interval
            i_mid = 0.5 * (i0 + i1)
            # Positive = discharge, Negative = charge
            if i_mid > 0:
                discharge_as += i_mid * dt
            elif i_mid < 0:
                charge_as += abs(i_mid) * dt

        return charge_as / 3600.0, discharge_as / 3600.0


# Helper type
Tuple_OptFloat_OptFloat = tuple[Optional[float], Optional[float]]
