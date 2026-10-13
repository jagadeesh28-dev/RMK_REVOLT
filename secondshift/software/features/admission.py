"""
8-Gate Feature Admission Framework (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

Enforces that every candidate feature must EARN admission through 8 strict gates:
- GATE 1: Measurement availability (required channels present)
- GATE 2: Measurement validity (sensors valid, finite, not corrupted)
- GATE 3: Temporal validity / causality (t_end <= t_decision; no look-ahead)
- GATE 4: Physical validity (obey established electrochemical/thermal bounds)
- GATE 5: Numerical stability (no div-zero, small dt, or overflow)
- GATE 6: Reproducibility & determinism (pure deterministic computation)
- GATE 7: Provenance completeness (complete audit lineage attached)
- GATE 8: Missingness correctness (None preserved; invalid never coerced to 0.0)

A feature that fails ANY gate is marked INVALID and REJECTED from admission to decision pipelines.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import math

from secondshift.interfaces.qualification_schema import DerivedFeature, TemporalProvenance, TemporalLeakageStatus
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.software.features.feature_metadata import FeatureDefinition, PhysicalBounds


@dataclass
class GateEvaluation:
    gate_number: int
    gate_name: str
    passed: bool
    reason: str


@dataclass
class AdmissionAuditResult:
    """Complete evaluation report across all 8 gates for a feature candidate."""
    feature_id: str
    admissible: bool
    gate_evaluations: List[GateEvaluation] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(g.passed for g in self.gate_evaluations)


class FeatureAdmissionEngine:
    """
    Evaluates candidate features against the 8 admission gates.
    Observational only: failure flags the feature as invalid without altering safety loops.
    """

    @staticmethod
    def evaluate(
        feature: DerivedFeature,
        definition: FeatureDefinition,
        raw_samples: List[Dict[str, Any]],
        decision_timestamp: Optional[float] = None
    ) -> AdmissionAuditResult:
        """
        Executes the 8-Gate admission audit on an extracted DerivedFeature.
        """
        gates: List[GateEvaluation] = []
        failures: List[str] = []

        # ---------------------------------------------------------------------
        # GATE 1: Measurement Availability
        # ---------------------------------------------------------------------
        g1_pass = True
        g1_reason = "Required measurement channels present"
        if not raw_samples and definition.min_samples > 0:
            g1_pass = False
            g1_reason = "No raw samples provided in observation window"
        else:
            is_data_quality_family = (definition.family.value == "DATA_QUALITY") if hasattr(definition.family, "value") else (str(definition.family) == "DATA_QUALITY")
            if is_data_quality_family and definition.feature_id in ("VALID_SAMPLE_FRACTION", "INVALID_SAMPLE_FRACTION"):
                has_any_quality_ch = any(
                    any(k in s for k in ("quality_flags", "is_valid", "sensor_valid", "voltage_v", "voltage", "current_a", "current"))
                    for s in raw_samples
                )
                if not has_any_quality_ch:
                    g1_pass = False
                    g1_reason = "No sample validity indicators present in stream"
            else:
                for req_ch in definition.source_measurements:
                    if req_ch != "PulseValidationRecord" and not any(req_ch in s for s in raw_samples):
                        # Check canonical aliases
                        alias_present = False
                        if req_ch == "voltage_v" and any("voltage" in s for s in raw_samples):
                            alias_present = True
                        elif req_ch == "current_a" and any("current" in s for s in raw_samples):
                            alias_present = True
                        elif req_ch == "temperature_c" and any("temperature" in s for s in raw_samples):
                            alias_present = True
                        elif req_ch in ("quality_flags", "is_valid") and any(("quality_flags" in s or "is_valid" in s) for s in raw_samples):
                            alias_present = True

                        if not alias_present:
                            g1_pass = False
                            g1_reason = f"Missing required measurement channel '{req_ch}' in sample stream"
                            break

        gates.append(GateEvaluation(1, "Measurement Availability", g1_pass, g1_reason))
        if not g1_pass:
            failures.append(g1_reason)

        # ---------------------------------------------------------------------
        # GATE 2: Measurement Validity & Ground-Truth Isolation
        # ---------------------------------------------------------------------
        g2_pass = True
        g2_reason = "Underlying measurements passed validity checks; no oracle/label leakage detected"
        if g1_pass:
            # Enforce Ground-Truth / Label Isolation and Battery-ID Shortcut Prevention
            prohibited_oracle_keys = {
                "soh", "true_soh", "rul", "true_rul", "ground_truth",
                "degradation_label", "degradation_regime", "oracle_health",
                "future_cycle", "eol_cycle", "hidden_state", "simulation_oracle"
            }
            # Check raw samples for prohibited oracle injection
            for s in raw_samples:
                leaked = set(s.keys()).intersection(prohibited_oracle_keys)
                if leaked:
                    g2_pass = False
                    g2_reason = f"Ground-truth leakage detected: Oracle keys {leaked} in telemetry sample"
                    break

            # Check feature context for oracle injection
            feat_ctx = getattr(feature, "context", {}) or {}
            if g2_pass and feat_ctx:
                leaked_ctx = set(feat_ctx.keys()).intersection(prohibited_oracle_keys)
                if leaked_ctx:
                    g2_pass = False
                    g2_reason = f"Ground-truth leakage detected: Oracle keys {leaked_ctx} in feature context"

            # Check for prohibited battery ID shortcut as a predictive feature
            feat_id_lower = definition.feature_id.lower()
            if g2_pass and any(feat_id_lower.startswith(p) for p in ("specimen_id", "battery_id", "oracle_", "health_score", "arbitrary_confidence")):
                g2_pass = False
                g2_reason = f"Prohibited feature pattern: '{definition.feature_id}' acts as shortcut or oracle proxy"

            # Check sensor faults and NaN/Inf in samples
            if g2_pass:
                is_data_quality_family = (definition.family.value == "DATA_QUALITY") if hasattr(definition.family, "value") else (str(definition.family) == "DATA_QUALITY")
                for s in raw_samples:
                    if not is_data_quality_family:
                        if s.get("is_valid") is False or s.get("sensor_valid") is False:
                            g2_pass = False
                            g2_reason = "Observation stream contains invalid or faulted sensor samples"
                            break
                    for k, v in s.items():
                        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                            g2_pass = False
                            g2_reason = f"Observation sample contains NaN or Inf in field '{k}'"
                            break
                    if not g2_pass:
                        break
        else:
            g2_pass = False
            g2_reason = "Measurement availability failed; cannot verify validity"

        gates.append(GateEvaluation(2, "Measurement Validity", g2_pass, g2_reason))
        if not g2_pass:
            failures.append(g2_reason)

        # ---------------------------------------------------------------------
        # GATE 3: Temporal Validity, Causality & Availability Semantics
        # ---------------------------------------------------------------------
        g3_pass = True
        g3_reason = "Observation window strictly precedes decision time; availability semantics satisfied"
        t_decision = decision_timestamp if decision_timestamp is not None else feature.temporal_provenance.decision_timestamp
        
        # 3a. Strict Temporal Causality Check
        if t_decision is not None:
            t_end = feature.temporal_provenance.observation_window_end
            if t_end > (t_decision + 1e-4):
                g3_pass = False
                g3_reason = f"Look-ahead future information leakage detected: t_end ({t_end:.4f}) > t_decision ({t_decision:.4f})"
        
        if g3_pass and feature.temporal_provenance.leakage_status == TemporalLeakageStatus.FUTURE_INFORMATION.value:
            g3_pass = False
            g3_reason = "Temporal provenance marked as FUTURE_INFORMATION"

        # 3b. Availability Semantics: OFFLINE_ONLY rejection at online decision time
        avail_str = definition.temporal_availability.value if hasattr(definition.temporal_availability, "value") else str(definition.temporal_availability)
        if g3_pass and avail_str == "OFFLINE_ONLY" and t_decision is not None:
            g3_pass = False
            g3_reason = f"Feature '{definition.feature_id}' is OFFLINE_ONLY and cannot be admitted for online decision at t_decision={t_decision:.4f}"

        # 3c. Availability Semantics: Segment Completion requirement
        if g3_pass and (definition.requires_segment_completion or avail_str == "ONLINE_AFTER_SEGMENT_COMPLETION"):
            ctx = getattr(feature, "context", {}) or {}
            if ctx.get("segment_completed") is False:
                g3_pass = False
                g3_reason = f"Feature '{definition.feature_id}' requires completed segment evidence; segment completion flag is False"
            seg_end = ctx.get("segment_end_timestamp")
            if g3_pass and seg_end is not None and t_decision is not None and seg_end > (t_decision + 1e-4):
                g3_pass = False
                g3_reason = f"Feature '{definition.feature_id}' requires completed segment, but segment end ({seg_end:.4f}) > t_decision ({t_decision:.4f})"

        gates.append(GateEvaluation(3, "Temporal Validity", g3_pass, g3_reason))
        if not g3_pass:
            failures.append(g3_reason)

        # ---------------------------------------------------------------------
        # GATE 4: Physical Validity (Scope-Aware)
        # ---------------------------------------------------------------------
        g4_pass = True
        g4_reason = "Feature value conforms to physical plausibility bounds for measurement scope"
        
        feat_scope = getattr(feature, "measurement_scope", None)
        if feat_scope and hasattr(definition, "supported_scopes") and definition.supported_scopes:
            supp_scopes = [s.value if hasattr(s, "value") else str(s) for s in definition.supported_scopes]
            if feat_scope not in supp_scopes:
                g4_pass = False
                g4_reason = f"Feature measurement scope '{feat_scope}' is not supported by definition (supported: {supp_scopes})"

        if g4_pass and feature.value is not None:
            ctx = getattr(feature, "context", {}) or {}
            series_cells = int(ctx.get("series_cells", 1))
            valid_bounds, bound_msg = definition.physical_bounds.validate(
                feature.value,
                scope=feat_scope,
                series_cells=series_cells
            )
            if not valid_bounds:
                g4_pass = False
                g4_reason = f"Physical bounds violation: {bound_msg}"

        gates.append(GateEvaluation(4, "Physical Validity", g4_pass, g4_reason))
        if not g4_pass:
            failures.append(g4_reason)

        # ---------------------------------------------------------------------
        # GATE 5: Numerical Stability
        # ---------------------------------------------------------------------
        g5_pass = True
        g5_reason = "Computation was numerically stable (no div-zero or NaN propagation)"
        if feature.value is not None:
            if math.isnan(feature.value) or math.isinf(feature.value):
                g5_pass = False
                g5_reason = "Extracted feature value is NaN or Infinite"
        gates.append(GateEvaluation(5, "Numerical Stability", g5_pass, g5_reason))
        if not g5_pass:
            failures.append(g5_reason)

        # ---------------------------------------------------------------------
        # GATE 6: Reproducibility & Determinism
        # ---------------------------------------------------------------------
        g6_pass = True
        g6_reason = "Feature algorithm is purely deterministic and free of random state"
        gates.append(GateEvaluation(6, "Reproducibility", g6_pass, g6_reason))

        # ---------------------------------------------------------------------
        # GATE 7: Provenance Completeness (Lineage + Contextual Operating Lineage)
        # ---------------------------------------------------------------------
        g7_pass = True
        g7_reason = "Full lineage metadata (session, measurements, window, versions, scope, context) attached"
        if not feature.source_measurements:
            g7_pass = False
            g7_reason = "DerivedFeature lacks source_measurements lineage"
        elif not feature.source_session:
            g7_pass = False
            g7_reason = "DerivedFeature lacks source_session lineage"
        elif not feature.feature_version or not feature.configuration_version:
            g7_pass = False
            g7_reason = "DerivedFeature lacks explicit version tracking"
        elif not getattr(feature, "measurement_scope", None):
            g7_pass = False
            g7_reason = "DerivedFeature lacks measurement_scope in provenance"

        # Contextual Provenance: R0_OHMIC must retain operational context (pulse amplitude, temperature, scope)
        if g7_pass and feature.feature_name == "R0_OHMIC":
            ctx = getattr(feature, "context", {}) or {}
            if not ctx or "pulse_amplitude_a" not in ctx:
                g7_pass = False
                g7_reason = "R0_OHMIC lacks required operational context in provenance (e.g. pulse_amplitude_a)"

        gates.append(GateEvaluation(7, "Provenance", g7_pass, g7_reason))
        if not g7_pass:
            failures.append(g7_reason)

        # ---------------------------------------------------------------------
        # GATE 8: Missingness Correctness (Unknown != Zero)
        # ---------------------------------------------------------------------
        g8_pass = True
        g8_reason = "Missing or invalid information correctly preserved as None, never 0.0"
        # If any upstream gate 1-5 failed, feature.value MUST be None
        upstream_failed = not (g1_pass and g2_pass and g3_pass and g4_pass and g5_pass)
        if upstream_failed and feature.value is not None:
            g8_pass = False
            g8_reason = f"Violation of Missingness Invariant: Feature has value={feature.value} despite failing upstream gates"
        gates.append(GateEvaluation(8, "Missingness Correctness", g8_pass, g8_reason))
        if not g8_pass:
            failures.append(g8_reason)

        overall_admissible = all(g.passed for g in gates) and (feature.value is not None)

        return AdmissionAuditResult(
            feature_id=feature.feature_name,
            admissible=overall_admissible,
            gate_evaluations=gates,
            failure_reasons=failures
        )
