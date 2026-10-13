# Canonical Feature Catalog

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/FEATURE_CATALOG.md`  
**Phase**: Phase 4 — Canonical Feature Engine (Acceptance Remediation Baseline)  
**Status**: FROZEN & CANONICAL  
**Authoritative Feature Counts**:
- Standardized Active Candidate Features: **29**
- Explicitly Cataloged Deferred Features: **1** (`DQ_DV_PEAK`)
- Total Cataloged Features in Registry: **30**
- Invariant: `FEATURE_COUNT_REGISTRY (29 active / 30 total) == FEATURE_COUNT_CATALOG == FEATURE_COUNT_REPORT == FEATURE_COUNT_TEST_EXPECTATION`

---

## 1. Epistemic Bound Justification Taxonomy

Every physical validity bound in this catalog carries an explicit epistemic classification to ensure scientific integrity:
- `LITERATURE_DERIVED`: Established by international electrochemical literature/standards (e.g., IEC 62619, thermodynamic ceilings).
- `CHEMISTRY_DERIVED`: Derived from active electrochemical couple properties (e.g., Li-ion interstitial intercalation voltages).
- `HARDWARE_SENSOR_DERIVED`: Sensor acquisition range, ADC resolution, or communication limits.
- `PROTOTYPE_CONFIG`: Specific to RMK prototype hardware bench configuration (e.g., contactors, shunt resistors).
- `NUMERICAL_SAFETY`: Mathematical guardrails (e.g., ratios strictly in $[0, 1]$, non-negative durations).
- `PROVISIONAL_ASSUMPTION`: Provisional engineering hypothesis; explicitly subject to future validation/ablation.

---

## 2. Measurement Scope & Series Cell Scaling Policy

Features are evaluated against explicit physical measurement scopes:
- `CELL`: Single cell telemetry (nominal $3.7\,\text{V}$, operating $[1.5, 4.5]\,\text{V}$).
- `MODULE`: Series/parallel group of cells.
- `PACK`: Full battery pack telemetry (nominal $7.4\,\text{V}$ for RMK 2s Li-ion pack, operating $[3.0, 9.0]\,\text{V}$).
- `UNKNOWN`: Unspecified hierarchy level; restricted to scale-invariant dimensionless features.

Extensive properties (voltage, power, total polarization drop) scale linearly with `series_cells` when evaluated at `MODULE` or `PACK` scope. Features never silently assume single-cell thresholds when processing pack-level data.

---

## 3. Master Feature Table (29 Active Standardized Candidates)

| Feature ID | Feature Name | Family | Units | Scope | Availability | Physical Bounds | Bound Justification | Provisional? | Scaling? | Status |
|---|---|:---:|:---:|:---:|:---:|---|:---:|:---:|:---:|:---:|
| `V_MEAN` | Mean Voltage | `ELECTRICAL` | `V` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[1.5, 4.5]\,\text{V}$ | `CHEMISTRY_DERIVED` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `V_MIN` | Minimum Voltage | `ELECTRICAL` | `V` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[1.5, 4.5]\,\text{V}$ | `CHEMISTRY_DERIVED` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `V_MAX` | Maximum Voltage | `ELECTRICAL` | `V` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[1.5, 4.5]\,\text{V}$ | `CHEMISTRY_DERIVED` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `I_MEAN` | Mean Current | `ELECTRICAL` | `A` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[-60.0, 60.0]\,\text{A}$ | `HARDWARE_SENSOR_DERIVED` | Yes | No | `VALIDATED_COMPUTATION` |
| `I_ABS_MEAN` | Mean Absolute Current | `ELECTRICAL` | `A` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 60.0]\,\text{A}$ | `HARDWARE_SENSOR_DERIVED` | Yes | No | `VALIDATED_COMPUTATION` |
| `I_PEAK` | Peak Current Magnitude | `ELECTRICAL` | `A` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 60.0]\,\text{A}$ | `HARDWARE_SENSOR_DERIVED` | Yes | No | `VALIDATED_COMPUTATION` |
| `P_MEAN` | Mean Electrical Power | `ELECTRICAL` | `W` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[-270.0, 270.0]\,\text{W}$ | `PROTOTYPE_CONFIG` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `P_PEAK` | Peak Power Magnitude | `ELECTRICAL` | `W` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 270.0]\,\text{W}$ | `PROTOTYPE_CONFIG` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `DELTA_V_TOTAL` | Total Pulse Polarization Drop | `PULSE` | `V` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 1.5]\,\text{V}$ | `PROVISIONAL_ASSUMPTION` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `DELTA_V_OHMIC` | Immediate Ohmic Drop | `PULSE` | `V` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 0.8]\,\text{V}$ | `PROVISIONAL_ASSUMPTION` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `R0_OHMIC` | Ohmic Internal Resistance | `PULSE` | `Ohm` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0001, 0.100]\,\Omega$ | `PROVISIONAL_ASSUMPTION` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `RELAXATION_DELTA_V` | Relaxation Voltage Recovery | `RELAXATION` | `V` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 0.5]\,\text{V}$ | `PROVISIONAL_ASSUMPTION` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `RELAXATION_SLOPE_DV_DT` | Relaxation Drift Rate ($dV/dt$) | `RELAXATION` | `V/s` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[-0.1, 0.1]\,\text{V/s}$ | `PROVISIONAL_ASSUMPTION` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `CHARGE_AH` | Integrated Charge Capacity | `COULOMETRIC` | `Ah` | `CELL, MOD, PACK` | `ONLINE_AFTER_SEGMENT_COMPLETION` | $[0.0, 150.0]\,\text{Ah}$ | `HARDWARE_SENSOR_DERIVED` | Yes | No | `VALIDATED_COMPUTATION` |
| `DISCHARGE_AH` | Integrated Discharge Capacity | `COULOMETRIC` | `Ah` | `CELL, MOD, PACK` | `ONLINE_AFTER_SEGMENT_COMPLETION` | $[0.0, 150.0]\,\text{Ah}$ | `HARDWARE_SENSOR_DERIVED` | Yes | No | `VALIDATED_COMPUTATION` |
| `COULOMBIC_EFFICIENCY` | Coulombic Efficiency | `COULOMETRIC` | `fraction` | `CELL, MOD, PACK` | `CONDITIONAL` | $[0.50, 1.05]$ | `LITERATURE_DERIVED` | False | No | `VALIDATED_COMPUTATION` |
| `CHARGE_WH` | Integrated Charge Energy | `ENERGY` | `Wh` | `CELL, MOD, PACK` | `ONLINE_AFTER_SEGMENT_COMPLETION` | $[0.0, 500.0]\,\text{Wh}$ | `HARDWARE_SENSOR_DERIVED` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `DISCHARGE_WH` | Integrated Discharge Energy | `ENERGY` | `Wh` | `CELL, MOD, PACK` | `ONLINE_AFTER_SEGMENT_COMPLETION` | $[0.0, 500.0]\,\text{Wh}$ | `HARDWARE_SENSOR_DERIVED` | Yes | Yes ($\times N_s$) | `VALIDATED_COMPUTATION` |
| `ENERGY_EFFICIENCY` | Round-Trip Energy Efficiency | `ENERGY` | `fraction` | `CELL, MOD, PACK` | `CONDITIONAL` | $[0.40, 1.00]$ | `LITERATURE_DERIVED` | False | No | `VALIDATED_COMPUTATION` |
| `T_MEAN` | Mean Surface Temperature | `THERMAL` | `degC` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 60.0]\,^\circ\text{C}$ | `LITERATURE_DERIVED` | False | No | `VALIDATED_COMPUTATION` |
| `T_MAX` | Peak Temperature | `THERMAL` | `degC` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[0.0, 65.0]\,^\circ\text{C}$ | `LITERATURE_DERIVED` | False | No | `VALIDATED_COMPUTATION` |
| `DELTA_T` | Temperature Rise | `THERMAL` | `degC` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[-20.0, 40.0]\,^\circ\text{C}$ | `NUMERICAL_SAFETY` | Yes | No | `VALIDATED_COMPUTATION` |
| `DT_DT` | Thermal Rise Rate ($dT/dt$) | `THERMAL` | `degC/s` | `CELL, MOD, PACK` | `ONLINE_INCREMENTAL` | $[-1.0, 2.0]\,^\circ\text{C/s}$ | `NUMERICAL_SAFETY` | Yes | No | `VALIDATED_COMPUTATION` |
| `VALID_SAMPLE_FRACTION` | Completeness Fraction | `DATA_QUALITY` | `fraction` | `ALL` | `ONLINE_INCREMENTAL` | $[0.0, 1.0]$ | `NUMERICAL_SAFETY` | False | No | `VALIDATED_COMPUTATION` |
| `INVALID_SAMPLE_FRACTION` | Corruption Fraction | `DATA_QUALITY` | `fraction` | `ALL` | `ONLINE_INCREMENTAL` | $[0.0, 1.0]$ | `NUMERICAL_SAFETY` | False | No | `VALIDATED_COMPUTATION` |
| `CURRENT_FLOW_VALID` | Current Flow Indicator | `DATA_QUALITY` | `boolean` | `ALL` | `ONLINE_INCREMENTAL` | $[0.0, 1.0]$ | `NUMERICAL_SAFETY` | False | No | `VALIDATED_COMPUTATION` |
| `PULSE_VALID` | Diagnostic Pulse Indicator | `DATA_QUALITY` | `boolean` | `ALL` | `ONLINE_INCREMENTAL` | $[0.0, 1.0]$ | `NUMERICAL_SAFETY` | False | No | `VALIDATED_COMPUTATION` |
| `TIMESTAMP_INTEGRITY` | Monotonicity Indicator | `DATA_QUALITY` | `boolean` | `ALL` | `ONLINE_INCREMENTAL` | $[0.0, 1.0]$ | `NUMERICAL_SAFETY` | False | No | `VALIDATED_COMPUTATION` |
| `MEASUREMENT_DURATION` | Window Elapsed Time | `DATA_QUALITY` | `s` | `ALL` | `ONLINE_INCREMENTAL` | $[0.0, 86400.0]\,\text{s}$ | `NUMERICAL_SAFETY` | False | No | `VALIDATED_COMPUTATION` |

---

## 4. Explicitly Cataloged Deferred Feature (1 Feature)

| Feature ID | Proposed Concept | Family | Disposition | Scientific Rationale |
|---|---|:---:|:---:|---|
| `DQ_DV_PEAK` | Differential Capacity Peak | `DEFERRED` | **DEFERRED (v0.1.0-DEFERRED)** | Requires low-rate pseudo-OCV cycling ($C/20$ to $C/50$) and high-resolution ($\le 1\,\text{mV}$) sampling. The SECONDShift test bench operates rapid qualification ($0.2C - 1C$); synthesizing smooth curves without physical data resolution violates the Physics-First rule. |

---

## 5. Explicitly Prohibited Feature Types

The following conceptual patterns are strictly rejected from ever entering the feature registry or admission engine:
1. `BATTERY_HEALTH_SCORE`: Artificial composite score ($w_1 \cdot \text{SOH} + w_2 \cdot R_0 + \dots$) with arbitrary weights. Violates the prohibition against synthetic target proxies.
2. `CONFIDENCE_SCORE`: Arbitrary $0-100$ score conflating data completeness with posterior epistemic confidence.
3. `BATTERY_ID_SHORTCUT`: Specimen identifier used directly or indirectly as an input feature.
4. `FUTURE_DEGRADATION_SLOPE`: Any feature utilizing post-decision cycle telemetry. Violates temporal causality.
5. `ORACLE_DERIVED_LABELS`: Direct leakage of ground-truth simulation attributes into candidate vectors.
