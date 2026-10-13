# Phase 6: Model Ablation & Worst-Case Safety Evaluation Report

**Project**: RMK REVOLT / SECONDShift Platform  
**Document**: `docs/PHASE6_ABLATION_RESULTS.md`  
**Phase**: Phase 6 — Chemistry / Domain Adaptation & Cross-Domain Prognostic Validity  
**Role**: Principal Battery Prognostics Research Engineer, Safety-Critical ML Researcher  
**Status**: **SCIENTIFICALLY FROZEN EVIDENCE REPORT**  
**Core Invariant**:
$$\mathbf{Never\ allow\ a\ better\ aggregate\ metric\ to\ override\ a\ worse\ cross\text{-}domain\ safety\ outcome.}$$

---

## 1. Executive Summary

In safety-critical battery second-life qualification, selecting a model based solely on minimum average mean absolute error (MAE) is dangerous. An algorithm may attain a marginally lower average MAE by exploiting spurious correlation (such as unstratified cell voltage) while exhibiting catastrophic errors or severe overconfidence on out-of-distribution battery chemistries.

This report documents the systematic ablation of seven candidate models (A0 through A6) across the real physical cohort ($N=12$) under battery-disjoint Leave-One-Battery-Out cross-validation (LOBO-CV).

### Key Empirical Findings
1. **Model A1 (Chemistry-Naive Pooled)** achieved the lowest average MAE ($0.1370$), but did so by fitting an unstratified voltage line that cannot distinguish chemistry differences from degradation.
2. **Model A3 (Chemistry-Conditioned Normalization) Catastrophically Failed**: Normalizing feature scale by empirical chemistry variance produced severe variance explosion on small sample sizes ($N=3$), resulting in an unacceptably high worst-case error ($2.4222$) and mean MAE of $0.3865$.
3. **Model A6 (Domain-Adaptive + Epistemic Uncertainty Gating)** provided the best safety profile: it utilizes pulse-invariant degradation features ($\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$) and automatically triggers a safe **DEFER** when a specimen belongs to an unsupported or unmodeled domain (`SPECIMEN_12_UNKNOWN_EXOTIC`), achieving $0.0\%$ unsupported-domain false acceptance.

---

## 2. Model Ablation Matrix (EXP-607)

All seven architectures were evaluated across the 12 physical LOBO folds using identical battery-disjoint splits:

| Model ID | Architecture Description | Feature Suite | Physical LOBO MAE | Physical LOBO RMSE | Median Absolute Error | Worst Battery Error | 95th Percentile Error | Worst Chemistry MAE | DEFER Rate |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **A0** | Phase 5.1 Minimal Baseline | $V_{\text{mean}}$ unstratified | $0.1384$ | $0.1781$ | $0.1281$ | $0.3744$ | $0.3098$ | $0.1599$ | $0.0\%$ |
| **A1** | Chemistry-Naive Pooled Ridge | $\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}, V_{\text{mean}}$ | **$0.1370$** | **$0.1776$** | **$0.1235$** | $0.3826$ | $0.3117$ | $0.1589$ | $0.0\%$ |
| **A2** | Chemistry-Stratified Ridge | Sub-models per chemistry | $0.1595$ | $0.2098$ | $0.1322$ | $0.5199$ | $0.3821$ | $0.1800$ | $0.0\%$ |
| **A3** | Chemistry-Conditioned Normalization | Conditional $z$-score Ridge | $0.3865$ | $0.7920$ | $0.1274$ | **$2.4222$** | **$1.7675$** | **$0.4730$** | $0.0\%$ |
| **A4** | Hierarchical Shared Shrinkage | Global prior + chem shrinkage | $0.1485$ | $0.1842$ | $0.1318$ | $0.3989$ | $0.3268$ | $0.1638$ | $0.0\%$ |
| **A5** | Domain-Adaptive Pulse | Pulse-only ($\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$) | $0.1679$ | $0.2198$ | $0.1671$ | $0.5316$ | $0.3842$ | $0.2062$ | $0.0\%$ |
| **A6** | **Domain-Adaptive + Epistemic Gating** | **Pulse + Epistemic DEFER** | **$0.1507$** | **$0.2116$** | **$0.1283$** | **$0.5316$** | **$0.3842$** | **$0.1821$** | **$8.3\%$** |

---

## 3. Detailed Model Analyses

### Model A0: Minimal Phase 5.1 Baseline (`V_MEAN`)
- **Evaluation**: LOBO $\text{MAE} = 0.1384$.
- **Mechanism**: Relies strictly on average terminal voltage.
- **Vulnerability**: Fails completely under domain shift because a fresh NMC cell ($3.75\text{V}$) is predicted as having unphysically high capacity/health if evaluated with an LFP intercept.

### Model A1: Chemistry-Naive Pooled Model
- **Evaluation**: LOBO $\text{MAE} = 0.1370$ (numerically lowest average MAE).
- **Mechanism**: Fits a single pooled hyperplane across LFP and NMC data.
- **Safety Flaw**: Exploits the correlation between higher NMC nominal voltage and moderate SOH values in the training set. It lacks epistemic awareness and remains confident on out-of-domain cells.

### Model A2: Chemistry-Stratified Models
- **Evaluation**: LOBO $\text{MAE} = 0.1595$.
- **Mechanism**: Routes cells to chemistry-specific sub-models.
- **Limitation**: Suffers on physical NMC folds ($N=3$) because fitting a multi-parameter Ridge model on only 2 training cells produces severe parameter estimation variance.

### Model A3: Chemistry-Conditioned Normalization (Negative Result)
- **Evaluation**: LOBO $\text{MAE} = 0.3865$, Worst Error = **$2.4222$**.
- **Root Cause of Failure**: Standardizing by sample standard deviation $\hat{\sigma}_{\text{chem}}$ on $N=3$ cells creates unstable denominators ($\hat{\sigma} \to 0$), causing test-point predictions to explode.
- **Scientific Implication**: Continuous parameter normalization cannot be performed reliably on small physical cohorts ($N < 30$).

### Model A4: Hierarchical Shared Shrinkage Model
- **Evaluation**: LOBO $\text{MAE} = 0.1485$.
- **Mechanism**: Shrinks chemistry-specific regression vectors toward a global shared prior:
  $$w_{\text{chem}} = \left(X_c^T X_c + \lambda_{\text{shrink}} I\right)^{-1} \left(X_c^T y_c + \lambda_{\text{shrink}} w_{\text{global}}\right)$$
- **Finding**: Stabilizes small-sample estimation relative to Model A2, reducing worst-group error from $0.1800$ to $0.1638$.

### Model A5: Domain-Adaptive Model (Pulse Invariant)
- **Evaluation**: LOBO $\text{MAE} = 0.1679$.
- **Mechanism**: Strips all voltage plateaus and relies solely on polarization features ($\Delta V_{\text{total}}, \Delta V_{\text{ohmic}}$).
- **Finding**: Robust across chemistries, but exhibits slightly higher baseline error ($0.1679$) because it loses the within-chemistry baseline offset.

### Model A6: Domain-Adaptive with Epistemic Gating (Recommended Architecture)
- **Evaluation**: LOBO $\text{MAE} = 0.1507$, Worst Group MAE = $0.1821$.
- **Mechanism**: Combines pulse-invariant features with the `DomainValidityLayer`. When evaluating an unsupported or unmodeled domain (`SPECIMEN_12`), the model triggers a safe **`DEFER`** rather than attempting extrapolation.
- **Safety Superiority**: Eliminates false confident acceptance of unmodeled chemistries.

---

## 4. Worst-Case & Safety-Oriented Metrics (EXP-608)

| Safety Metric | Naive Model A1 | Stratified Model A2 | Adaptive Gated Model A6 | Safety Requirement |
|---|:---:|:---:|:---:|:---:|
| **Worst-Group (Chemistry) MAE** | $0.1589$ | $0.1800$ | $0.1821$ | Must not silently mask worst group |
| **Worst Single Battery Error** | $0.3826$ | $0.5199$ | $0.5316$ | Bound worst-case failure |
| **95th Percentile Absolute Error** | $0.3117$ | $0.3821$ | $0.3842$ | Constrain tail error |
| **Maximum Overconfidence Under Shift** | **HIGH** | MODERATE | **ZERO (Gated)** | $\sigma$ must inflate under shift |
| **False Confident Acceptance Rate** | **$8.3\%$** | $8.3\%$ | **$0.0\%$** | Zero unmodeled cells accepted |
| **Unsupported Domain Acceptance Rate** | **$100\%$** | $0.0\%$ | **$0.0\%$** | Block unsupported chemistries |
| **DEFER Rate on Unsupported Domains** | $0.0\%$ | $0.0\%$ | **$100.0\%$** | Must trigger DEFER on OOD |
