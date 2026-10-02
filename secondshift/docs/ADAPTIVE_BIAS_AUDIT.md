# Data Leakage, Parameter Alignment & Adaptive Bias Audit

**Project:** SECONDShift (Risk-Constrained Adaptive Qualification Under State and Model Uncertainty)  
**Document ID:** `DOC-BIAS-AUDIT`  
**Evaluation Standard:** Independent Scientific Bias and Leakage Forensics  
**Date of Audit:** October 2, 2026  

---

## 1. Executive Summary

$$\mathbf{CRITICAL\ FINDING:\ SIMULATION\ PARAMETER\ CO-DESIGN\ AND\ POST-HOC\ TUNING\ DETECTED}$$

A rigorous peer-review audit requires searching for hidden information leakage, parameter tuning on test specimens, and post-hoc threshold modifications. Our forensic audit identified three distinct forms of adaptive bias:

1. **Exact Simulation-Model Parameter Co-Design:** In `chemistry_engine.py`, the likelihood template means (`expected_lfp_drop = 0.022V`, `expected_nmc_drop = 0.038V`) match the exact mathematical constants used inside `MockHermesHardware` (`0.002V` pol + $10\text{A} \times 2.0\text{ m}\Omega = 0.022\text{V}$; `0.022V` pol + $10\text{A} \times 1.6\text{ m}\Omega = 0.038\text{V}$).
2. **Post-Hoc Metric Threshold Realignment:** Metric evaluation logic was modified during development from a single strict threshold ($SOH \ge 0.70$) to a tiered admissibility threshold ($SOH \ge 0.65$ for DERATE) after observing that `SPECIMEN_05` ($SOH = 0.67$) was flagging an apparent false acceptance.
3. **Absence of Independent Training/Holdout Split:** The 12 specimens were used to formulate the benchmark edge cases; there is no separate training cohort from which priors were learned. All priors are hand-crafted physical heuristics.

---

## 2. Forensic Breakdown of Identified Leakages & Biases

### 2.1. Parameter Alignment Between Mock Hardware and Inference Engine
- **Source Code Evidence:**
  - In `secondshift/software/hermes/hermes_driver.py` (lines 122-124):
    ```python
    v_pol = (0.022 if self.chemistries[i] == "NMC" else 0.002) * (eff_current / 10.0)
    v_term = ocv - (eff_current * self.r0[i]) - v_pol + noise
    ```
  - In `secondshift/software/chemistry/chemistry_engine.py` (lines 93-95):
    ```python
    expected_lfp_drop = 0.022 # 22mV typical (2.0 mOhm * 10A + 2mV pol)
    expected_nmc_drop = 0.038 # 38mV typical (1.6 mOhm * 10A + 22mV pol)
    sigma_slope = 0.006
    ```
- **Analysis:**
  The Bayesian likelihood template in `chemistry_engine.py` was hand-tuned to match the exact mathematical behavior of the synthetic hardware emulator.
- **Scientific Impact:**
  Because the likelihood templates are perfectly centered on the emulator's mean outputs, chemistry disambiguation achieves near-perfect separation in simulation ($P(\text{LFP}) = 0.994$). On real physical electrochemical cells, internal resistance and polarization vary with temperature, aging, and state of charge, which would broaden the observation distribution and reduce disambiguation confidence.

---

### 2.2. Post-Hoc Metric Rule Adjustment on `SPECIMEN_05`
- **Audit Trace:**
  - In initial development, a cell with $SOH < 0.70$ was classified as "globally unsafe."
  - When `SPECIMEN_05` ($SOH = 0.67, R_0 = 3.8\text{ m}\Omega$) was evaluated, it was designed to be safe for Derated duty ($0.5C$ continuous current).
  - The evaluation script was updated post-hoc to recognize tiered admissibility (`is_usable_derate` for $SOH \ge 0.65$ and $R_0 \le 4.0\text{ m}\Omega$).
- **Scientific Justification & Limitation:**
  While tiered admissibility is physically sound (derating current by $50\%$ reduces $I^2 R$ heat generation by $75\%$), adjusting evaluation rules after observing specimen behavior constitutes developmental tuning. In a strict double-blind study, operational rules must be frozen prior to specimen assignment.

---

### 2.3. Heuristic Priors vs "Learned" Priors
- **Audit Trace:**
  - Priors in `chemistry_engine.py` line 33:
    - `"KNOWN_LFP_FLEET"` $\to P(\text{LFP}) = 0.990, P(\text{NMC}) = 0.008, P(\text{UNKNOWN}) = 0.002$
    - `"TAGLESS_MIXED"` $\to P(\text{LFP}) = 0.500, P(\text{NMC}) = 0.450, P(\text{UNKNOWN}) = 0.050$
    - `"UNKNOWN"` $\to P(\text{LFP}) = 0.333, P(\text{NMC}) = 0.333, P(\text{UNKNOWN}) = 0.334$
- **Analysis:**
  These numbers were chosen by engineering intuition, not estimated via Maximum Likelihood Estimation (MLE) or empirical Bayes on a training fleet.
- **Required Scientific Framing:**
  The paper must state: **"Priors are hand-specified heuristic Dirichlet distributions representing intake documentation certainty, not empirically fitted parameters."**

---

## 3. Quantification of Bias Impact & Generalization Risk

If SECONDShift is deployed on real physical batteries without re-tuning:
1. **Electrolyte Aging Drift:** Aged LFP cells can develop higher transfer resistance, increasing total pulse drop from $22\text{ mV}$ to $35\text{ mV}$, which falls in the overlap zone with NMC ($38\text{ mV}$). With $\sigma_{\text{slope}} = 6\text{ mV}$, an aged LFP cell could be misclassified as AMBIGUOUS or NMC, increasing the False Rejection Rate.
2. **Temperature Sensitivity:** At $0^\circ\text{C}$, electrolyte viscosity increases impedance by $2\times - 3\times$. If the likelihood templates are not parameterized by temperature $T$, disambiguation confidence will degrade significantly.

---

## 4. Policy for Separation of Development vs Final Validation

To maintain rigorous scientific standards:
1. **Explicit Disclosure:** The paper must transparently disclose that the current likelihood parameters were calibrated to the nominal $25^\circ\text{C}$ electrochemical models of 20Ah LFP and NMC cells.
2. **Future Requirement:** A genuine 2-stage experimental protocol must be conducted in future work:
   - **Stage 1 (Calibration Set, $N=50$ cells):** Measure empirical distributions of $\Delta V_{\text{slope}}(SOC, T, SOH)$ across cells to fit likelihood parameters $(\mu, \sigma)$ via maximum likelihood.
   - **Stage 2 (Held-out Test Set, $N=100$ cells):** Evaluate frozen decision engine on unseen specimens without parameter modification.
