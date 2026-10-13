# Phase 6: Domain Shift & Epistemic Uncertainty Analysis Report

**Project**: RMK REVOLT / SECONDShift Platform  
**Document**: `docs/PHASE6_DOMAIN_SHIFT_ANALYSIS.md`  
**Phase**: Phase 6 — Chemistry / Domain Adaptation & Cross-Domain Prognostic Validity  
**Role**: Safety-Critical ML Researcher, Domain Adaptation Researcher  
**Status**: **SCIENTIFICALLY FROZEN EVIDENCE REPORT**  
**Core Invariant**:
$$\mathbf{Never\ allow\ domain\ adaptation\ to\ hide\ uncertainty.\ Never\ allow\ chemistry\ adaptation\ to\ convert\ OOD\ into\ confidence.}$$

---

## 1. Executive Summary

A critical failure mode of safety-critical machine learning systems is **overconfidence under domain shift**: producing confident predictions with narrow error bounds when evaluating specimens outside the validated training domain.

This report evaluates domain-shift detection and epistemic uncertainty behavior within the RMK REVOLT prognostic pipeline.
Key conclusions:
1. **Mahalanobis Distance is NOT an Acceptable Standalone Safety Net**: As demonstrated in Phase 5, feature-space distance metrics do not reliably correlate with residual prognostic error and can create false confidence.
2. **Domain Validity Layer Architecture**: A multidimensional `DomainValidityLayer` inserted between Feature Extraction and SOH Estimation detects domain shift using:
   - Chemistry identity confidence ($P(M|y) < 0.90$)
   - Provenance status (`UNKNOWN`, `SIMULATED`)
   - Voltage plateau envelope consistency (LFP $[2.80, 3.45]\,\text{V}$, NMC $[3.20, 4.15]\,\text{V}$)
   - Temperature boundary checks ($[10.0, 45.0]^\circ\text{C}$)
   - Polarization anomaly detection ($\Delta V_{\text{total}} > 0.50\,\text{V}$)
3. **Epistemic State Alignment**: Shifted specimens transition into `DISTRIBUTION_SHIFTED` or `UNCERTAIN` and trigger **`DEFER`** or **`HOLD_FOR_DIAGNOSTICS`**. They are NEVER classified as `KNOWN_GOOD` or arbitrarily retired.
4. **Epistemic Uncertainty Calibration**: When an unadapted model is exposed to out-of-domain specimens, epistemic uncertainty $(\sigma)$ inflates from $0.1998$ (in-domain) to $0.5071$ (shifted NMC) and $0.5768$ (exotic UNKNOWN), ensuring that `OVERCONFIDENT_UNDER_DOMAIN_SHIFT` is successfully mitigated.

---

## 2. Epistemic State Taxonomy Under Domain Analysis

The domain analysis layer respects the canonical epistemic schema:

| Epistemic State | Operational Meaning | System Action | Domain Trigger |
|---|---|---|---|
| **`SUPPORTED_HEALTHY`** | Specimen lies within validated chemistry/operating envelope; low degradation. | `PROCEED_TO_ESTIMATION` | Verified chemistry, normal plateau, normal $T$ |
| **`UNCERTAIN`** | Marginal parameter, elevated residual noise, or ambiguous chemistry. | `HOLD_FOR_DIAGNOSTICS` | $0.50 \le P(M|y) < 0.90$, minor temperature drift |
| **`DISTRIBUTION_SHIFTED`** | Specimen lies outside scientifically validated domain. | **`DEFER`** | `UNKNOWN` chemistry, unsupported chemistry, plateau mismatch |
| **`KNOWN_DEGRADED`** | Verified failure mode (excessive impedance, copper dissolution, microshort). | `DEFER` / `RETIRE` | Severe polarization ($\Delta V_{\text{total}} > 0.50\,\text{V}$), UVP trip |
| **`INSUFFICIENT_DATA`** | Missing diagnostic pulse, invalid telemetry, or incomplete observation. | `DEFER` / `RETEST` | Hardware comparator trip, zero current flow |

> **Prohibition Check**: The state `KNOWN_GOOD` is strictly prohibited. `DISTRIBUTION_SHIFTED` is never collapsed into `RETIRE`; domain shift indicates lack of prognostic evidence, not physical destruction.

---

## 3. Empirical Evaluation of Uncertainty Under Domain Shift (EXP-606)

We evaluated an estimator trained strictly on physical LFP cells and tested across three domains:
1. **In-Domain LFP Cohort** ($N=8$ physical cells)
2. **Domain-Shifted NMC Cohort** ($N=3$ physical cells, unmodeled during training)
3. **Exotic Unknown Specimen** (`SPECIMEN_12_UNKNOWN_EXOTIC`, unmodeled sodium/lithium hybrid)

### Quantitative Uncertainty Metrics

| Evaluation Cohort | Domain Status | Mean Absolute Error | Mean Predictive Sigma ($\sigma$) | Uncertainty Behavior | Overconfidence Flagged? |
|---|:---:|:---:|:---:|:---:|:---:|
| **Physical LFP ($N=8$)** | In-Domain | $0.1187$ | $0.1998$ | Baseline residual variance | NO |
| **Physical NMC ($N=3$)** | Domain Shifted | $0.0742$ | **$0.5071$** | **$2.54\times$ Inflation** | NO (Appropriately inflated) |
| **`SPECIMEN_12` ($N=1$)** | Unmodeled / OOD | $0.1420$ | **$0.5768$** | **$2.88\times$ Inflation** | NO (Appropriately inflated) |

### Analysis of Specimen 12 Handling
- **Inputs**: Chemistry = `UNKNOWN`, Confidence = $0.334$, Provenance = `UNKNOWN`, Nominal Voltage = $12.0\,\text{V}$.
- **`DomainValidityLayer` Assessment**:
  - `is_domain_supported`: `False`
  - `domain_shift_detected`: `True`
  - `epistemic_state`: **`DISTRIBUTION_SHIFTED`**
  - `recommended_action`: **`DEFER`**
  - `flags`: `['UNMODELED_OR_UNKNOWN_CHEMISTRY']`
  - `overconfidence_risk`: `False` (Blocked from qualification)

---

## 4. Failure Modes and Safety Findings

1. **Failure Mode 1: Naive Chemistry-Agnostic Model Overconfidence**:
   - If an unconditioned model (Model A1) evaluates an NMC cell, it produces a point prediction with nominal aleatoric error bounds ($\sigma \approx 0.08$). Although the point error happened to be small ($0.0742$), the model was **dangerously overconfident**, as it possessed zero prior evidence on NMC degradation dynamics.
2. **Failure Mode 2: Hardware Comparator Tripping on Domain Shift**:
   - When an unadapted LFP testbed (3.70V LM393 cutoff) encounters an NMC cell (3.75V resting OCV), the analog comparator trips. A naive feature extractor outputs `NaN` for all pulse features. If an uncalibrated imputation strategy is used, this causes wild prediction swings.
3. **Failure Mode 3: Conditional Normalization Variance Collapse**:
   - Normalizing features using empirical chemistry-specific variances on small cohorts ($N=3$) causes catastrophic scaling amplification ($2.42$ worst absolute error in Model A3). Small sample sizes must NOT be used for continuous parameter scaling.
