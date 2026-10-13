# Phase 5.1 Feature Ablation & Scientific Validation Results

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/FEATURE_ABLATION_RESULTS.md`  
**Phase**: Phase 5.1 — Scientific Evidence-Freeze Correction & Finalization  
**Validation Unit**: `BATTERY / SPECIMEN` (Strict LOBO-CV & Nested Grouped CV, Never Random Telemetry Rows)  
**Specimen Cohort**:
- **Real Physical Benchmark Cohort**: $N_{\text{physical}} = 12$ physical cells (8 LFP, 3 NMC, 1 UNKNOWN) — *Level 2 Evidence*
- **Synthetic Simulation Cohort**: $N_{\text{synthetic}} = 100$ simulated specimens (50 LFP, 50 NMC) — *Level 1 Evidence*
- **Total Computational Cohort**: $N_{\text{total}} = 112$ specimens — *Mixed Evidence*

---

## 1. Battery-Disjoint Split vs Random Row Split (Leakage & Generalization Gap)

To demonstrate why random row splitting is scientifically invalid for battery prognostics, an ordinary random 75/25 row split was benchmarked against Leave-One-Battery-Out (LOBO-CV) on the mixed cohort ($N=112$).

| Split Strategy | Validation Unit | Test MAE | Test RMSE | Test $R^2$ | Scientific Finding & Interpretation |
|---|---|:---:|:---:|:---:|---|
| **Random Row Split** | Telemetry Rows | **0.0915** | 0.1168 | -0.0297 | **Artificially optimistic**: Random row splitting produces lower apparent error because training rows leak identical battery identity and operating regime into the test set. |
| **Battery-Disjoint Split (LOBO)** | **BATTERY / SPECIMEN** | **0.0959** | 0.1193 | 0.1497 | **Scientifically valid & conservative**: Evaluates generalization to completely unseen cells. Battery-disjoint LOBO provides the more conservative and independent estimate of cross-battery generalization. |
| **Generalization Gap ($\Delta$)** | — | **+0.0044** | +0.0025 | — | **Explicitly defined positive gap**: $\text{GENERALIZATION GAP} = \text{LOBO\_MAE} - \text{RANDOM\_SPLIT\_MAE} = 0.0959 - 0.0915 = +0.0044$ MAE. |

> [!IMPORTANT]
> **Scientific Wording Correction (Correction B)**: Random row splitting produced lower apparent error than battery-disjoint LOBO, indicating an optimistic generalization estimate under non-independent row-level splitting. Battery-disjoint LOBO provides the more conservative and independent estimate of cross-battery generalization. Do NOT claim that LOBO has a lower MAE than random row splitting.

---

## 2. Real vs. Synthetic Cohort Breakdown & Baseline-Specific Improvements

Real physical evidence ($N=12$) is strictly separated from synthetic simulation evidence ($N=100$). Synthetic specimens underestimate real-world manufacturing tolerances, contact resistances, and sensor noise.

| Suite ID | Suite Name | Real Physical ($N=12$) MAE | Synthetic ($N=100$) MAE | Total Mixed ($N=112$) MAE | Scientific Assessment |
|---|---|:---:|:---:|:---:|---|
| **A0** | Minimal Baseline (`V_MEAN`) | 0.1785 | 0.0972 | 0.1034 | Minimal reference operating voltage. High error on physical cells due to LFP flat plateau ($+0.477\,\text{V}$ shift vs NMC). |
| **A1** | Electrical Only (V, I, P) | 0.1651 | 0.0881 | 0.0960 | Load profile aggregates reflect electronic load stimulus, not internal degradation. |
| **A2** | Electrical + Pulse ($\Delta V_{\text{ohmic}}, R_0, \Delta V_{\text{total}}$) | **0.1395** | **0.0879** | **0.0949** | **BEST OVERALL SUITE**: Pulse polarization envelope improves prediction. |
| **A3** | Electrical + Relaxation (Rest $\Delta V, dV/dt$) | 0.1651 | 0.0881 | 0.0960 | Neutral on rapid 10s screening; valuable for micro-short and diffusion recovery. |
| **A6** | Electrical + Thermal ($T_{\text{mean}}, \Delta T, dT/dt$) | 0.1672 | 0.0889 | 0.0970 | Thermal rise $<0.5^\circ\text{C}$ is within thermistor noise floor; worsens regression error. |
| **A7** | Electrical + Data Quality | 0.1651 | 0.0881 | 0.0960 | Telemetry completeness indicators have zero correlation with degradation ($r = 0.000$). |
| **A8** | Full Candidate Set (29 Features) | 0.1655 | 0.0880 | 0.0959 | Overparameterized model burdened by 79 collinear pairs. |
| **A9** | Provisionally Admitted Suite | **0.1646** | **0.0949** | **0.0972** | Compact candidate set. Physical MAE is nearly double synthetic MAE ($0.1646$ vs $0.0949$). |

### Baseline-Specific Improvement Quantification (Correction C)
When evaluating the improvement of Suite A2 on the real physical cohort ($N=12$):
- **Relative to Minimal Baseline A0 (`V_MEAN`)**:  
  $$\Delta \text{MAE}_{(\text{A2} - \text{A0})} = 0.1395 - 0.1785 = \mathbf{-0.0390} \text{ MAE} \quad (\text{A2 improved physical MAE by } 0.0390 \text{ relative to minimal A0})$$
- **Relative to Electrical-Only Baseline A1**:  
  $$\Delta \text{MAE}_{(\text{A2} - \text{A1})} = 0.1395 - 0.1651 = \mathbf{-0.0256} \text{ MAE} \quad (\text{Relative to A1 electrical-only, A2 improved physical MAE by } 0.0256)$$

> [!WARNING]
> Never report simply "A2 improves MAE by 0.0390" without explicitly specifying the baseline reference (A0 minimal baseline vs A1 electrical-only baseline).

---

## 3. Suite-Level vs. Individual Feature-Level Evidence (Correction D)

To audit Feature-Selection Optimism Bias, Nested Grouped Cross-Validation was executed (Outer LOBO across test batteries; Inner 4-fold Grouped CV across training batteries for feature selection and model fitting).

| Cohort | Naive LOBO MAE | Nested Grouped LOBO MAE | Selection Bias Optimism ($\Delta$ MAE) | Inner Loop Selected Suite |
|---|:---:|:---:|:---:|---|
| **Real Physical Cohort ($N=12$)** | **0.1646** | **0.1684** | **$+0.0038$** | `A2_ELEC_PLUS_PULSE` selected across 100% of folds |
| **Total Mixed Cohort ($N=112$)** | **0.0972** | **0.0975** | **$+0.0003$** | `A2_ELEC_PLUS_PULSE` selected across 100% of folds |

### Critical Separation Principle (Correction D)
> **Nested CV consistently selected the A2 pulse/electrical feature suite in 100% of outer folds, but this does not imply that every constituent feature provides independent incremental predictive value.**

Suite A2 represents an aggregate set (`V_MEAN`, `V_MIN`, `V_MAX`, `I_MEAN`, `I_ABS_MEAN`, `I_PEAK`, `P_MEAN`, `P_PEAK`, `DELTA_V_TOTAL`, `DELTA_V_OHMIC`, `R0_OHMIC`). Individual Leave-One-Feature-Out (LOFO) ablation must be used to evaluate whether each individual constituent feature provides independent incremental predictive information.

---

## 4. Individual Leave-One-Feature-Out (LOFO) & Fold-Level Robustness (Correction E)

Each candidate feature $X$ was ablated from the Full Candidate Set (Suite A8), measuring:
$$\Delta \text{MAE}_k = \text{MAE}_{(\text{Full} \setminus \{X\}), k} - \text{MAE}_{(\text{Full}), k}$$

### A. Real Physical Cohort ($N = 12$, Level 2 Evidence)

| Feature Name | Family | Mean $\Delta$ MAE | Median $\Delta$ MAE | 95% Confidence Interval | Cohen's $d$ | Paired $t$ $p$-value | Improved / Degraded Folds | Statistical Sig. | Engineering Sig. ($\ge 0.005$) | Final Phase-5.1 Status |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **`DELTA_V_TOTAL`** | PULSE | **+0.01355** | +0.00845 | [+0.00077, +0.02633] | **0.67** | **0.0382** | 9 / 3 | **YES** | **YES** | **PROVISIONALLY_SUPPORTED** |
| **`DELTA_V_OHMIC`** | PULSE | +0.00016 | +0.00011 | [-0.00034, +0.00065] | 0.20 | 0.4943 | 8 / 4 | NO | NO | **PROVISIONALLY_SUPPORTED / MODEST_EFFECT** |
| **`R0_OHMIC`** | PULSE | +0.00000 | +0.00000 | [0.00000, 0.00000] | 0.00 | 1.0000 | 0 / 12 | NO | NO | **CONTEXTUAL / PROVISIONAL** |
| **`RELAXATION_DELTA_V`**| RELAXATION | +0.00000 | +0.00000 | [0.00000, 0.00000] | 0.00 | 1.0000 | 0 / 12 | NO | NO | **INSUFFICIENT_INCREMENTAL_EVIDENCE** |
| **`V_MEAN`** | ELECTRICAL | -0.00192 | -0.00095 | [-0.00421, +0.00037] | -0.51 | 0.0912 | 3 / 9 | NO | NO | **CONDITIONAL** |

### B. Total Mixed Cohort ($N = 112$, Mixed Evidence)

| Feature Name | Family | Mean $\Delta$ MAE | Median $\Delta$ MAE | 95% Confidence Interval | Cohen's $d$ | Paired $t$ $p$-value | Improved / Degraded Folds | Statistical Sig. | Engineering Sig. ($\ge 0.005$) | Final Phase-5.1 Status |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **`DELTA_V_TOTAL`** | PULSE | **+0.00444** | +0.00096 | [+0.00139, +0.00749] | **0.27** | **0.0052** | 67 / 45 | **YES** | MARGINAL | **PROVISIONALLY_SUPPORTED** |
| **`DELTA_V_OHMIC`** | PULSE | **+0.00121** | +0.00067 | [+0.00049, +0.00194] | **0.31** | **0.0012** | 69 / 43 | **YES** | NO | **PROVISIONALLY_SUPPORTED / MODEST_EFFECT** |
| **`R0_OHMIC`** | PULSE | +0.00003 | +0.00000 | [0.00000, +0.00005] | 0.21 | 0.0286 | 22 / 90 | **YES** | NO | **CONTEXTUAL / PROVISIONAL** |
| **`RELAXATION_DELTA_V`**| RELAXATION | +0.00000 | +0.00000 | [0.00000, 0.00000] | 0.00 | 1.0000 | 0 / 112 | NO | NO | **INSUFFICIENT_INCREMENTAL_EVIDENCE** |
| **`V_MEAN`** | ELECTRICAL | -0.00073 | -0.00021 | [-0.00121, -0.00024] | -0.28 | 0.0037 | 34 / 78 | **YES (Degrades)**| NO | **CONDITIONAL** |

### Individual Feature Evidence Interpretations
1. **`DELTA_V_TOTAL` (PROVISIONALLY_SUPPORTED)**: Demonstrates the strongest individual physical-cohort evidence among all tested candidates ($\text{Mean } \Delta\text{MAE} = +0.01355$, Cohen's $d = 0.67$, $p = 0.0382$, improves 9 of 12 folds). Captures the total polarization envelope. Not universally validated; does not prove causal mechanism; not sufficient alone for safe qualification.
2. **`DELTA_V_OHMIC` (PROVISIONALLY_SUPPORTED / MODEST_EFFECT)**: Demonstrates modest predictive evidence. Statistically significant on the mixed cohort ($p = 0.0012$, Cohen's $d = 0.31$, 69/112 folds improved), but physical LOFO effect is small ($\text{Mean } \Delta\text{MAE} = +0.00016$, $p = 0.4943$). Characterized explicitly as modest.
3. **`R0_OHMIC` (CONTEXTUAL / PROVISIONAL)**: High collinearity with $\Delta V_{\text{ohmic}}$ under fixed 10A current ($r > 0.98$). Physical LOFO incremental value is 0.0. $>25\%$ shift across SOC regimes. Prohibited from universal health scalar claim; interpreted strictly as protocol- and operating-condition-dependent electrical observation.
4. **`RELAXATION_DELTA_V` (INSUFFICIENT_INCREMENTAL_EVIDENCE)**: Zero demonstrated incremental contribution to bulk SOH in 10s rapid screening ($\text{Mean } \Delta\text{MAE} = 0.00000$, 0/12 folds improved). Cataloged for future micro-short and diffusion recovery testing, but not a currently supported prognostic feature.
5. **`V_MEAN` (CONDITIONAL)**: Removing `V_MEAN` improves cross-battery generalization when unstratified across mixed chemistries ($\Delta\text{MAE} = -0.00192$ on physical cells, $p = 0.0037$ on mixed cohort). LFP flat plateau creates negative transfer with sloping NMC ($+0.477\,\text{V}$ shift). Strictly conditional on chemistry identification.

---

## 5. Mechanism Claim Demarcation & R0 Context Dependence (Corrections F & G)

### R0 Contextual Dependence (Correction F)
- $\text{SOC} = 15\%$: $R_0 = 12.38\,\text{m}\Omega$
- $\text{SOC} = 55\%$: $R_0 = 15.53\,\text{m}\Omega$
- $\text{SOC} = 75\%$: $R_0 = 15.62\,\text{m}\Omega$
- *Finding*: $R_0$ exhibits a $>25\%$ shift across SOC regimes. **$R_0$ is NOT a universal battery-health scalar.**
- Valid scientific interpretation: *"R0 demonstrates predictive utility under the tested protocol and validation regime as an observed electrical response conditioned on SOC, temperature, current amplitude, duration, and testbench cabling."*

### Mechanism Claim Retraction (Correction G)
- **Previous Overclaim**: "DELTA_V_OHMIC accurately resolves electrolyte conductivity and SEI degradation."
- **Retraction & Remediated Language**: Terminal pulse measurements aggregate bulk electrolyte resistance, separator tortuosity, electrode contact resistance, current collector welding, and measurement wiring. Terminal electrical measurements cannot isolate SEI layer thickness without three-electrode EIS or teardown.
- **Approved Terminology**: *"Terminal pulse measurements capture aggregate early-time electrical polarization / ohmic response associated with battery state."*

---

## 6. Sampling Rate, Thermal, & Data Quality Claims (Corrections H, I, J)

1. **Sampling Rate (Correction H)**:
   - *"The current RMK pulse protocol and R0 extraction method require approximately 10 Hz sampling under the tested conditions."*
   - Classified strictly as a **PROVISIONAL ENGINEERING REQUIREMENT**, not a universal law of battery physics.
2. **Thermal Evidence (Correction I)**:
   - Rapid 10s pulse heating is $<0.5^\circ\text{C}$, below thermistor accuracy ($\pm 0.5^\circ\text{C}$). Adding thermal features degrades SOH regression ($\Delta\text{MAE} = +0.0010$).
   - Approved phrasing: *"The tested rapid-screening thermal features did not demonstrate incremental SOH predictive value under the evaluated protocol."* Thermal sensing remains active in Layer 1 & 2 for safety boundaries, thermal runaway protection, and context gating.
3. **Data Quality Epistemic Separation (Correction J)**:
   - Pearson correlation with SOH is $r = 0.000$. Data quality metrics are **MEASUREMENT RELIABILITY SIGNALS**, not electrochemical health signals.
   - Retained in Layer 1 & 2 for measurement admissibility and DEFER decisions; excluded from SOH regression.

---

## 7. Final Phase 5.1 Accounting Invariant

The 30 cataloged features are strictly accounted for:
- **PROVISIONALLY_SUPPORTED (1)**: `DELTA_V_TOTAL`
- **PROVISIONALLY_SUPPORTED / MODEST_EFFECT (1)**: `DELTA_V_OHMIC`
- **CONTEXTUAL / PROVISIONAL (1)**: `R0_OHMIC`
- **INSUFFICIENT_INCREMENTAL_EVIDENCE (1)**: `RELAXATION_DELTA_V`
- **CONDITIONAL (5)**: `V_MEAN`, `T_MEAN`, `RELAXATION_SLOPE_DV_DT`, `DISCHARGE_AH`, `DISCHARGE_WH`
- **DEFERRED (1)**: `DQ_DV_PEAK`
- **REJECTED (20)**: `V_MIN`, `V_MAX`, `I_MEAN`, `I_ABS_MEAN`, `I_PEAK`, `P_MEAN`, `P_PEAK`, `CHARGE_AH`, `COULOMBIC_EFFICIENCY`, `CHARGE_WH`, `ENERGY_EFFICIENCY`, `T_MAX`, `DELTA_T`, `DT_DT`, `VALID_SAMPLE_FRACTION`, `INVALID_SAMPLE_FRACTION`, `CURRENT_FLOW_VALID`, `PULSE_VALID`, `TIMESTAMP_INTEGRITY`, `MEASUREMENT_DURATION`

$$\mathbf{1 + 1 + 1 + 1 + 5 + 1 + 20 = 30 \text{ Total Features}}$$
