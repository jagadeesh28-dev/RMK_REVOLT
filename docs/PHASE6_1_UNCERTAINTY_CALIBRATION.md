# Phase 6.1: Uncertainty Calibration Audit

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: [`docs/PHASE6_1_UNCERTAINTY_CALIBRATION.md`](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/docs/PHASE6_1_UNCERTAINTY_CALIBRATION.md)  
**Status**: AUDITED & RIGOROUSLY SCOPED  
**Result**: `UNCERTAINTY_CALIBRATION_NOT_ESTABLISHED`  

---

## 1. Governing Distinction: Responsiveness vs Calibration

A cornerstone finding of the Phase 6 exploratory investigation was that predictive standard deviation $\sigma$ inflated when models trained exclusively on LFP were evaluated on NMC and exotic UNKNOWN specimens:

- **In-Domain LFP**: Mean $\sigma \approx 0.1998$
- **Shifted NMC**: Mean $\sigma \approx 0.5071$ ($2.54\times$ inflation)
- **Shifted UNKNOWN**: Mean $\sigma \approx 0.5812$ ($2.91\times$ inflation)

In Phase 6 reports, this behavior was characterized as:
> *"Overconfident Under Domain Shift: FALSE / Overconfidence successfully eliminated."*

### The Scientific Correction

A rise in epistemic uncertainty under domain shift establishes **Uncertainty Responsiveness**, NOT **Uncertainty Calibration**.

```
UNCERTAINTY RESPONSIVENESS:
Does the uncertainty metric increase when an out-of-distribution specimen is presented?
[DEMONSTRATED IN PHASE 6]
       ≠
UNCERTAINTY CALIBRATION:
Does the numerical uncertainty estimate quantitatively correspond to the true statistical error distribution?
[UNVALIDATED IN PHASE 6 / 6.1]
```

Uncertainty calibration requires that for any predicted confidence level $1 - \alpha$, the empirical probability that the true target $y$ falls within the prediction interval $[\hat{y} - z_{\alpha/2}\sigma, \hat{y} + z_{\alpha/2}\sigma]$ asymptotically matches $1 - \alpha$, and that $\sigma$ scales monotonically with the expected conditional absolute error $\mathbb{E}[|y - \hat{y}| \mid x]$.

Inflation alone is merely a heuristic penalty. Without empirical calibration against a representative physical test cohort, wide intervals give an illusion of safety through sheer uninformative breadth.

---

## 2. Quantitative Calibration Audit on Physical Cohort

Using the audited physical cohort ($N=12$), predictions and epistemic standard deviations were evaluated using the Phase 6 ridge epistemic model (trained on LFP, evaluated across all physical cells).

### Empirical Calibration Metrics

| Evaluation Cohort | Sample Size ($N$) | Mean Absolute Error ($\overline{|e|}$) | Mean Predicted Sigma ($\overline{\sigma}$) | Ratio $\overline{|e|} / \overline{\sigma}$ | Nominal 95% Coverage | Mean 95% Interval Width ($3.92\overline{\sigma}$) | Pearson $r(|e|, \sigma)$ | $p$-value |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **In-Domain LFP** | 8 | $0.1186$ | $0.1998$ | $0.5938$ | $100.0\%$ | $0.7832$ | $+0.6633$ | $0.0729$ |
| **Shifted NMC** | 3 | $0.0742$ | $0.5071$ | $0.1463$ | $100.0\%$ | $1.9879$ | $-0.9337$ | $0.2332$ |
| **Shifted UNKNOWN** | 1 | $0.1418$ | $0.5812$ | $0.2440$ | $100.0\%$ | $2.2783$ | N/A ($N=1$) | N/A |
| **Overall Cohort** | **12** | **$0.1094$** | **$0.3084$** | **$0.3547$** | **$100.0\%$** | **$1.2089$** | **$-0.0036$** | **$0.9912$** |

### Mathematical Regression of Error on Sigma

In a well-calibrated Gaussian predictive model, the relationship between absolute error $|e|$ and standard deviation $\sigma$ satisfies:

$$\mathbb{E}[|e| \mid \sigma] = \sqrt{\frac{2}{\pi}} \sigma \approx 0.7979 \cdot \sigma$$

A linear regression of actual prediction error $|e_i|$ against predicted standard deviation $\sigma_i$ across the physical cohort yielded:

$$\widehat{|e|} = -0.0017 \cdot \sigma + 0.1100 \quad (R^2 = 0.00001, p = 0.991)$$

The empirical calibration slope is $-0.0017$, diverging completely from the theoretical expected slope $+0.7979$. The rank correlation is equally uninformative ($\text{Spearman } \rho = 0.1958, p = 0.542$).

---

## 3. Why Full Calibration Cannot Be Established

The audit identifies three definitive reasons why uncertainty calibration cannot be claimed:

### 1. Severe Sample Size Underpowering
Reliability diagrams, quantile binning, and calibration error metrics (such as Expected Calibration Error, ECE) require large sample sizes ($N \ge 100$) with dense sampling across error quantiles. The physical domain-shifted cohort contains only $N=3$ NMC cells and $N=1$ UNKNOWN cell. It is statistically impossible to construct empirical CDFs or validate coverage rates on 4 shifted specimens.

### 2. Excessive Interval Dilation Exceeding Physical Scale
While empirical coverage under nominal 95% intervals is technically $100.0\%$ across all 12 cells, this coverage is achieved vacuously. For NMC cells, the mean interval width is:

$$\text{Full Width}_{95\%} = 2 \times 1.96 \times 0.5071 = 1.9879 \text{ SOH units} \quad (\text{Half Width} = 1.96\sigma = 0.9939 \text{ SOH units})$$

For the UNKNOWN cell, the raw unclipped 95% full interval width expands to:

$$\text{Full Width}_{95\%} = 2 \times 1.96 \times 0.5812 = 2.2783 \text{ SOH units} \quad (\text{Half Width} = 1.96\sigma = 1.1391 \text{ SOH units})$$

State of Health (SOH) is physically bounded on the unit interval $[0.0, 1.0]$. These are raw, unclipped Gaussian predictive intervals from the linear ridge epistemic model. A raw uncertainty interval with full-width spanning $\sim 2.0$ to $2.3$ SOH units (and half-width exceeding $1.0$) is wider than the entire physical state space of the battery. An uninformative interval trivially covers the true value, but cannot be called "calibrated."

### 3. Heuristic Distance Penalty Formulation
The epistemic uncertainty in `CrossDomainRidgeModel` is calculated as:

$$\sigma_i = \sigma_{\text{base}} \times \left(1.0 + 0.5 \frac{\|z_i\|_2}{\sqrt{D}}\right) \times \gamma_{\text{OOD}}$$

where $\gamma_{\text{OOD}} = 2.5$ if chemistry is outside the training set. The factor $2.5$ is an arbitrary engineering inflation factor, not a posterior marginal variance derived from a calibrated Bayesian neural network, Gaussian process, or empirical conformal procedure.

---

## 4. Policy on Conformal Prediction and New Algorithms

In strict adherence to Phase 6.1 constraints:
- **No Conformal Prediction Introduced**: Conformal prediction was NOT implemented in Phase 6.1. Introducing split-conformal inference or non-conformity scores without a sufficiently powered physical calibration set ($N \ge 50$) would produce unstable non-exchangeable bounds under domain shift.
- **No Algorithm Replacement**: The underlying uncertainty model was not altered. Modifying the algorithm merely to manufacture a favorable calibration metric is scientifically invalid.

---

## 5. Official Phase 6.1 Language & Final Determination

### Retracted / Superseded Language
- *"Overconfidence successfully eliminated."*
- *"Uncertainty is calibrated under domain shift."*
- *"Predictive intervals validate safe cross-chemistry deployment."*

### Approved Phase 6.1 Canonical Language
> *"The tested domain-shift scenarios produced increased epistemic uncertainty ($\sigma$ inflated $2.54\times$ to $2.88\times$) and triggered appropriate DEFER behavior on unmodeled specimens. Calibration of uncertainty against independent physical prediction error remains unvalidated due to sample size limitations ($N_{\text{NMC}}=3, N_{\text{UNK}}=1$) and heuristic variance scaling."*

### Formal Status
$$\mathbf{UNCERTAINTY\ CALIBRATION:\ UNVALIDATED}$$
