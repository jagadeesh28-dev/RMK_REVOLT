# Phase 5.1 Feature Utility & Evidence Freeze Matrix

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/FEATURE_VALIDATION_MATRIX.md`  
**Phase**: Phase 5.1 — Scientific Evidence-Freeze Correction & Finalization  
**Governing Principle**:  
$$\text{COMPUTABLE} \ne \text{IMPLEMENTATION-VALID} \ne \text{PHYSICALLY VALIDATED} \ne \text{PROGNOSTICALLY SUPPORTED} \ne \text{UNIVERSALLY VALID} \ne \text{CAUSALLY INTERPRETED}$$  
**Single Source of Truth**: 30 Total Cataloged Features (29 Candidate Features + 1 Deferred Feature)  
**Specimen Evidence Cohort**:
- **Real Physical Cohort**: $N = 12$ physical cells (8 LFP, 3 NMC, 1 UNKNOWN) — *Level 2 Evidence*
- **Synthetic Cohort**: $N = 100$ simulated specimens (50 LFP, 50 NMC) — *Level 1 Evidence*
- **Total Computational Cohort**: $N = 112$ computational specimens — *Mixed Evidence*

---

## 1. Summary of Feature Admission Classification (Phase 5.1 Final)

| Status | Count | Description | Features |
|---|:---:|---|---|
| **PROVISIONALLY_SUPPORTED** | **1** | Strongest individual physical-cohort LOFO evidence (Mean $\Delta\text{MAE} = +0.01355$, $p = 0.0382$, Cohen's $d = 0.67$, improves 9 of 12 folds). Captures total overpotential envelope (ohmic + fast charge transfer). Not universally validated; no causal mechanism claim. | `DELTA_V_TOTAL` |
| **PROVISIONALLY_SUPPORTED / MODEST_EFFECT** | **1** | Modest individual physical LOFO effect ($\Delta\text{MAE} = +0.00016$, $p = 0.4943$, 8/12 improved); statistically significant on mixed cohort ($\Delta\text{MAE} = +0.00121$, $p = 0.0012$, 69/112 improved). Mechanism interpreted as aggregate early-time electrical polarization / ohmic response (NOT direct SEI isolation). | `DELTA_V_OHMIC` |
| **CONTEXTUAL / PROVISIONAL** | **1** | Observed electrical response influenced by SOC, temperature, current amplitude, pulse duration, and cabling. Physical LOFO incremental value is 0.0 under fixed current. $>25\%$ shift across SOC regimes. Prohibited from universal health scalar claim. | `R0_OHMIC` |
| **INSUFFICIENT_INCREMENTAL_EVIDENCE** | **1** | No demonstrated incremental LOFO contribution to bulk SOH under tested 10s screening protocol (Physical $\Delta\text{MAE} = 0.00000$, 0/12 folds improved). Cataloged for future micro-short and diffusion recovery testing, but not a currently supported prognostic feature. | `RELAXATION_DELTA_V` |
| **CONDITIONAL** | **5** | Valid strictly under explicitly defined operating boundaries (chemistry identification and OCV plateau conditioning for `V_MEAN`, safety and context gating for `T_MEAN`, extended $\ge 30\,\text{s}$ rest for `RELAXATION_SLOPE_DV_DT`, full discharge cycle for `DISCHARGE_AH`/`DISCHARGE_WH`). | `V_MEAN`, `T_MEAN`, `RELAXATION_SLOPE_DV_DT`, `DISCHARGE_AH`, `DISCHARGE_WH` |
| **DEFERRED** | **1** | Valid electrochemical concept (differential capacity phase transitions), but uncomputable under rapid intake screening protocol without low-rate C/20 cycle. | `DQ_DV_PEAK` |
| **REJECTED** | **20** | Collinear without incremental value, electronic load stimulus proxies, derivative noise amplification, or telemetry data-quality indicators ($r = 0.000$). DQ indicators remain active in Layers 1 & 2 for measurement admissibility and DEFER gating. | `V_MIN`, `V_MAX`, `I_MEAN`, `I_ABS_MEAN`, `I_PEAK`, `P_MEAN`, `P_PEAK`, `CHARGE_AH`, `COULOMBIC_EFFICIENCY`, `CHARGE_WH`, `ENERGY_EFFICIENCY`, `T_MAX`, `DELTA_T`, `DT_DT`, `VALID_SAMPLE_FRACTION`, `INVALID_SAMPLE_FRACTION`, `CURRENT_FLOW_VALID`, `PULSE_VALID`, `TIMESTAMP_INTEGRITY`, `MEASUREMENT_DURATION` |
| **TOTAL** | **30** | Exactly accounts for all 30 cataloged features ($1 + 1 + 1 + 1 + 5 + 1 + 20 = 30$). | |

---

## 2. Mandatory Feature Evidence Table (14-Column Specification)

| Feature ID | Family | Real Evidence | Synthetic Evidence | Battery-Disjoint Evidence | Temporal Evidence | Noise Robustness | Incremental Value | Domain Dependence | Measurement Cost (s) | Mechanism Confidence | Prognostic Status | Evidence Level | Final Phase-5.1 Status |
|---|---|:---:|:---:|:---:|:---:|---|:---:|---|:---:|---|---|:---:|:---:|
| **`DELTA_V_TOTAL`** | PULSE | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.989$) | $+0.01355$ ($p=0.0382$) | RATE_SOC_CONDITIONED | 10.0 | AGGREGATE_ELECTRICAL | PROVISIONALLY_SUPPORTED | Level 2 | **PROVISIONALLY_SUPPORTED** |
| **`DELTA_V_OHMIC`** | PULSE | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.981$) | $+0.00016$ ($p=0.4943$) | RATE_SOC_CONDITIONED | 0.1 | AGGREGATE_ELECTRICAL | PROVISIONALLY_SUPPORTED / MODEST_EFFECT | Level 2 | **PROVISIONALLY_SUPPORTED / MODEST_EFFECT** |
| **`R0_OHMIC`** | PULSE | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.984$) | $0.00000$ ($p=1.0000$) | SOC_TEMP_CONDITIONED | 0.1 | AGGREGATE_ELECTRICAL | CONTEXTUAL / PROVISIONAL | Level 2 | **CONTEXTUAL / PROVISIONAL** |
| **`RELAXATION_DELTA_V`**| RELAXATION | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.991$) | $0.00000$ (Neutral) | DURATION_CONDITIONED | 10.0 | AGGREGATE_ELECTRICAL | INSUFFICIENT_INCREMENTAL_EVIDENCE | Level 2 | **INSUFFICIENT_INCREMENTAL_EVIDENCE** |
| **`V_MEAN`** | ELECTRICAL | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.998$) | $-0.00192$ (Unstratified) | CHEMISTRY_CONDITIONAL | 1.0 | AGGREGATE_ELECTRICAL | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`T_MEAN`** | THERMAL | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.999$) | $-0.00112$ (Harmful) | AMBIENT_CONDITIONAL | 1.0 | ENVIRONMENTAL_CONTEXT | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`RELAXATION_SLOPE_DV_DT`**| RELAXATION| Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Moderate ($\tau = 0.724$) | $0.00000$ | DURATION_CONDITIONED | 30.0 | AGGREGATE_ELECTRICAL | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`DISCHARGE_AH`** | COULOMETRIC | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.999$) | $0.00000$ (Intake) | CYCLE_DEPTH_CONDITIONAL| 18000.0 | DIRECT_ELECTROCHEMICAL | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`DISCHARGE_WH`** | ENERGY | Level 2 ($N=12$) | Level 1 ($N=100$) | Strict LOBO-CV | $t_{\text{feat}} \le t_{\text{dec}}$ | Robust ($\tau = 0.999$) | $0.00000$ (Intake) | CYCLE_DEPTH_CONDITIONAL| 18000.0 | DIRECT_ELECTROCHEMICAL | CONDITIONAL | Level 2 | **CONDITIONAL** |
| **`DQ_DV_PEAK`** | ICA | None | Level 0 | Invalid in Rapid | Offline Only | Sensitive to ADC noise | N/A | LOW_RATE_ONLY | 18000.0 | DIRECT_ELECTROCHEMICAL| INSUFFICIENT_EVIDENCE | Level 0 | **DEFERRED** |
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

## 3. Evidence Strength & Limitation Demarcation

1. **Physical Sample Size Limitation**:
   - Physical cohort $N = 12$ cells (8 LFP, 3 NMC, 1 UNKNOWN).
   - NMC $N = 3$ is **exploratory evidence**.
   - Single UNKNOWN chemistry cell cannot support chemistry-specific conclusions.
   - Cross-chemistry and cross-form-factor generalization are strictly **NOT established**. Prospective validation has not been performed.
2. **Evidence Hierarchy Level Demarcation**:
   - Current physical cohort evidence is classified as **Level 2** (`LEVEL_2_SMALL_PHYSICAL_COHORT`), NOT Level 3, 4, or 5.
   - Simulation cohort evidence is classified as **Level 1** (`LEVEL_1_SIMULATION_COHORT`).
   - Software/untested features are classified as **Level 0** (`LEVEL_0_SOFTWARE_SYNTHETIC`).
3. **No Direct Mechanism Identification**:
   - Terminal pulse electrical measurements aggregate bulk electrolyte resistance, separator tortuosity, tab/current collector welds, contact resistance, and testbench cabling.
   - Claims that $\Delta V_{\text{ohmic}}$ or $R_0$ directly measure SEI layer degradation are **RETRACTED**.
