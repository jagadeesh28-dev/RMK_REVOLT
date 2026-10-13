"""
Energy Feature Extractor (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Extracts electrical energy integration and efficiency features:
- CHARGE_WH
- DISCHARGE_WH
- ENERGY_EFFICIENCY
"""

from typing import Dict, Any, List, Optional
import math

from secondshift.interfaces.qualification_schema import DerivedFeature
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.software.features.feature_metadata import FeatureDefinition
from secondshift.software.features.extractors.base import BaseFeatureExtractor


class EnergyFeatureExtractor(BaseFeatureExtractor):
    """Deterministic extractor for electrical energy and round-trip efficiency."""

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

        # ENERGY_EFFICIENCY: Ratio of discharge Wh to charge Wh
        if f_id == "ENERGY_EFFICIENCY":
            charge_wh = ctx.get("charge_wh")
            discharge_wh = ctx.get("discharge_wh")

            if charge_wh is None or discharge_wh is None:
                charge_wh, discharge_wh = self._integrate_energy(samples)

            if charge_wh is None or discharge_wh is None:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Incomplete cycle data: requires both charge and discharge energy for efficiency calculation",
                    measurement_scope=scope,
                    context=ctx
                )

            if charge_wh <= 0.1:  # Denominator threshold
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    f"Denominator near-zero or insufficient charge energy: {charge_wh:.4f} Wh <= 0.1 Wh",
                    measurement_scope=scope,
                    context=ctx
                )

            computed = discharge_wh / charge_wh

        elif f_id in ("CHARGE_WH", "DISCHARGE_WH"):
            if not samples or len(samples) < definition.min_samples:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    f"Insufficient samples for energy integration: {len(samples)} < {definition.min_samples}",
                    measurement_scope=scope,
                    context=ctx
                )

            ch_wh, dis_wh = self._integrate_energy(samples)
            if f_id == "CHARGE_WH":
                computed = ch_wh
            else:
                computed = dis_wh

            if computed is None:
                return self.build_invalid_feature(
                    definition, session_id, segment_id, tp,
                    "Energy integration failed",
                    measurement_scope=scope,
                    context=ctx
                )
        else:
            return self.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Unsupported energy feature: {f_id}",
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
    def _integrate_energy(samples: List[Dict[str, Any]]) -> Tuple_OptFloat_OptFloat:
        """
        Integrates charge and discharge Watt-hours using trapezoidal rule.
        Returns (charge_wh, discharge_wh).
        """
        if len(samples) < 2:
            return None, None

        def _get_ts(s: Dict[str, Any]) -> Optional[float]:
            for k in ("timestamp", "timestamp_s", "t_rel", "timestamp_monotonic"):
                if k in s and s[k] is not None:
                    return float(s[k])
            return None

        def _get_v(s: Dict[str, Any]) -> Optional[float]:
            for k in ("voltage_v", "voltage"):
                if k in s and s[k] is not None:
                    val = float(s[k])
                    if not math.isnan(val) and not math.isinf(val):
                        return val
            return None

        def _get_i(s: Dict[str, Any]) -> Optional[float]:
            for k in ("current_a", "current"):
                if k in s and s[k] is not None:
                    val = float(s[k])
                    if not math.isnan(val) and not math.isinf(val):
                        return val
            return None

        charge_ws = 0.0
        discharge_ws = 0.0

        for idx in range(len(samples) - 1):
            s0, s1 = samples[idx], samples[idx + 1]
            t0, t1 = _get_ts(s0), _get_ts(s1)
            v0, v1 = _get_v(s0), _get_v(s1)
            i0, i1 = _get_i(s0), _get_i(s1)

            if None in (t0, t1, v0, v1, i0, i1):
                continue

            dt = t1 - t0
            if dt <= 0 or dt > 3600.0:
                continue

            p0 = v0 * i0
            p1 = v1 * i1
            p_mid = 0.5 * (p0 + p1)

            if p_mid > 0:
                discharge_ws += p_mid * dt
            elif p_mid < 0:
                charge_ws += abs(p_mid) * dt

        return charge_ws / 3600.0, discharge_ws / 3600.0


# Helper type
Tuple_OptFloat_OptFloat = tuple[Optional[float], Optional[float]]
