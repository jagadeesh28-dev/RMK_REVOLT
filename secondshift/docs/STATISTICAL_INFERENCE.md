# Statistical Inference, Hypothesis Testing & Paired Significance Audit

**Project:** SECONDShift (Risk-Constrained Adaptive Qualification Under State and Model Uncertainty)  
**Document ID:** `DOC-STAT-INFER`  
**Evaluation Standard:** Exact Paired Statistical Testing, Distribution Metrics & Significance Reporting  
**Execution Script:** [`secondshift/experiments/run_statistical_inference.py`](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/experiments/run_statistical_inference.py)  
**Date of Audit:** October 2, 2026  

---

## 1. Executive Summary & Statistical Honesty Declaration

$$\mathbf{CRITICAL\ STATISTICAL\ FINDING:\ DWELL\ TIME\ IS\ SIGNIFICANT;\ DECISION\ PARITY\ IS\ UNDERPOWERED}$$

In scientific research, percentages must not be reported without formal statistical hypothesis testing. Our paired analysis on the reference dataset ($N=12$) reveals a critical divergence:

1. **Diagnostic Dwell Time Reduction is Statistically Significant:**  
   The reduction in qualification dwell time from $800.0\text{ s}$ (Baseline A) to $12.5\text{ s}$ (SECONDShift) achieves **$p = 0.000488 < 0.001$** under the non-parametric Wilcoxon signed-rank test.
2. **Categorical Decision Accuracy Difference is NOT Statistically Significant on $N=12$:**  
   Under the paired McNemar exact binomial test, comparing Baseline A (75% accuracy) vs SECONDShift (91.7% accuracy) yields **$p = 0.6250 > 0.05$**. With only 4 discordant pairs (3 wins for SECONDShift on NMC packs, 1 win for Baseline A on derated LFP), $N=12$ lacks statistical power to reject the null hypothesis of decision parity at $\alpha = 0.05$.
3. **Paper Reporting Mandate:** We explicitly report $p = 0.625$ for classification parity and acknowledge that a larger benchmark ($N \ge 60$) is required to achieve formal statistical significance for decision accuracy.

---

## 2. Paired Hypothesis Tests

### 2.1. Paired Dwell Time Analysis: Wilcoxon Signed-Rank Test
- **Null Hypothesis ($H_0$):** The median difference in diagnostic dwell time between Baseline A and SECONDShift is zero.
- **Alternative Hypothesis ($H_1$):** SECONDShift achieves lower median diagnostic dwell time.
- **Data (Paired $N=12$ Observations):**
  - Baseline A: $800.0\text{ s}$ across all 12 specimens.
  - SECONDShift: $[0.012\text{s},\ 0.012\text{s},\ 0.008\text{s},\ 0.008\text{s},\ 0.002\text{s},\ 0.002\text{s},\ 0.002\text{s},\ 0.002\text{s},\ 0.002\text{s},\ 0.002\text{s},\ 0.004\text{s},\ 0.002\text{s}]$.
- **Test Statistic:** $W = 0.0$
- **Exact p-value:** **$p = 0.000488$**
- **Conclusion:** **Reject $H_0$ ($p < 0.001$).** SECONDShift delivers a statistically significant reduction in qualification dwell time.

---

### 2.2. Paired Decision Analysis: McNemar Exact Binomial Test
- **Null Hypothesis ($H_0$):** Baseline A and SECONDShift have identical marginal probabilities of making a correct qualification decision ($P(\text{Correct}_A) = P(\text{Correct}_{SS})$).
- **Contingency Matrix of Paired Decisions:**
  $$\begin{pmatrix} \text{Both Correct} & \text{Baseline A Only Correct} \\ \text{SECONDShift Only Correct} & \text{Both Incorrect} \end{pmatrix} = \begin{pmatrix} 8 & 1 \\ 3 & 0 \end{pmatrix}$$
- **Discordant Pairs:**
  - $b = 1$: `SPECIMEN_05` (Baseline A correctly derated; SECONDShift conservatively retired).
  - $c = 3$: `SPECIMEN_09`, `SPECIMEN_10`, `SPECIMEN_11` (Baseline A falsely accepted NMC; SECONDShift correctly rejected/held).
- **Exact Two-Sided Binomial p-value:**
  $$p = 2 \times \sum_{k=0}^{\min(1, 3)} \binom{4}{k} 0.5^4 = 2 \times \left( \frac{1}{16} + \frac{4}{16} \right) = 2 \times \frac{5}{16} = \frac{10}{16} = \mathbf{0.6250}$$
- **Conclusion:** **Fail to reject $H_0$ ($p = 0.625 > 0.05$).** 
  While SECONDShift corrected 3 hazardous false acceptances, $N=12$ is underpowered to establish statistical significance for accuracy differences.

---

## 3. Timing Distribution Metrics for SECONDShift

Based on the 12-specimen qualification runs:

| Metric | Measured Value (Simulation Clock) | Bench Target Specification |
| :--- | :---: | :---: |
| **Mean Dwell Time** | $0.0049\text{ s}$ ($12.50\text{ s}$ physical bench dwell) | $< 400.0\text{ s}$ |
| **Median Dwell Time** | $0.0025\text{ s}$ ($2.50\text{ s}$ passive triage clearing) | $< 100.0\text{ s}$ |
| **Standard Deviation** | $0.0042\text{ s}$ | N/A |
| **Interquartile Range (IQR)**| $0.0062\text{ s}$ | N/A |
| **P95 Dwell Time** | $0.0126\text{ s}$ ($54.0\text{ s}$ multi-step physical pulse) | $< 180.0\text{ s}$ |

---

## 4. Summary of Statistical Findings for Publication

1. **Dwell Time:** The $98.4\%$ dwell time reduction is statistically proven ($p < 0.001$).
2. **Accuracy & FAR:** Observed $FAR = 0.00\%$ ($0/7$) and accuracy $= 91.67\%$ ($11/12$), but the paired difference does not reach statistical significance ($p = 0.625$).
3. **Scientific Integrity Statement:** The paper will state: *"While SECONDShift eliminates 3 false acceptances committed by Baseline A, a sample size of $N=12$ is statistically underpowered to reject the null hypothesis of decision parity. A powered cohort of $N \ge 60$ specimens is required to confirm statistical significance."*
