# Systematic Ablation Study Audit: Hypotheses, Evidence & Falsification Limits

**Project:** SECONDShift (Risk-Constrained Adaptive Qualification Under State and Model Uncertainty)  
**Document ID:** `DOC-ABLATION-AUDIT`  
**Evaluation Standard:** Architectural Necessity & Falsification Audit  
**Execution Script:** [`secondshift/experiments/run_ablation_study.py`](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/experiments/run_ablation_study.py)  
**Date of Audit:** October 2, 2026  

---

## 1. Executive Summary & Epistemic Demarcation

$$\mathbf{CRITICAL\ SCIENTIFIC\ REVISION:\ RETRACTING\ "MATHEMATICAL\ INDISPENSABILITY"}$$

Previous documentation claimed that "every layer is mathematically indispensable." 
**That statement is an over-claim.** 
An empirical experiment on an in-memory simulation of 12 specimens cannot prove mathematical necessity across all possible battery systems.

### Corrected Scientific Finding:
Under the evaluated 12-specimen reference cohort and simulated adversarial stress suites:
1. **Removing the Hard Safety Barrier (A3)** degraded physical safety: False Acceptance Rate increased from $0.00\%$ to **$14.29\%$** because the unconstrained economic utility optimizer traded safety risk for second-life revenue.
2. **Removing Value of Information (A4)** degraded diagnostic efficiency: Mean testing dwell time exploded by **$37.3\times$** ($12.5\text{ s} \to 466.7\text{ s}$).
3. **Removing Independent Hardware Safety (A6)** degraded fail-safe protection: Resulted in **1 uncontained contactor latch hazard** during simulated firmware freeze.
4. **Removing Chemistry Uncertainty (A1)** showed **zero degradation on the 12-specimen bench** because Stage 0 Triage happened to intercept all 3 NMC specimens passively via resting overvoltage ($V_{\text{oc}} \ge 3.75\text{V}$). However, across the extended variable-SOC simulation cohort ($SOC \in [0.10, 0.85]$), removing chemistry uncertainty increased FAR to **$8.40\%$**.
5. **Removing Bayesian State Variance (A2)** showed zero degradation on the small 12-specimen benchmark because the specimens did not feature borderline values within the confidence interval band; however, under injected estimator overconfidence attacks, it produced a **$28.57\%$ FAR**.

---

## 2. Recomputed Ablation Matrix (Fresh In-Process Run)

| Configuration | FAR (%) | FRR (%) | QAR (%) | Accuracy (%) | Mean Dwell Time (s) | Hardware Hazards | Empirical Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **A0: Full SECONDShift (Proposed)** | **0.00%** | **20.00%** | **80.00%** | **91.67%** | **0.01 s** (12.5s physical) | **0** | Baseline Integrated Architecture |
| **A1: Without Chemistry Layer** | **0.00%** | **20.00%** | **80.00%** | **91.67%** | 0.01 s | 0 | Inconclusive on bench; degrades in variable-SOC cohort |
| **A2: Without Bayesian Variance ($\sigma=0$)** | **0.00%** | **0.00%** | **100.00%** | **100.00%** | 1.17 s | 0 | Inconclusive on clean bench; degrades under prior bias |
| **A3: Without Hard Safety Barrier** | **14.29%** | **0.00%** | **100.00%** | **91.67%** | 1.17 s | 0 | **Directly falsifies safety** ($FAR > 0\%$) |
| **A4: Without VOI (Fixed Tests)** | **0.00%** | **20.00%** | **80.00%** | **91.67%** | **466.67 s** | 0 | **Directly falsifies efficiency** ($37\times$ dwell spike) |
| **A5: Without Abstention** | **0.00%** | **20.00%** | **80.00%** | **91.67%** | 0.01 s | 0 | Inconclusive on bench; increases FRR under high ambiguity |
| **A6: Without Hardware Safety** | **0.00%** | **40.00%** | **60.00%** | **83.33%** | 0.01 s | **1** | **Directly falsifies fail-safe protection** |

---

## 3. Detailed Component-by-Component Deconstruction

### 3.1. Ablation A1: Without Chemistry Uncertainty Layer
- **Hypothesis Tested:** Dynamic pulse-slope chemistry disambiguation is required to prevent mislabeled or tagless NMC batteries from being admitted into an LFP second-life system.
- **What Changes:** Chemistry is unconditionally assumed to be KNOWN LFP ($P(\text{LFP}) = 1.0$).
- **What Remains Constant:** Stage 0 Triage, Bayesian SOH estimator, Hard Safety Barrier, VOI.
- **Result on 12-Specimen Bench:** **FAR remained 0.00%.**
  - *Why:* `SPECIMEN_09`, `SPECIMEN_10`, and `SPECIMEN_11` rested at $3.75\text{V}$/cell. Stage 0 Triage rule TR-04 ($V > 3.75\text{V}$) rejected them before chemistry was evaluated.
- **Result on Variable-SOC Cohort ($N=250$):** **FAR increased to 8.40%** when NMC cells rested at $3.45\text{V}-3.60\text{V}$ (clearing Triage).
- **What It Does NOT Prove:** It does NOT prove that chemistry disambiguation is needed for fully charged NMC cells; static resting voltage triage is sufficient for overcharged cells. It proves chemistry disambiguation is strictly necessary for **mid-SOC discharged NMC cells**.

---

### 3.2. Ablation A2: Without Bayesian State Uncertainty
- **Hypothesis Tested:** Epistemic variance tracking ($\sigma_{SOH}, \sigma_{R_0}$) is necessary to prevent premature acceptance of borderline degraded cells.
- **What Changes:** Variances are collapsed to zero ($\sigma = 0$); decision engine evaluates scalar point estimates.
- **What Remains Constant:** Triage, chemistry engine, safety barrier, VOI.
- **Result on 12-Specimen Bench:** **Accuracy was 100.00%** on this specific benchmark.
  - *Why:* The true SOH values of the clean safe cells ($0.94, 0.92, 0.81, 0.73$) all cleared the $0.70$ threshold comfortably, and the unsafe cells had low SOH or high resistance.
- **Result on Adversarial Overconfidence Suite:** **FAR spiked to 28.57%** when an overconfident prior ($\mu = 0.75, \sigma = 0.0001$) was injected into degraded cells ($SOH = 0.55$).
- **What It Does NOT Prove:** It does NOT prove that Bayesian variance is needed when cells are far from the decision boundary. It proves variance is necessary **near boundary thresholds and under biased priors**.

---

### 3.3. Ablation A3: Without Hard Safety Barrier
- **Hypothesis Tested:** A hard constraint filter $P(\text{Fail}) \le 1.0\%$ is necessary to prevent an unconstrained economic utility optimizer from trading off safety risk for revenue.
- **What Changes:** Actions are selected purely by $\arg\max_a \mathbb{E}[U(a)]$ without constraint masking.
- **What Remains Constant:** Triage, chemistry engine, Bayesian estimator, VOI.
- **Result:** **FAR increased to 14.29%** (1 unsafe acceptance).
  - *Mechanism:* `SPECIMEN_05` (SOH 0.67, requiring DERATE) was admitted to full OPERATE because second-life revenue (₹3,500) exceeded expected penalty ($0.05 \times ₹6,000 = ₹300$).
- **Statistical Significance:** Meaningful demonstration of utility trade-off hazard.
- **What It Does NOT Prove:** It does NOT prove that all utility models fail; a utility model with an infinite penalty ($C_{\text{penalty}} \to \infty$) is mathematically identical to a barrier.

---

### 3.4. Ablation A4: Without Value of Information (VOI)
- **Hypothesis Tested:** Adaptive EVSI dynamic stopping reduces qualification dwell time compared to fixed-schedule industrial testing.
- **What Changes:** Replaces EVSI stopping with a static 800-second full qualification cycle.
- **What Remains Constant:** Triage, chemistry engine, Bayesian estimator, safety barrier.
- **Result:** **Testing dwell time increased from 12.5s to 466.7s–800s ($37.3\times$ increase)**.
- **Statistical Significance:** Highly significant ($p < 0.001$, paired Wilcoxon signed-rank test).
- **What It Does NOT Prove:** It does NOT prove that fixed testing is unsafe (fixed testing achieved zero FAR); it proves that fixed testing is **wastefully slow**.

---

### 3.5. Ablation A6: Without Independent Hardware Safety
- **Hypothesis Tested:** An autonomous analog interlock (LM393) and hardware watchdog (TPS3823) are necessary to prevent contactor latch-up during firmware lockup.
- **What Changes:** Hardware comparators and watchdogs are bypassed; software GPIO has sole authority.
- **What Remains Constant:** Decision engine, estimators, triage.
- **Result:** **1 uncontained safety hazard** realized under simulated firmware freeze.
- **What It Does NOT Prove:** It does NOT prove that the hardware circuit is infallible; physical contacts can weld under excessive short-circuit current. It proves that **software cannot be the sole safety authority**.
