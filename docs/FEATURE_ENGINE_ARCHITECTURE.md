# Canonical Feature Engine Architecture

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/FEATURE_ENGINE_ARCHITECTURE.md`  
**Phase**: Phase 4 — Canonical Feature Engine (Acceptance Remediation Baseline)  
**Status**: FROZEN & CANONICAL ARCHITECTURE  

---

## 1. Purpose & Core Philosophy

In lithium-ion battery qualification and remanufacturing diagnostics, predictive models often fail because features are extracted ad-hoc without physical ground truth, temporal causality, or lineage tracking.

The **Phase 4 Canonical Feature Engine** establishes a rigorous, scientifically defensible feature-generation layer governed by the non-negotiable project principle:

> **"KNOW WHAT YOU KNOW. KNOW WHAT YOU DON’T KNOW. NEVER OPTIMIZE SAFETY AWAY."**

### Core Architectural Invariants:
1. **Measurement $\ne$ Feature**: Raw sensor observations (ADC voltages, currents, temperatures) are fundamentally distinct from derived electrochemical features. Every feature must document its derivation, units, physical hypothesis, and epistemic justification.
2. **Features Must EARN Admission**: No feature is automatically accepted into downstream modeling. Every candidate feature must pass the **8-Gate Feature Admission Framework**.
3. **No Fake Physics**: No arbitrary polynomial combinations, weighted-sum "health scores", or synthetic confidence metrics.
4. **Unknown $\ne$ Zero**: If an observation is missing, invalid, or sub-threshold, the feature returns `value = None` and `quality_status = INVALID`. Valid measured zero quantities (e.g., zero-current open-circuit conditions) are preserved as `0.0`.
5. **Zero Look-Ahead Leakage**: Online features consumed at decision timestamp $t_{\text{decision}}$ may only ingest telemetry whose physical observation interval satisfies $t_{\text{end}} \le t_{\text{decision}} + 10^{-4}\,\text{s}$.
6. **No Silent Clipping**: Invalid physical values, unphysical inverted timestamps ($dt < 0$), or out-of-bound measurements must deterministically yield `None` and fail Gate 4/5. They are NEVER silently clipped or coerced into plausible numbers.
7. **Ground-Truth & Oracle Isolation**: Production feature extractors have zero access to ground truth labels (`soh`, `rul`, `degradation_label`, `hidden_state`). Any attempt to inject oracle shortcuts is caught and rejected by Gate 2.
8. **Battery ID Shortcut Prohibition**: Specimen or battery identifiers are preserved purely for provenance tracking and audit lineage. They are structurally blocked from acting as numerical proxy predictors.
9. **Observational Isolation**: Feature extraction errors never alter or bypass the hardware safety supervisor (`HardSafetyBarrier`). Safety constraints remain strictly independent.
10. **Scope-Aware Validation**: Features explicitly declare their `MeasurementScope` (`CELL`, `MODULE`, `PACK`). Extensive physical quantities (voltage, power) scale with series cell count $N_s$ (e.g., RMK 2s nominal $7.4\,\text{V}$ pack scales $[1.5, 4.5]\,\text{V}$ bounds to $[3.0, 9.0]\,\text{V}$), preventing false rejections of valid pack telemetry.

---

## 2. End-to-End Extraction Pipeline

```
          RAW PHYSICAL OBSERVATION / TELEMETRY STREAM
                               │
                               ▼
        Layer 1 & 2 Sensor Feasibility & Pulse Validation
                               │
                               ▼
            Temporal Observation Window Selection
                               │
                               ▼
                 Measurement Quality Gate (Gate 1 & 2)
           (Availability, Validity, Ground-Truth Isolation)
                               │
                               ▼
         Family-Specific Deterministic Feature Extraction
    (Electrical | Pulse | Relaxation | Coulometric | Energy | Thermal | Quality)
                               │
                               ▼
                 Physical Validity Gate (Gate 4 & 5)
           (Scope-Aware Bounds, Scaling, Numerical Stability)
                               │
                               ▼
                 Missingness / Quality Annotation (Gate 8)
                               │
                               ▼
           Temporal Provenance & Causality Gate (Gate 3)
      (Causality, Segment-Completion, Availability Modes)
                               │
                               ▼
             Canonical DerivedFeature Representation
           (Attached Scope, Context, and Audit Lineage)
                               │
                               ▼
           Authoritative Feature Registry Verification
                               │
                               ▼
                   CANDIDATE FEATURE SET
```

---

## 3. The 8-Gate Feature Admission Framework

Every feature extracted by `CanonicalFeatureEngine` is evaluated through the `FeatureAdmissionEngine`:

| Gate | Name | Requirement | Failure Outcome |
|:---:|---|---|---|
| **GATE 1** | **Measurement Availability** | Required raw channels (`voltage_v`, `current_a`, `temperature_c`, `timestamp`) exist in observation window. | `value = None`, `quality = INVALID` |
| **GATE 2** | **Measurement Validity & GT Isolation** | Sensor samples passed validity checks; zero ground-truth/oracle keys (`soh`, `rul`, `degradation_regime`) or battery ID shortcuts present. | `value = None`, leakage violation logged |
| **GATE 3** | **Temporal Validity & Availability** | $t_{\text{end}} \le t_{\text{decision}} + 10^{-4}\,\text{s}$; `OFFLINE_ONLY` features rejected at online decision time; segment completion verified if required. | Flagged `FUTURE_INFORMATION` or `INCOMPLETE_SEGMENT`, rejected |
| **GATE 4** | **Physical Validity (Scope-Aware)** | Value conforms to electrochemical bounds for declared `MeasurementScope` (`CELL`, `MODULE`, `PACK`), scaling with series cells. | `value = None`, bounds violation logged |
| **GATE 5** | **Numerical Stability** | No division-by-zero, negative duration ($dt < 0$), singular matrix, or floating-point NaN/Inf. | `value = None`, `quality = INVALID` |
| **GATE 6** | **Reproducibility & Determinism** | Pure deterministic function; identical telemetry and config yield bitwise identical features and provenance. | Rejection if non-deterministic |
| **GATE 7** | **Provenance Completeness** | Full lineage (`source_session`, `source_segment`, channels, versions, scope, and operating context for $R_0$) attached. | Inadmissible to qualification pipeline |
| **GATE 8** | **Missingness Correctness** | Preserves `None` when invalid; physically measured `0.0` preserved. Zero coercion strictly forbidden. | Inadmissible if coerced to default |

---

## 4. Canonical Feature Contract (`DerivedFeature`)

All features emit strictly as `DerivedFeature` objects from `secondshift/interfaces/qualification_schema.py`:

```python
@dataclass
class DerivedFeature:
    feature_name: str                     # e.g., "R0_OHMIC", "V_MEAN"
    feature_version: str = "1.0.0"       # Semantic version of extraction algorithm
    value: Optional[float] = None        # Physically measured scalar or None
    unit: str = ""                       # SI or standard engineering unit
    source_session: str = ""             # Parent QualificationSession ID
    source_segment: Optional[str] = None # Executed TestSegment ID
    source_measurements: List[str]       # Raw channels consumed (e.g. ["voltage_v", "current_a"])
    temporal_provenance: TemporalProvenance # Observation window [t_start, t_end] vs t_decision
    physical_meaning: str = ""           # Human-readable physical interpretation
    expected_direction: Optional[str] = None # e.g., "HIGHER_IS_WORSE", "LOWER_IS_WORSE"
    quality_status: str = "VALID"        # VALID | DEGRADED | INVALID
    configuration_version: str = "2.0.0" # Version of experimental thresholds
    measurement_scope: str = "CELL"      # CELL | MODULE | PACK | UNKNOWN
    context: Dict[str, Any] = field(default_factory=dict) # Operational conditioning context

    @property
    def is_admissible(self) -> bool:
        """True iff value is not None, quality is VALID, and no future leakage."""
        return (
            self.value is not None
            and self.quality_status == "VALID"
            and self.temporal_provenance.leakage_status == "AVAILABLE_AT_DECISION_TIME"
        )
```

---

## 5. Temporal Availability Semantics

Features declare explicit temporal availability classes:

1. **`ONLINE_INCREMENTAL`**: Computable instantaneously during an active test step using past and current samples only (e.g. `V_MEAN`, `I_PEAK`, `R0_OHMIC`, `T_MEAN`). Admissible for online triage and closed-loop decisions.
2. **`ONLINE_AFTER_SEGMENT_COMPLETION`**: Computable online, but only after the specific qualification segment finishes (e.g. `CHARGE_AH`, `DISCHARGE_WH`). Admissible at decision time $t_{\text{decision}} \ge t_{\text{segment\_end}}$.
3. **`CONDITIONAL`**: Computable only after a complete multi-step charge-discharge cycle finishes (e.g. `COULOMBIC_EFFICIENCY`, `ENERGY_EFFICIENCY`). Inadmissible mid-cycle.
4. **`OFFLINE_ONLY`**: Retrospective or computationally deferred features (e.g. `DQ_DV_PEAK`). Strictly prohibited in online test-bench decision gates.

---

## 6. Contextual Operating Lineage for $R_0$

Ohmic internal resistance ($R_0$) is highly state-dependent. It is never treated as an unconditioned scalar. The extraction provenance attaches:
- `pulse_amplitude_a`: Actual mean current during pulse
- `pulse_duration_s`: Duration of transient excitation
- `temperature_c`: Surface temperature at time of pulse
- `soc`: Estimated or protocol state-of-charge context
- `direction`: `CHARGE` vs `DISCHARGE`
- `measurement_scope`: `CELL`, `MODULE`, or `PACK`
- `series_cells`: Count of series cells in specimen

If operational conditioning context is stripped, Gate 7 rejects admission of $R_0$.

---

## 7. Epistemic Separation: Computation vs. Prognostics

Phase 4 strictly enforces:
- **`COMPUTATIONALLY_VALIDATED`**: The feature is correctly extracted according to its mathematical definition and passes all 8 admission gates.
- **`PROGNOSTICALLY_VALIDATED`**: Evidence demonstrates that the feature provides stable, reproducible predictive information for a target (SOH/RUL). **Phase 4 DOES NOT establish prognostic validity.**
- **Measurement Quality $\ne$ Model Confidence**: Sensor data completeness and quality fractions are data metrics; they must never be conflated with posterior Bayesian or conformal model confidence.
- **Thermal Metrics are Safety/Context**: Thermal measurements serve safety boundaries and contextual conditioning; they do not improve rapid qualification RUL prognostics.
