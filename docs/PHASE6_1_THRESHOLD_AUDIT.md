# Phase 6.1: Chemistry-Confidence Threshold Audit

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: [`docs/PHASE6_1_THRESHOLD_AUDIT.md`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/docs/PHASE6_1_THRESHOLD_AUDIT.md)  
**Status**: AUDITED & RIGOROUSLY SCOPED  
**Current Threshold Classification**: `PROVISIONAL_ENGINEERING_THRESHOLD`  
**Optimization Status**: `THRESHOLD_OPTIMIZATION_UNDERPOWERED`  

---

## 1. Origin and Justification Audit of $P(M|y) < 0.90$

In the Phase 6 `DomainValidityLayer`, the rule governing chemistry confidence evaluation was specified as:

$$\text{If } P(M \mid y) < 0.90 \implies \text{Flag: AMBIGUOUS\_CHEMISTRY\_IDENTITY} \implies \text{Action: HOLD\_FOR\_DIAGNOSTICS}$$

### Origin Audit
1. **Source**: The threshold originated in `ChemistryDisambiguationEngine` as a heuristic engineering demarcation between:
   - $P(M \mid y) \ge 0.990$: High-confidence known chemistry (`KNOWN`)
   - $0.900 \le P(M \mid y) < 0.990$: Probable chemistry identity (`PROBABLE`)
   - $P(M \mid y) < 0.900$: Ambiguous chemistry identity requiring additional diagnostics (`AMBIGUOUS`)
2. **Empirical Calibration Status**: The value $0.90$ was **NOT empirically calibrated** against receiver operating characteristic (ROC) curves, Precision-Recall curves, or cost-sensitive utility functions. It was selected as an intuitive engineering default.
3. **Audit Verdict**: It is a **provisional engineering threshold**, not an experimentally optimized decision boundary.

---

## 2. Sensitivity Analysis Across Candidate Thresholds

To quantify the operational impact of the confidence threshold without re-running full training campaigns, a sensitivity sweep was executed across:

$$\tau \in \{0.50,\, 0.60,\, 0.70,\, 0.80,\, 0.90,\, 0.95,\, 0.99\}$$

Each threshold was evaluated across the 12 physical specimens and an ambiguous synthetic sweep ($P(M \mid y) \in [0.40, 0.98]$).

### Sensitivity Sweep Results Table

| Candidate Threshold ($\tau$) | Physical DEFER Rate | Physical HOLD Rate | Physical PROCEED Rate | False Confident Acceptance Rate | Known LFP False DEFER Rate | Unknown Detection Rate | Ambiguous Sweep HOLD Rate | Ambiguous Sweep PROCEED Rate | Threshold Status |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **0.50** | $16.7\%$ (2/12) | $0.0\%$ (0/12) | $83.3\%$ (10/12) | **0.0%** | $12.5\%$* | **100.0%** | $14.3\%$ | $85.7\%$ | PROVISIONAL |
| **0.60** | $16.7\%$ (2/12) | $0.0\%$ (0/12) | $83.3\%$ (10/12) | **0.0%** | $12.5\%$* | **100.0%** | $28.6\%$ | $71.4\%$ | PROVISIONAL |
| **0.70** | $16.7\%$ (2/12) | $0.0\%$ (0/12) | $83.3\%$ (10/12) | **0.0%** | $12.5\%$* | **100.0%** | $42.9\%$ | $57.1\%$ | PROVISIONAL |
| **0.80** | $16.7\%$ (2/12) | $0.0\%$ (0/12) | $83.3\%$ (10/12) | **0.0%** | $12.5\%$* | **100.0%** | $57.1\%$ | $42.9\%$ | PROVISIONAL |
| **0.90 (Current)** | **16.7% (2/12)** | **0.0% (0/12)** | **83.3% (10/12)** | **0.0%** | **12.5%*** | **100.0%** | **71.4%** | **28.6%** | **PROVISIONAL** |
| **0.95** | $16.7\%$ (2/12) | $0.0\%$ (0/12) | $83.3\%$ (10/12) | **0.0%** | $12.5\%$* | **100.0%** | $85.7\%$ | $14.3\%$ | PROVISIONAL |
| **0.99** | $16.7\%$ (2/12) | $0.0\%$ (0/12) | $83.3\%$ (10/12) | **0.0%** | $12.5\%$* | **100.0%** | $100.0\%$ | $0.0\%$ | PROVISIONAL |

*\*Note on Known LFP False DEFER Rate: The 1 DEFER among 8 LFP cells is triggered by the severe impedance/polarization safety rule ($\Delta V_{\text{total}} > 0.50\,\text{V}$ on `SPECIMEN_06_HIGH_RES_LFP`), which is classified as `KNOWN_DEGRADED`, not by chemistry misclassification.*

---

## 3. Why Threshold Optimization Is Underpowered

The sensitivity sweep demonstrates an essential statistical reality:
1. **Discontinuous Physical Cohort**: In the physical cohort of 12 cells:
   - 8 LFP cells have verified laboratory provenance ($P = 0.99$)
   - 3 NMC cells have verified laboratory provenance ($P = 0.99$)
   - 1 UNKNOWN cell has unmodeled telemetry ($P = 0.334$)
2. **Invariance of Physical Decision**: Because there are **zero physical specimens** with intermediate confidence scores between $0.35$ and $0.98$, **every threshold from 0.50 to 0.95 produces the exact same binary classification**:
   - `SPECIMEN_12` ($P = 0.334 < \tau$) is always detected and deferred.
   - All 11 LFP/NMC cells ($P = 0.99 > \tau$) always pass the chemistry confidence check.
3. **Statistical Underpowering**: Calculating an empirical optimum requires a continuous density of borderline specimens. With zero observations in $[0.35, 0.95]$, standard optimization methods (Youden's $J$ statistic, cost-minimization) have a degenerate objective function with an unidentifiable flat plateau.

Therefore, the audit formally rules:
$$\mathbf{THRESHOLD\ OPTIMIZATION:\ UNDERPOWERED}$$

---

## 4. Fundamental Invariant: Chemistry Identification $\ne$ SOH Estimation

A vital requirement of the Phase 6.1 audit is enforcing that chemistry disambiguation does not become a hidden health scalar:

$$\text{CHEMISTRY IDENTIFICATION} \ne \text{SOH ESTIMATION}$$

1. **Orthogonal Physical Concepts**:
   - Chemistry identification answers: *What electrochemical system produced these observations?*
   - SOH estimation answers: *How much degradative capacity loss and impedance growth has this specific specimen accumulated?*
2. **The Danger of Entanglement**: A model that can reliably distinguish an LFP cell from an NMC cell (e.g., via the $0.477\,\text{V}$ plateau difference) does not thereby possess any predictive validity regarding the remaining capacity or cycle life of either cell.
3. **Architectural Guardrail**: Chemistry confidence $P(M \mid y)$ is strictly restricted to domain validity gating. It must never be passed as a feature, prior, or continuous scalar into the SOH estimation regression model.

---

## 5. Approved Phase 6.1 Language

### Retracted / Forbidden Language
- *"The 0.90 threshold has been validated to eliminate misclassification risk."*
- *"0.90 is the mathematically optimal confidence cutoff."*

### Approved Canonical Language
> *"The threshold $P(M \mid y) < 0.90$ is designated as a PROVISIONAL ENGINEERING THRESHOLD. It effectively identifies unmodeled chemistries on the tested cohort without producing false rejections of known specimens. However, because the physical dataset lacks borderline confidence observations between 0.35 and 0.95, threshold optimization is currently underpowered and has not been prospectively calibrated against a representative physical domain-validation cohort."*
