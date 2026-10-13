# Phase 6.1: Model Comparability & Risk/Accuracy Tradeoff Audit

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: [`docs/PHASE6_1_MODEL_COMPARABILITY.md`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/docs/PHASE6_1_MODEL_COMPARABILITY.md)  
**Status**: AUDITED & MATHEMATICALLY VERIFIED  
**Metric Comparability Status**: `DIRECTLY_COMPARABLE`  

---

## 1. Audit of Reported A0–A6 Metrics

Phase 6 reported Mean Absolute Error (MAE) metrics across seven model configurations evaluated on the real physical cohort:

$$\text{A0} = 0.1384,\quad \text{A1} = 0.1370,\quad \text{A2} = 0.1595,\quad \text{A3} = 0.3865,\quad \text{A4} = 0.1485,\quad \text{A5} = 0.1679,\quad \text{A6} = 0.1507$$

### Verification of Experimental Basis

To prevent comparisons across mismatched evaluation conditions, the audit verified the provenance and pipeline parameters for every model configuration:

| Dimension | Verification Finding | Identical Across A0–A6? |
|---|---|:---:|
| **Evaluation Dataset** | Real Physical Cohort ($N=12$) from `ground_truth_registry.json` | **YES** |
| **Data Origin** | Physical hardware testbench observations (SELV 4S LFP / single NMC) | **YES** |
| **Cross-Validation Split** | Leave-One-Battery-Out (`BatteryDisjointSplitter.split_lobo`), 12 folds | **YES** |
| **Battery-Disjoint Integrity** | Test battery specimen strictly excluded from training fold | **YES** |
| **Evaluation Target** | Canonical State of Health (`true_soh`), bounded on $[0.0, 1.0]$ | **YES** |
| **Missing Value Imputation** | Training fold median imputation (`safe_impute`), zero test leakage | **YES** |
| **Regularization Parameter** | Ridge regression penalty $\alpha = 1.0$ across all estimators | **YES** |
| **Random Seed** | Fixed seed ($42$) governing deterministic execution | **YES** |
| **Aggregation Formula** | $\text{MAE} = \frac{1}{K} \sum_{k=1}^K |y_k - \hat{y}_k|$ across all 12 test folds | **YES** |

### Mathematical Comparability Ruling

Because every model configuration was fitted and scored on the **exact same 12 folds of the exact same 12 physical specimens**, the reported errors are:

$$\mathbf{STRICTLY\ DIRECTLY\ COMPARABLE}$$

---

## 2. Model Architecture & Feature Breakdown

| Model Key | Architecture Description | Feature Set Used | Normalization / Gating Method | Physical LOBO MAE | Worst Error |
|---|---|---|---|:---:|:---:|
| **A0** | Unstratified Phase 5 baseline | `V_MEAN` | Global unstandardized | $0.1384$ | $0.3744$ |
| **A1** | Naive pooled multi-feature model | `DELTA_V_TOTAL`, `DELTA_V_OHMIC`, `V_MEAN` | Global unstandardized | **$0.1370$** | $0.3826$ |
| **A2** | Chemistry-stratified sub-models | `DELTA_V_TOTAL`, `DELTA_V_OHMIC`, `V_MEAN` | Per-chemistry independent fitting | $0.1595$ | $0.5199$ |
| **A3** | Chemistry-conditioned normalized model | `DELTA_V_TOTAL`, `DELTA_V_OHMIC`, `V_MEAN` | Training-only continuous z-score per chemistry | $0.3865$ | $2.4222$ |
| **A4** | Hierarchical shared shrinkage model | `DELTA_V_TOTAL`, `DELTA_V_OHMIC`, `V_MEAN` | Shrinkage toward global prior ($\lambda=5.0$) | $0.1485$ | $0.3989$ |
| **A5** | Domain-adaptive pulse-invariant model | `DELTA_V_TOTAL`, `DELTA_V_OHMIC` | Pulse-only features without voltage plateaus | $0.1679$ | $0.5316$ |
| **A6** | Domain-adaptive with epistemic gating | `DELTA_V_TOTAL`, `DELTA_V_OHMIC` | Pulse features + `DomainValidityLayer` DEFER | $0.1507$ | $0.5316$ |

---

## 3. The Central Research Tradeoff: Model A1 vs Model A6

A primary contribution of the Phase 6.1 audit is clarifying the scientific relationship between Model A1 and Model A6:

> **RESEARCH QUESTION**:  
> *Is Model A6 preferable to Model A1 for risk-constrained qualification, even though Model A6 exhibits a higher average MAE?*

### Quantified Risk/Accuracy Tradeoff Table

| Performance Metric | Model A1 (Chemistry-Naive Pooled) | Model A6 (Domain-Adaptive + Gated) | Delta (A6 vs A1) | Operational Significance |
|---|:---:|:---:|:---:|---|
| **Average Physical MAE** | **$0.1370$** | **$0.1507$** | **$+0.0137$ (+9.98%)** | A1 is numerically more accurate on in-domain cells |
| **Worst Physical Error** | **$0.3826$** | **$0.5316$** | $+0.1490$ | A6 error on challenging in-domain fold is higher |
| **Out-of-Domain False Acceptance** | **$8.33\%$ (1/12)** | **$0.00\%$ (0/12)** | **$-8.33\%$ (ELIMINATED)** | A1 accepts exotic unmodeled cell; A6 DEFERS |
| **Operational DEFER Rate** | $0.00\%$ (0/12) | $8.33\%$ (1/12) | $+8.33\%$ | A6 routes exotic specimen to laboratory diagnostics |
| **Reliance on Spurious Features** | High (`V_MEAN`) | Zero (pulse invariant) | Voltage removed | A1 suffers negative transfer under unmodeled voltage |
| **Domain Risk Posture** | **Vulnerable / Overconfident** | **Risk-Constrained / Domain-Aware** | **Conservative** | Fundamental difference in safety posture |

### Scientific Analysis: What Accuracy Is Sacrificed to Prevent False Acceptance?

1. **Why A1 Attains Lower Average MAE**:
   Model A1 includes `V_MEAN` in its feature vector. Within the dominant LFP cohort (8 of 12 specimens), steady-state voltage correlates with State of Charge and nominal health. By exploiting voltage plateau information, A1 shaves $0.0137$ off its average MAE across the cohort.
2. **Why A1 Is Dangerous**:
   When evaluating `SPECIMEN_12_UNKNOWN_EXOTIC`, Model A1 naively evaluates the exotic cell without domain checks, outputting a confident SOH prediction ($\hat{y} = 0.634$) that has zero physical validity. It exhibits an **$8.33\%$ false confident acceptance rate**.
3. **The Architectural Role of A6**:
   Model A6 intentionally strips `V_MEAN` because cell voltage is a non-transferable domain proxy ($d = 3.82$). By relying strictly on pulse dynamics ($\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$) and coupling with `DomainValidityLayer`, Model A6 detects that `SPECIMEN_12` possesses unmodeled chemistry, assigns an epistemic state of `DISTRIBUTION_SHIFTED`, and triggers an operational `DEFER`.
4. **Conclusion**:
   Model A6 is **NOT** "more accurate." Calling it more accurate is scientifically false. Model A6 is **RISK-CONSTRAINED AND DOMAIN-AWARE**: it sacrifices $0.0137$ average MAE on known cells in exchange for complete elimination of confident false acceptance on unmodeled domains.

---

## 4. Re-scoping of Model A3 Normalization Failure

In Phase 6 reports, the failure of Model A3 ($\text{MAE} = 0.3865$, $\text{Worst Error} = 2.4222$) was described with the overly broad claim:
> *"Continuous parameter scaling on small cohorts is mathematically unsound."*

### The Audit Correction

Continuous feature normalization (z-scoring, whitening) is a mathematically sound linear transformation. What failed in Model A3 was not the mathematics of normalization, but its numerical stability under an extreme small-sample setting:

1. **The Mechanism of Failure**:
   Under LOBO cross-validation on NMC cells ($N=3$), training folds contained only 2 NMC cells. For feature `DELTA_V_TOTAL`, the two training NMC cells had near-identical voltage sags ($0.0382\,\text{V}$ and $0.0384\,\text{V}$).
2. **Sample Variance Collapse**:
   The sample standard deviation estimated on these two points collapsed toward zero:

   $$\hat{\sigma}_{\text{NMC}} = \sqrt{\frac{1}{2-1} \sum_{i=1}^2 (x_i - \bar{x})^2} \approx 0.00014\,\text{V}$$

3. **Numerical Explosion**:
   When the held-out test cell ($0.0400\,\text{V}$) was normalized:

   $$z_{\text{test}} = \frac{0.0400 - 0.0383}{0.00014} \approx 12.14$$

   This enormous standardized feature value multiplied by the ridge regression weight produced a runaway test prediction of $\hat{y} = 3.122$, generating a catastrophic absolute error of $2.4222$ on a target bounded by $[0, 1]$.

### Approved Re-scoped Language
> *"The tested continuous chemistry-conditioned normalization implementation was unstable under the available small-N NMC cohort, with sample variance estimates collapsing toward zero ($\hat{\sigma} \to 0$) and causing severe division-by-near-zero scaling instability. This is an implementation and sample-size limitation of the evaluated empirical estimator, not a universal proof that normalization is mathematically invalid."*
