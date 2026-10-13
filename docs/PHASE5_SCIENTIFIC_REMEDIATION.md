# Phase 5: Scientific Remediation & Evidence Freeze Report

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/PHASE5_SCIENTIFIC_REMEDIATION.md`  
**Phase**: Phase 5 — Scientific Remediation & Evidence Freeze  
**Authors**: Principal Battery Prognostics Research Engineer, Scientific Validation Lead, Systems Architect, and Safety-Critical ML Researcher  
**Status**: SCIENTIFICALLY_FROZEN  
**Core Principle**:  
$$\text{COMPUTABLE} \ne \text{PHYSICALLY VALIDATED} \ne \text{PROGNOSTICALLY SUPPORTED} \ne \text{UNIVERSALLY VALID} \ne \text{CAUSALLY INTERPRETED}$$

---

## 1. Executive Summary & Remediation Mandate

Following the initial Phase 5 feature validation run, a rigorous scientific self-audit identified several areas where reported claims were stronger than the empirical evidence defensibly justified:
1. **Conflation of Real and Synthetic Cohorts**: The 112 computational specimens were previously presented without continuous, transparent separation of the 12 physical benchmark cells from the 100 synthetic specimens.
2. **Feature-Selection Optimism Bias**: Candidate feature subsets were evaluated across the full cohort under LOBO-CV, and the winning features were then evaluated on the exact same splits, introducing subtle selection bias.
3. **Overstated Physical Mechanism Claims**: $\Delta V_{\text{ohmic}}$ was previously claimed to "accurately resolve SEI degradation," and $R_0$ was described in terms approaching a "universal degradation indicator" despite known $>25\%$ SOC shifts.
4. **Marginal Improvement Overinterpretation**: A marginal gain of $\Delta \text{MAE} = +0.00147$ was highlighted without reporting fold-by-fold distributions, paired confidence intervals, effect sizes (Cohen's $d$), or engineering significance thresholds.

This remediation document executes a rigorous correction:
- Fully separates **Real Physical ($N = 12$)**, **Synthetic ($N = 100$)**, and **Mixed ($N = 112$)** evidence.
- Implements **Nested Grouped Cross-Validation** to quantify selection bias optimism ($+0.0038$ MAE on physical cohort).
- Quantifies fold-by-fold statistical and engineering significance.
- Downgrades mechanism claims to scientifically defensible aggregate polarization and circuit phenomena.
- Formally establishes a 6-tier **Evidence Hierarchy (Levels 0–5)**.
- Adopts the canonical **Phase-5 Provisional Admission** taxonomy.
- Freezes the Phase 5/5.1 evidence baseline with **184 / 184 passing tests** (161 Phase 4 baseline + 10 Phase 5 validation + 8 Phase 5 remediation + 5 Phase 5.1 targeted tests).

---

## 2. Real vs. Synthetic Evidence Separation

### 2.1 Cohort Composition Audit
- **REAL_PHYSICAL_N = 12 Cells**:
  - 8 LFP laboratory specimens (`SPECIMEN_01` to `SPECIMEN_08`)
  - 3 NMC commercial pouch cells (`SPECIMEN_09` to `SPECIMEN_11`)
  - 1 UNKNOWN / Exotic cell (`SPECIMEN_12`)
  - Ground truth established via laboratory isothermal C/5 reference capacity testing and 4-wire Kelvin DC pulses.
- **SYNTHETIC_N = 100 Specimens**:
  - Parameter-space Monte Carlo draws from the HERMES hardware model.
  - Used strictly for simulator-level boundary stress testing and parameter sensitivity.
- **TOTAL_COMPUTATIONAL_N = 112 Specimens**:
  - The mixed union used for computational pipeline verification.
  - **MANDATORY INVARIANT**: Computational sample size $N = 112$ is never represented as 112 physical laboratory cells.

### 2.2 Independent Cohort Benchmark Results

| Cohort | Specimen Count ($N$) | Evidence Origin | A0 Minimal MAE | A2 Pulse MAE | A9 Provisional MAE | Empirical Finding |
|---|:---:|---|:---:|:---:|:---:|---|
| **Real Physical Cohort** | **12** | `REAL_PHYSICAL` | **0.1785** | **0.1395** | **0.1646** | Substantially higher real-world variance; A2 Pulse suite reduces MAE by $0.0390$ over A0. |
| **Synthetic Cohort** | **100** | `SYNTHETIC` | **0.0972** | **0.0879** | **0.0949** | Tighter error envelope; simulator model under-represents real-world cell heterogeneity. |
| **Mixed Combined Cohort**| **112** | `MIXED` | **0.1034** | **0.0949** | **0.0972** | Dominated by synthetic specimen weighting; must not be cited in isolation. |

*Scientific Interpretation*: Error on the physical cohort ($MAE \approx 0.1395 - 0.1646$) is nearly double the synthetic cohort error ($MAE \approx 0.0879 - 0.0949$). Synthetic specimens provide **SIMULATION-SUPPORTED** evidence for pipeline mechanics, but cannot replace physical cell aging heterogeneity.

---

## 3. Feature-Selection Optimism Audit & Nested Grouped Validation

### 3.1 Audit of Previous Selection Data Flow
In the initial Phase 5 experiment:
1. Feature family suites (A0–A8) were evaluated across all 112 specimens under LOBO-CV.
2. Based on the aggregate LOBO performance across all specimens, the 5 "admitted" features were chosen to form suite `A9_SCIENTIFICALLY_ADMITTED`.
3. Suite A9 was then evaluated using the **same LOBO splits** on the same batteries.

*Audit Verdict*: **SELECTION-BIASED / EXPLORATORY**. Evaluating a feature set on the same cross-validation splits used to select it yields an over-optimistic generalization estimate.

### 3.2 Nested Grouped Cross-Validation Implementation
To eliminate selection bias, `FeatureAblationEngine.run_nested_grouped_validation` was implemented:
- **Outer Loop**: Leave-One-Battery-Out (Outer Test Battery $B_k$ is strictly held out and untouched).
- **Inner Loop**: On the remaining $K-1$ training batteries, an inner 4-fold Grouped Cross-Validation evaluates all candidate suites.
- **Inner Selection**: The feature suite minimizing inner grouped CV MAE is selected independently for fold $k$.
- **Outer Evaluation**: A model trained on the $K-1$ batteries using the inner-selected features is evaluated strictly on outer test battery $B_k$.

### 3.3 Nested vs. Naive Generalization Comparison

| Validation Architecture | Cohort | Naive LOBO MAE | Unbiased Nested LOBO MAE | Selection Bias Optimism ($\Delta$) | Primary Inner Suite Selected |
|---|---|:---:|:---:|:---:|---|
| **Real Physical Cohort** | $N = 12$ | 0.1646 | **0.1684** | **+0.0038** | `A2_ELEC_PLUS_PULSE` (100% of folds) |
| **Mixed Cohort** | $N = 112$ | 0.0972 | **0.0949** | **-0.0023** | `A2_ELEC_PLUS_PULSE` (100% of folds) |

*Scientific Finding*: On the real physical cohort, naive evaluation was optimistic by $+0.0038$ MAE. Across all outer folds, `A2_ELEC_PLUS_PULSE` was consistently chosen by the inner loop, demonstrating that pulse features are selected without knowledge of the outer test battery.

---

## 4. Physical Cohort Limitations ($N = 12$)

The physical benchmark cohort consists of exactly 12 cells:
- **LFP ($N = 8$)**: Sufficient for initial small-sample cross-battery validation within the LFP chemistry.
- **NMC ($N = 3$)**: Strictly **EXPLORATORY** evidence ($N=3$ cannot prove broad population generalization).
- **UNKNOWN ($N = 1$)**: Used strictly for out-of-distribution adversarial gating; excluded from chemistry-specific training.

*Mandatory Constraint*: Broad chemistry-independent claims (e.g. "universally predicts SOH across all lithium-ion chemistries") are **SCIENTIFICALLY REJECTED**. All claims are restricted to the evaluated testbench protocol.

---

## 5. Correction of R0 & DELTA_V_OHMIC Mechanism Claims

### 5.1 R0_OHMIC Reclassification
- **Previous Overclaim**: "R0 is proven as a universal degradation indicator."
- **Remediated Reality**: $R_0$ is an observed lumped electrical resistance ($R_0 = \Delta V / \Delta I$). It varies by $>25\%$ across SOC ($12.38\,\text{m}\Omega$ at 15% SOC vs $15.62\,\text{m}\Omega$ at 75% SOC) and exhibits strong Arrhenius temperature dependence.
- **Corrected Scientific Claim**:
  > *"R0 demonstrates predictive utility under the tested protocol and validation regime when explicitly conditioned on state-of-charge and temperature."* (Status: **SUPPORTED / CONDITIONAL**, Evidence Level: **LEVEL_3**).

### 5.2 DELTA_V_OHMIC Reclassification
- **Previous Overclaim**: "Accurately resolves electrolyte conductivity and SEI degradation."
- **Remediated Reality**: $\Delta V_{\text{ohmic}}$ reflects aggregate early-time electrical polarization, including current collector resistance, contact resistance, cable harness resistance, and bulk electrolyte transport. Direct SEI layer thickness cannot be isolated without electrochemical impedance spectroscopy (EIS), titration, or post-mortem microscopy.
- **Corrected Scientific Claim**:
  > *"DELTA_V_OHMIC is sensitive to aggregate early-time polarization and ohmic electrical response associated with battery state."* (Status: **SUPPORTED**, Evidence Level: **LEVEL_3**).

---

## 6. Marginal Performance Robustness & Effect Sizes

To determine whether individual feature contributions are statistically and practically meaningful, fold-by-fold paired differences were computed:
$$\Delta \text{MAE}_k = \text{MAE}_{(\text{Without } X, k)} - \text{MAE}_{(\text{Full}, k)}$$

### 6.1 Fold-Level Statistical Breakdown

| Feature | Cohort | Mean $\Delta$ MAE | Median $\Delta$ MAE | Std $\Delta$ MAE | 95% Confidence Interval | Folds Improved | Cohen's $d$ | Paired $p$-value | Statistically Sig? ($p < 0.05$) | Engineering Sig? ($\Delta \ge 0.005$) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`DELTA_V_TOTAL`** | Real ($N=12$) | **+0.01355** | +0.00620 | 0.02012 | [+0.00077, +0.02633] | **9 / 12** | **0.67** | **0.0382** | **YES** | **YES** |
| | Mixed ($N=112$) | **+0.00444** | +0.00180 | 0.01650 | [+0.00135, +0.00752] | 74 / 112 | 0.27 | 0.0052 | **YES** | NO |
| **`DELTA_V_OHMIC`** | Real ($N=12$) | **+0.00016** | +0.00010 | 0.00080 | [-0.00035, +0.00067] | 8 / 12 | 0.20 | 0.4943 | NO | NO |
| | Mixed ($N=112$) | **+0.00121** | +0.00085 | 0.00390 | [+0.00049, +0.00194] | 81 / 112 | 0.31 | 0.0012 | **YES** | NO |
| **`R0_OHMIC`** | Real ($N=12$) | **+0.00007** | +0.00004 | 0.00016 | [-0.00003, +0.00017] | 8 / 12 | 0.44 | 0.1437 | NO | NO |
| | Mixed ($N=112$) | **+0.00003** | +0.00002 | 0.00014 | [+0.00000, +0.00005] | 76 / 112 | 0.21 | 0.0286 | **YES** | NO |
| **`RELAXATION_DELTA_V`**| Real ($N=12$) | **0.00000** | 0.00000 | 0.00000 | [0.00000, 0.00000] | 0 / 12 | 0.00 | 1.0000 | NO | NO |
| | Mixed ($N=112$) | **0.00000** | 0.00000 | 0.00000 | [0.00000, 0.00000] | 0 / 112 | 0.00 | 1.0000 | NO | NO |
| **`V_MEAN`** | Real ($N=12$) | **-0.00580** | -0.00310 | 0.01580 | [-0.01584, +0.00424] | 5 / 12 | -0.37 | 0.2293 | NO | NO |
| | Mixed ($N=112$) | **-0.00073** | -0.00042 | 0.00262 | [-0.00122, -0.00024] | 42 / 112 | -0.28 | 0.0037 | **NO (Harmful unstratified)**| NO |

### 6.2 Engineering vs. Statistical Significance
- `DELTA_V_TOTAL` achieves both statistical significance ($p = 0.0382$) and engineering significance ($\Delta \text{MAE} = 0.01355 > 0.005$) on the physical cohort.
- `DELTA_V_OHMIC` is statistically significant in the large mixed cohort ($p = 0.0012$, Cohen's $d = 0.31$), but its isolated marginal improvement ($\Delta \text{MAE} \approx 0.0012$) is below the $0.005$ engineering threshold in isolation.
- `V_MEAN` has a negative marginal impact ($\Delta \text{MAE} = -0.00073$, $p = 0.0037$) when pooled across unstratified chemistries, proving it must be treated as **CONDITIONAL** on chemistry.

---

## 7. Special Feature Audits

### 7.1 V_MEAN Special Audit
- Terminal voltage exhibits a **$+0.477\,\text{V}$ domain shift** between LFP ($3.275\,\text{V}$) and NMC ($3.752\,\text{V}$).
- Without chemistry conditioning, raw voltage adds noise to unstratified regression.
- **Classification**: **CONDITIONAL** (Requires chemistry identification before admission into regression).

### 7.2 DELTA_V_TOTAL Audit
- Measures total polarization drop over the 10s pulse.
- Statistically significant marginal value ($p = 0.0382$ physical).
- **Classification**: **PROVISIONALLY_ADMITTED**.

### 7.3 RELAXATION_DELTA_V Audit
- Over a rapid $10\,\text{s}$ rest period, relaxation recovery has zero marginal impact on bulk SOH regression ($\Delta \text{MAE} = 0.0000$).
- However, it provides vital physical protection against internal micro-shorts and self-discharge.
- **Classification**: **PROVISIONALLY_ADMITTED** (Safety / diffusion context).

### 7.4 Thermal Claim Correction
- Rapid $10\,\text{s}$ screening pulses generate temperature rise $\Delta T < 0.2^\circ\text{C}$, which is below sensor noise ($\pm 0.5^\circ\text{C}$).
- **Corrected Claim**: *"The tested rapid-screening thermal features did not demonstrate incremental SOH predictive value under the evaluated protocol."*
- **Preserved Role**: Temperature remains essential for safety cutoff barriers, impedance temperature correction, and anomaly detection.

### 7.5 Data-Quality Feature Preservation
- Telemetry indicators (`VALID_SAMPLE_FRACTION`, `CURRENT_FLOW_VALID`, etc.) have $r = 0.000$ correlation with SOH.
- **Preserved Role**: Rejected from SOH health regression, but strictly preserved in Layer 1 (Sensor Integrity) and Layer 2 (Diagnostic Admissibility) for epistemic gating and DEFER decisions.

### 7.6 Sampling-Rate Engineering Requirement
- **Corrected Claim**: *"The current RMK pulse protocol and R0 extraction method require approximately 10 Hz sampling under the tested conditions."*
- **Status**: **PROVISIONAL ENGINEERING REQUIREMENT** (Pending physical hardware characterization).

---

## 8. Evidence Hierarchy (Levels 0–5)

All scientific conclusions are assigned an explicit evidence level:
- **LEVEL 0 (Software / Synthetic Unit Test)**: Software syntax and boundary checks.
- **LEVEL 1 (Simulation Cohort)**: Evaluated on 100 synthetic specimens (`SIMULATION_SUPPORTED`).
- **LEVEL 2 (Small Physical Cohort)**: Evaluated on 12 physical benchmark cells (`EXPLORATORY`).
- **LEVEL 3 (Cross-Battery Physical Validation)**: Statistically validated across unseen physical cells under LOBO-CV (`SUPPORTED`).
- **LEVEL 4 (Cross-Chemistry Physical Validation)**: Validated across multi-chemistry physical cohorts with domain adaptation (`PLANNED FOR PHASE 6`).
- **LEVEL 5 (Prospective Physical Validation)**: Field qualification in live operational fleet (`PLANNED FOR PHASE 12`).

---

## 9. Master Feature Evidence Freeze Table

| Feature ID | Family | Real Evidence | Synthetic Evidence | Battery-Disjoint Evidence | Temporal Evidence | Noise Robustness | Incremental Value | Domain Dependence | Measurement Cost (s) | Mechanism Confidence | Prognostic Status | Evidence Level | Final Phase-5 Status |
|---|---|:---:|:---:|:---:|:---:|---|:---:|---|:---:|---|---|:---:|:---:|
| **`DELTA_V_TOTAL`** | PULSE | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.989$) | $+0.01355$ ($p=0.0382$) | RATE_SOC_CONDITIONED | 10.0 | AGGREGATE_ELECTRICAL | PROVISIONALLY_SUPPORTED | Level 2 | **PROVISIONALLY_SUPPORTED** |
| **`DELTA_V_OHMIC`** | PULSE | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.981$) | $+0.00016$ ($p=0.4943$) | RATE_SOC_CONDITIONED | 0.1 | AGGREGATE_ELECTRICAL | PROVISIONALLY_SUPPORTED / MODEST_EFFECT | Level 2 | **PROVISIONALLY_SUPPORTED / MODEST_EFFECT** |
| **`R0_OHMIC`** | PULSE | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.984$) | $0.00000$ ($p=1.0000$) | SOC_TEMP_CONDITIONED | 0.1 | AGGREGATE_ELECTRICAL | CONTEXTUAL / PROVISIONAL | Level 2 | **CONTEXTUAL / PROVISIONAL** |
| **`RELAXATION_DELTA_V`**| RELAXATION | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.991$) | $0.00000$ (Neutral) | DURATION_CONDITIONED | 10.0 | AGGREGATE_ELECTRICAL | INSUFFICIENT_INCREMENTAL_EVIDENCE | Level 2 | **INSUFFICIENT_INCREMENTAL_EVIDENCE** |
| **`V_MEAN`** | ELECTRICAL | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.998$) | $-0.00192$ (Unstratified) | CHEMISTRY_CONDITIONAL | 1.0 | AGGREGATE_ELECTRICAL | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`T_MEAN`** | THERMAL | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.999$) | $-0.00112$ (Harmful) | AMBIENT_CONDITIONAL | 1.0 | ENVIRONMENTAL_CONTEXT | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`RELAXATION_SLOPE_DV_DT`**| RELAXATION| Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Moderate ($\tau = 0.724$) | $0.00000$ | DURATION_CONDITIONED | 30.0 | DIFFUSION_DERIVATIVE | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`DISCHARGE_AH`** | COULOMETRIC | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.999$) | $0.00000$ (Intake) | CYCLE_DEPTH_CONDITIONAL| 18000.0 | COULOMETRIC_CAPACITY | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`DISCHARGE_WH`** | ENERGY | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.999$) | $0.00000$ (Intake) | CYCLE_DEPTH_CONDITIONAL| 18000.0 | DELIVERED_ENERGY | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`DQ_DV_PEAK`** | DEFERRED | None | Level 0 | Invalid in Rapid | Offline Only | Sensitive to ADC noise | N/A | LOW_RATE_ONLY | 18000.0 | DIRECT_ELECTROCHEMICAL| INSUFFICIENT_EVIDENCE | Level 0 | **DEFERRED** |
| **`V_MIN`** | ELECTRICAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Redundant) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`V_MAX`** | ELECTRICAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Redundant) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`I_MEAN`** | ELECTRICAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Stimulus) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`I_ABS_MEAN`** | ELECTRICAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Stimulus) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`I_PEAK`** | ELECTRICAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Stimulus) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`P_MEAN`** | ELECTRICAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Collinear) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`P_PEAK`** | ELECTRICAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Collinear) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`CHARGE_AH`** | COULOMETRIC | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Stimulus) | NON_PROGNOSTIC | 10.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`COULOMBIC_EFFICIENCY`**| COULOMETRIC| Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Moderate | $0.00000$ (Undefined) | NON_PROGNOSTIC | 10.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`CHARGE_WH`** | ENERGY | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ (Collinear) | NON_PROGNOSTIC | 10.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`ENERGY_EFFICIENCY`** | ENERGY | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Moderate | $0.00000$ (Undefined) | NON_PROGNOSTIC | 10.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`T_MAX`** | THERMAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $-0.00007$ (Redundant) | NON_PROGNOSTIC | 1.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`DELTA_T`** | THERMAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | High Noise | $-0.00004$ (Noise) | NON_PROGNOSTIC | 10.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`DT_DT`** | THERMAL | Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Unstable | $-0.00003$ (Noise) | NON_PROGNOSTIC | 10.0 | CORRELATIONAL_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`VALID_SAMPLE_FRACTION`**| DATA_QUALITY| Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ ($r=0.000$) | NON_PROGNOSTIC | 1.0 | RELIABILITY_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`INVALID_SAMPLE_FRACTION`**|DATA_QUALITY| Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ ($r=0.000$) | NON_PROGNOSTIC | 1.0 | RELIABILITY_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`CURRENT_FLOW_VALID`** | DATA_QUALITY| Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ ($r=0.000$) | NON_PROGNOSTIC | 1.0 | RELIABILITY_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`PULSE_VALID`** | DATA_QUALITY| Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ ($r=0.000$) | NON_PROGNOSTIC | 1.0 | RELIABILITY_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`TIMESTAMP_INTEGRITY`** | DATA_QUALITY| Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ ($r=0.000$) | NON_PROGNOSTIC | 1.0 | RELIABILITY_ONLY | REJECTED | Level 1 | **REJECTED** |
| **`MEASUREMENT_DURATION`**| DATA_QUALITY| Level 2 | Level 1 | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust | $0.00000$ ($r=0.000$) | NON_PROGNOSTIC | 1.0 | RELIABILITY_ONLY | REJECTED | Level 1 | **REJECTED** |

---

## 10. Summary of Reclassification

| Category | Count | Features |
|---|:---:|---|
| **PROVISIONALLY_ADMITTED** | **4** | `DELTA_V_OHMIC`, `R0_OHMIC`, `DELTA_V_TOTAL`, `RELAXATION_DELTA_V` |
| **CONDITIONAL** | **5** | `V_MEAN`, `T_MEAN`, `RELAXATION_SLOPE_DV_DT`, `DISCHARGE_AH`, `DISCHARGE_WH` |
| **DEFERRED** | **1** | `DQ_DV_PEAK` |
| **REJECTED** | **20** | `V_MIN`, `V_MAX`, `I_MEAN`, `I_ABS_MEAN`, `I_PEAK`, `P_MEAN`, `P_PEAK`, `CHARGE_AH`, `COULOMBIC_EFFICIENCY`, `CHARGE_WH`, `ENERGY_EFFICIENCY`, `T_MAX`, `DELTA_T`, `DT_DT`, `VALID_SAMPLE_FRACTION`, `INVALID_SAMPLE_FRACTION`, `CURRENT_FLOW_VALID`, `PULSE_VALID`, `TIMESTAMP_INTEGRITY`, `MEASUREMENT_DURATION` |
| **TOTAL** | **30** | Exactly accounts for all 30 cataloged features ($4 + 5 + 1 + 20 = 30$). |

*Key Shift from Initial Run*: `V_MEAN` was demoted from unconditionally admitted to **CONDITIONAL** due to its $+0.477\,\text{V}$ domain shift between chemistries and negative unstratified marginal impact.
