# Statistical Power Analysis & Sample Size Roadmap

**Project:** SECONDShift (Risk-Constrained Adaptive Qualification Under State and Model Uncertainty)  
**Document ID:** `DOC-POWER-ROADMAP`  
**Evaluation Standard:** Binomial Power Analysis & Minimum Sample Size Sizing  
**Execution Script:** [`secondshift/experiments/run_statistical_inference.py`](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/experiments/run_statistical_inference.py)  
**Date of Audit:** October 2, 2026  

---

## 1. Executive Summary: Sizing the Empirical Evidence Gap

$$\mathbf{DATASET\ SCALE\ AUDIT:\ CURRENT\ N = 12\ vs\ REQUIRED\ N \ge 300}$$

A critical finding of our statistical audit is that **the current $N=12$ testbed is statistically underpowered** to prove high-confidence population safety claims. This document establishes the exact mathematical sample sizes required to convert research prototype observations into definitive, peer-reviewed scientific proof.

| Research Claim / Safety Goal | Null Hypothesis ($H_0$) | Current Sample ($N$) | Required Sample ($N_{\text{req}}$) | Evidence Status |
| :--- | :---: | :---: | :---: | :--- |
| **Fleet Population FAR $< 1.0\%$** | $\text{FAR} \ge 0.010$ | $N_{\text{unsafe}} = 7$ | **$N_{\text{unsafe}} \ge 299$** | **UNDERPOWERED** (Satisfied only in simulation) |
| **Decision Accuracy $> 85.0\%$** | $\text{Accuracy} \le 0.850$ | $N = 12$ | **$N \ge 60$** | **UNDERPOWERED** ($p = 0.625$ in paired test) |
| **Hazard Detection Sensitivity $> 90.0\%$** | $\text{Sensitivity} \le 0.900$ | $N_{\text{unsafe}} = 7$ | **$N_{\text{unsafe}} \ge 59$** | **UNDERPOWERED** |

---

## 2. Mathematical Derivations of Required Sample Sizes

### 2.1. Fleet Population FAR $< 1.0\%$ at 95% Confidence (Zero-Failure Rule)
- **Goal:** Demonstrate that the true population False Acceptance Rate is strictly below $1.0\%$ ($\alpha = 0.01$) with $95\%$ statistical confidence, assuming zero false acceptances ($k = 0$) are observed during physical qualification.
- **Formulation (Clopper-Pearson Binomial One-Sided Upper Bound):**
  $$\text{UCB}_{95\%} = 1 - (1 - 0.95)^{1/N_{\text{unsafe}}} = 1 - (0.05)^{1/N_{\text{unsafe}}} \le 0.010$$
  $$(0.05)^{1/N_{\text{unsafe}}} \ge 0.990$$
  $$\frac{1}{N_{\text{unsafe}}} \ln(0.05) \ge \ln(0.990)$$
  $$N_{\text{unsafe}} \ge \frac{\ln(0.05)}{\ln(0.990)} = \frac{-2.99573}{-0.01005} \approx \mathbf{298.07}$$
- **Required Sample Size:** **$N_{\text{unsafe}} \ge 299$ consecutive zero-failure trials** ($\approx 300$ unsafe specimens).
- **Comparison to Current Benchmark:** The current testbed contains $N_{\text{unsafe}} = 7$. Observing zero failures in $7$ trials yields:
  $$\text{UCB}_{95\%}(N=7) = 1 - (0.05)^{1/7} = 1 - 0.6518 = \mathbf{34.82\%}$$
  *Scientific Finding:* $N=7$ proves that FAR is bounded below $34.8\%$, but **cannot mathematically prove FAR $< 1.0\%$**. Fleet-scale simulation ($N=300$) satisfies this bound, but physical proof awaits the expanded testbed.

---

### 2.2. Demonstrating Decision Accuracy $> 85.0\%$ (Power $= 80\%$, $\alpha = 0.05$)
- **Goal:** Falsify the null hypothesis $H_0: p \le 0.85$ in favor of $H_1: p = 0.95$ with $80\%$ statistical power ($\beta = 0.20$) at one-sided significance $\alpha = 0.05$.
- **Formulation (Asymptotic Proportion Power Equation):**
  $$N = \left[ \frac{z_{1-\alpha} \sqrt{p_0 (1 - p_0)} + z_{1-\beta} \sqrt{p_1 (1 - p_1)}}{p_1 - p_0} \right]^2$$
  Where $z_{0.95} = 1.645$, $z_{0.80} = 0.842$, $p_0 = 0.85$, $p_1 = 0.95$:
  $$N = \left[ \frac{1.645 \sqrt{0.85 \times 0.15} + 0.842 \sqrt{0.95 \times 0.05}}{0.95 - 0.85} \right]^2$$
  $$N = \left[ \frac{1.645 \times 0.3571 + 0.842 \times 0.2179}{0.10} \right]^2 = \left[ \frac{0.5874 + 0.1835}{0.10} \right]^2 = [7.709]^2 = \mathbf{59.43}$$
- **Required Sample Size:** **$N \ge 60$ distinct physical battery specimens.**

---

### 2.3. Demonstrating Hazard Detection Sensitivity $> 90.0\%$ (Power $= 80\%$, $\alpha = 0.05$)
- **Goal:** Falsify $H_0: \text{Sensitivity} \le 0.90$ in favor of $H_1: \text{Sensitivity} = 0.98$ with $80\%$ statistical power.
- **Formulation:**
  $$N_{\text{unsafe}} = \left[ \frac{1.645 \sqrt{0.90 \times 0.10} + 0.842 \sqrt{0.98 \times 0.02}}{0.98 - 0.90} \right]^2$$
  $$N_{\text{unsafe}} = \left[ \frac{1.645 \times 0.3000 + 0.842 \times 0.1400}{0.08} \right]^2 = \left[ \frac{0.4935 + 0.1179}{0.08} \right]^2 = [7.642]^2 = \mathbf{58.40}$$
- **Required Sample Size:** **$N_{\text{unsafe}} \ge 59$ degraded / hazardous specimens.**

---

## 3. Experimental Scaling Roadmap

To elevate SECONDShift from an academic proof-of-concept to an indisputable tier-1 research publication, we propose a three-stage experimental expansion:

```
[ STAGE 1: Current Benchmark (Completed) ]
N = 12 Specimens (8 LFP, 3 NMC, 1 Unknown)
Status: Proves algorithmic functionality, EVSI dwell reduction (p < 0.001), and mock safety interlocks.

       │
       ▼
[ STAGE 2: Powered Academic Publication Benchmark ]
N = 60 Specimens (30 LFP, 20 NMC, 10 Mislabeled/Degraded)
Target: Statistically demonstrates Decision Accuracy > 85% (p < 0.05) and Sensitivity > 90%.

       │
       ▼
[ STAGE 3: Industrial Pre-Certification Fleet ]
N = 300 Unsafe + 200 Safe Specimens (N_total = 500)
Target: Statistically proves physical population FAR < 1.0% at 95% Clopper-Pearson confidence.
```

---

## 4. Policy for Manuscript Disclosures

1. The research paper must explicitly state: **"The reference testbed of $N=12$ demonstrates algorithmic correctness and achieves statistically significant dwell time reduction ($p < 0.001$). Proving a fleet population FAR $< 1.0\%$ at 95% confidence requires $N \ge 299$ zero-failure trials, which is verified in simulation and forms the objective of our expanded testbed."**
2. Never claim that $N=12$ is "fleet-scale." Always refer to it as an "edge-case laboratory benchmark."
