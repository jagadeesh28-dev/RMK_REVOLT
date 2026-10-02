# SECONDShift Research Hypothesis & Falsification Framework (`RESEARCH_HYPOTHESIS.md`)

```
====================================================================================================
PROJECT: SECONDShift — Risk-Constrained Adaptive Qualification Under State and Model Uncertainty
STATUS: HYPOTHESIS FROZEN | FALSIFIABLE SCIENTIFIC FRAMEWORK
CORE INVARIANT: EVIDENCE > FEATURES | NULL HYPOTHESES EXPLICITLY TESTED
DATE: October 2026
====================================================================================================
```

---

## 1. Central Research Hypothesis

> **Primary Scientific Hypothesis ($H_{\text{central}}$):**  
> *"A battery qualification system that explicitly models battery-state uncertainty, chemistry/model identity uncertainty, and failure-risk constraints can reduce diagnostic testing effort (time and energy) while maintaining a predefined maximum unsafe-acceptance risk ($\text{FAR} \le 1.0\%$) compared with fixed-duration battery testing and scalar-SOH screening."*

---

## 2. Operational Falsifiable Sub-Hypotheses

To ensure scientific rigor, the central hypothesis is decoupled into seven distinct, mathematically falsifiable sub-hypotheses. Each hypothesis specifies an explicit **Null Hypothesis ($H_0$)**, **Alternative Hypothesis ($H_1$)**, quantitative metric, and rejection condition.

### Sub-Hypothesis H1: Diagnostic Dwell Time Reduction
- **$H_{0,1}$ (Null):** Mean diagnostic dwell time under SECONDShift is greater than or equal to fixed-duration testing:
  $$\mathbb{E}[T_{\text{SECONDShift}}] \ge \mathbb{E}[T_{\text{Fixed}}]$$
- **$H_{1,1}$ (Alternative):** SECONDShift achieves at least a 50% reduction in mean diagnostic dwell time relative to fixed testing:
  $$\mathbb{E}[T_{\text{SECONDShift}}] < 0.50 \cdot \mathbb{E}[T_{\text{Fixed}}]$$
- **Falsification Condition:** If mean time for healthy batteries $\ge 400\text{ s}$ (given an 800s fixed baseline), H1 is **FALSIFIED**.

---

### Sub-Hypothesis H2: Diagnostic Energy Consumption Reduction
- **$H_{0,2}$ (Null):** Total electrical energy consumed during qualification under SECONDShift is greater than or equal to fixed-duration testing:
  $$\mathbb{E}[E_{\text{SECONDShift}}] \ge \mathbb{E}[E_{\text{Fixed}}]$$
- **$H_{1,2}$ (Alternative):** SECONDShift reduces diagnostic energy consumption by at least 60%:
  $$\mathbb{E}[E_{\text{SECONDShift}}] < 0.40 \cdot \mathbb{E}[E_{\text{Fixed}}]$$
- **Falsification Condition:** If average energy consumed $\ge 8.96\text{ Wh}$ (given a $22.4\text{ Wh}$ fixed baseline), H2 is **FALSIFIED**.

---

### Sub-Hypothesis H3: Unsafe-Acceptance Risk Bounding
- **$H_{0,3}$ (Null):** The true False Acceptance Rate ($\text{FAR}$) for unsafe battery specimens under SECONDShift exceeds the 1.0% safety limit:
  $$P(\text{Accept} \mid \text{Unsafe}) > 0.01$$
- **$H_{1,3}$ (Alternative):** The one-sided 95% confidence upper bound on FAR satisfies:
  $$\text{FAR}_{95\%} \le 0.010 \quad (1.0\%)$$
- **Falsification Condition:** If any unsafe specimen is accepted into `OPERATE` or if the 95% upper confidence bound exceeds $1.0\%$ across the validation fleet, H3 is **FALSIFIED**.

---

### Sub-Hypothesis H4: Justified Epistemic Abstention
- **$H_{0,4}$ (Null):** Under unresolvable chemistry ambiguity or severe model misspecification, the system forces commitment to `OPERATE` or `DERATE` at the same rate as known specimens:
  $$P(\text{Abstain} \mid \text{Ambiguous}) \le 0.10$$
- **$H_{1,4}$ (Alternative):** When posterior chemistry ambiguity remains below $99.0\%$ confidence ($P(M \mid \mathbf{y}) < 0.990$), the system strictly abstains from operational commitment:
  $$P(\text{Operate} \mid \text{Ambiguous}) = 0.000, \quad P(\text{Abstain} \mid \text{Ambiguous}) \ge 0.500$$
- **Falsification Condition:** If any ambiguous or tagless NMC cell is assigned `OPERATE` under an LFP algorithm, H4 is **FALSIFIED**.

---

### Sub-Hypothesis H5: Selective Testing on Informative Specimens
- **$H_{0,5}$ (Null):** SECONDShift executes the same number of diagnostic tests regardless of prior certainty:
  $$\mathbb{E}[N_{\text{tests}} \mid \sigma_{\text{prior}} \le 0.03] = \mathbb{E}[N_{\text{tests}} \mid \sigma_{\text{prior}} \ge 0.15]$$
- **$H_{1,5}$ (Alternative):** Specimens with tight, informative priors converge in fewer diagnostic tests than specimens with diffuse, uncertain priors:
  $$\mathbb{E}[N_{\text{tests}} \mid \text{Certain}] < \mathbb{E}[N_{\text{tests}} \mid \text{Uncertain}]$$
- **Falsification Condition:** If healthy certain specimens require as many diagnostic tests as highly uncertain specimens, H5 is **FALSIFIED**.

---

### Sub-Hypothesis H6: Autonomous Physical Safety Interlock Independence
- **$H_{0,6}$ (Null):** During catastrophic software or microcontroller failure (CPU freeze, watchdog stall, power loss), the physical circuit fails to disconnect within safe thermal/electrical time limits ($t > 200\text{ ms}$):
  $$t_{\text{trip}} > 0.200\text{ s}$$
- **$H_{1,6}$ (Alternative):** The independent analog comparator and supervisory watchdog drop contactor current to $0.000\text{ A}$ within $<200\text{ ms}$ completely independent of software execution:
  $$t_{\text{trip}} \le 0.200\text{ s}$$
- **Falsification Condition:** If current continues flowing after microcontroller lockup or watchdog timeout beyond $200\text{ ms}$, H6 is **FALSIFIED**.

---

### Sub-Hypothesis H7: Robustness Under Adversarial Information Degradation
- **$H_{0,7}$ (Null):** When sensor noise, missing telemetry, or biased priors are injected, the decision engine becomes more aggressive (increases acceptance rate of borderline cells).
- **$H_{1,7}$ (Alternative):** The decision engine becomes strictly more conservative (increases abstention or testing rate) as observation noise or epistemic uncertainty increases:
  $$\frac{\partial P(\text{Conservative Action})}{\partial \sigma_{\text{noise}}} \ge 0$$
- **Falsification Condition:** If injecting sensor noise or missing packets increases the probability of assigning `OPERATE`, H7 is **FALSIFIED**.
