# SECONDShift Benchmark Results & Scientific Validation Report

**Project:** SECONDShift — Risk-Constrained Adaptive Qualification Under State and Model Uncertainty  
**Audit Date:** 2026-10-02  
**Status:** REBUILT & INDEPENDENTLY AUDITED  
**Evidence Tier:** Multi-Tier Scientific Synthesis  
**Repository Document:** `secondshift/docs/RESULTS.md`  

---

## 1. Executive Summary

This document compiles the audited empirical results of the **SECONDShift** platform across the 12-specimen laboratory benchmark cohort, adversarial overconfidence stress tests, epistemic chemistry disambiguation suites, and hardware interlock benchmarks.

All numbers in this report derive strictly from the raw execution manifest (`data/processed/blind_validation_results.json`) and verified recomputations (`experiments/recompute_all_metrics.py`).

---

## 2. Primary 12-Specimen Benchmark Performance Matrix

All metrics are evaluated against ground truth on the 12-specimen edge-case benchmark cohort (5 Truly Safe, 7 Truly Unsafe; 8 LFP, 3 NMC, 1 Unknown).

| Evaluation Metric | Baseline A (Full OEM Cycler) [1] | Baseline B (Scalar SOH) [2] | Baseline C (Static Sigma) [2] | SECONDShift (Proposed) [3] | Statistical Significance / Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **True Positive (TP)** | 5 | 4 | 4 | **4** | Correctly qualified safe packs |
| **True Negative (TN)** | 4 | 0 | 0 | **7** | Correctly rejected unsafe packs |
| **False Positive (FP)** | 3 | 8 | 8 | **0** | Catastrophic False Acceptances |
| **False Negative (FN)** | 0 | 0 | 0 | **1** | Conservative False Rejections |
| **Classification Accuracy** | 75.00% [42.8%, 94.5%] | 33.33% [9.9%, 65.1%] | 33.33% [9.9%, 65.1%] | **91.67% [61.5%, 99.8%]** | Paired McNemar $p = 0.6250$ (Not Significant) [4] |
| **Qualified Acceptance Rate (QAR)** | 100.0% [47.8%, 100.0%] | 80.0% [28.4%, 99.5%] | 80.0% [28.4%, 99.5%] | **80.00% [28.4%, 99.5%]** | 4 of 5 truly safe specimens qualified |
| **False Acceptance Rate (FAR)** | 42.86% [9.9%, 81.6%] (3/7) | 100.00% [63.1%, 100.0%] (8/8) | 100.00% [63.1%, 100.0%] (8/8) | **0.00% [0.0%, 41.0%] (0/7)** | 1-Sided 95% UCB = **34.82%** [5] |
| **False Rejection Rate (FRR)** | 0.00% [0.0%, 52.2%] (0/5) | 0.00% [0.0%, 52.2%] (0/5) | 0.00% [0.0%, 52.2%] (0/5) | **20.00% [0.5%, 71.6%] (1/5)** | 1 marginal borderline pack derated/rejected |
| **Precision (PPV)** | 62.50% | 33.33% | 33.33% | **100.00%** | Zero false acceptances in qualified stream |
| **Balanced Accuracy** | 78.57% | 40.00% | 40.00% | **90.00%** | Arithmetic mean of Sensitivity and Specificity |
| **F1 Score** | 0.7692 | 0.5000 | 0.5000 | **0.8889** | Harmonic mean of Precision and Recall |
| **Mean Dwell Time ($t_{\text{dwell}}$)** | 10,800.0 s | 0.05 s | 0.05 s | **311.7 s** | Wilcoxon $W=0.0, p = 0.000488$ ($p < 0.001$) [6] |
| **Dwell Time Reduction** | Ref (0.0%) | N/A (Strawman) | N/A (Strawman) | **97.11% Reduction** | Statistically significant ($p < 0.001$) |
| **Mean Energy Consumed** | 22.40 Wh | 0.00 Wh | 0.00 Wh | **0.98 Wh** | 95.6% diagnostic energy savings |

---

### Footnotes & Methodological Disclosures

- **[1] Baseline A (Legitimate ATE Cycler Benchmark):** Represents standard automated test equipment executing a full CC-CV cycle at C/3 rate ($10,800\text{ s} \approx 3\text{ hr}$). Because it lacks chemistry disambiguation, Baseline A falsely accepts 3 unsafe NMC packs (`SPECIMEN_03`, `SPECIMEN_06`, `SPECIMEN_11`) based on misleading voltage readings, yielding $\text{FAR} = 42.86\%$.
- **[2] Baselines B and C (Illustrative Static Strawmen):** Baselines B and C are static prior evaluation models that take zero physical measurements ($t = 0.05\text{ s}$). They are included for pedagogical contrast and are **expressly designated as non-competitive strawmen**.
- **[3] SECONDShift Pipeline:** Executed in software simulation via `MockHermesHardware` using active VOI stopping and chemistry Bayesian inference.
- **[4] McNemar Paired Significance ($p = 0.6250$):** Across $N=12$ paired specimens, SECONDShift and Baseline A disagreed on only 4 specimens ($b=3, c=1$). The exact two-sided binomial McNemar test yields $p = 0.6250 > 0.05$. Therefore, **the classification accuracy superiority of SECONDShift over Baseline A is NOT statistically significant on $N=12$**, despite the apparent nominal difference ($91.7\%$ vs $75.0\%$).
- **[5] Sample Size Bounding on FAR:** Although $0$ out of $7$ unsafe specimens were accepted ($\text{FAR}_{\text{obs}} = 0.0\%$), the Clopper-Pearson exact 95% one-sided upper confidence bound on a sample of $N=7$ is $34.82\%$. An empirical sample of $N=7$ **cannot mathematically prove** the design target of $\text{FAR} < 1.0\%$. To prove $\text{FAR}_{95\%, \text{UCB}} \le 1.0\%$ with zero observed failures requires $N_{\text{unsafe}} \ge 299$ consecutive tests.
- **[6] Dwell Time Significance (Wilcoxon $p < 0.001$):** Unlike classification accuracy, the reduction in diagnostic dwell time from $10,800\text{ s}$ to $311.7\text{ s}$ is strongly statistically significant ($W = 0.0, p = 0.000488$, effect size $r = 0.88$).

---

## 3. Hardware Safety Interlock Latency

Hardware latency metrics represent **observed measurements from external laboratory oscilloscope bench testing**, not in-repo software loop execution:

| Safety Interlock Layer | Target Design Limit | Observed Hardware Benchmark [7] | Primary Protection Function |
| :--- | :---: | :---: | :--- |
| **LM393 Dual Analog Comparator** | $< 15.0\text{ ms}$ | **$11.8\text{ ms}$** | Autonomous over/under-voltage window trip |
| **TPS3823 Hardware Watchdog** | $< 250.0\text{ ms}$ | **$194.2\text{ ms}$** | MCU firmware stall / lockup trip |

- **[7] Single-Trace Bench Observation ($N=1$):** Latencies were recorded on a Rigol DS1054Z oscilloscope during prototype bring-up. They are single-instance bench observations, not fleet-scale statistical distributions. In-repository testing of these circuits operates via `MockHermesHardware`.

---

## 4. Adversarial & Chemistry Robustness Summary

- **Adversarial Overconfidence Attacks (14 stress modes):** Monotonic conservatism confirmed ($\partial P(\text{Conservative})/\partial \sigma \ge 0$, Cochran-Armitage $p < 0.0001$).
- **Epistemic Chemistry Disambiguation ($N=250$ cycles):** Across nominal random seeds, zero ambiguous packs were qualified into `OPERATE`. In 1 of 10 evaluated random seeds (Seed 123), an empirical $\text{FAR} = 10.0\%$ was observed on borderline disguised NMC cells under sensor noise, demonstrating the necessity of reporting seed variance.
