# SECONDShift Physical Experiment Protocol

This document defines the execution protocol for the ten benchmark qualification experiments implemented in [`run_physical_benchmark_suite.py`](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/experiments/run_physical_benchmark_suite.py).

---

## Benchmark Experiment 1: Intake Triage Admissibility Gate
- **Objective:** Verify deterministic mechanical, electrical, and self-discharge triage admissibility.
- **Apparatus:** 4S Battery Module / Battery Emulator, DMM, Calipers.
- **Protocol:**
  1. Inspect physical casing for bulging ($\Delta d > 1.5\text{ mm}$), electrolyte odor, or terminal oxidation.
  2. Measure open-circuit terminal voltage $V_{\text{term}}$.
  3. If $V_{\text{term}} < 10.0\text{ V}$ or $V_{\text{term}} > 14.6\text{ V}$, record `TRIAGE_REJECT`.
  4. Monitor $V_{\text{term}}$ over $60\text{ s}$ baseline to compute $|dV/dt_{\text{rest}}|$.
  5. If $|dV/dt_{\text{rest}}| > 20.0\text{ mV/hr}$, record `TRIAGE_REJECT_MICROSHORT`.
- **Pass Criteria:** Mechanically sound cells with $V \in [10.0\text{V}, 14.6\text{V}]$ pass to Layer 2; all defective cells are rejected in $<100\text{ ms}$.

---

## Benchmark Experiment 2: Baseline Ohmic Resistance Pulse
- **Objective:** Quantify initial high-frequency ohmic resistance $R_0$.
- **Apparatus:** HERMES Testbed, IRLB8721 Electronic Load, INA226 Current Monitor.
- **Protocol:**
  1. Establish stable resting voltage $V_0$ ($I = 0\text{ A}$ for $10\text{ s}$).
  2. Apply a regulated $5.0\text{ A}$ discharge current pulse for $5.0\text{ s}$.
  3. Capture $V(t)$ at $100\text{ Hz}$ across the transition.
  4. Calculate Ohmic resistance:
     $$R_0 = \frac{V_0 - V(t = 50\text{ ms})}{I_{\text{pulse}}}$$
- **Pass Criteria:** Measurement error $\le \pm 0.1\text{ m}\Omega$; thermal rise during pulse $\Delta T < 0.5^\circ\text{C}$.

---

## Benchmark Experiment 3: Extended Relaxation & Micro-Short Detection
- **Objective:** Detect latent separator micro-shorts via electrochemical potential relaxation.
- **Protocol:**
  1. Apply a conditioning current pulse ($5.0\text{ A}$, $10\text{ s}$).
  2. Terminate current and record cell voltage relaxation at $10\text{ Hz}$ for $300\text{ s}$.
  3. Fit dual-exponential polarization model:
     $$V_{\text{relax}}(t) = V_{\text{ocv}} - \Delta V_1 e^{-t/\tau_1} - \Delta V_2 e^{-t/\tau_2} - k_{\text{leak}} t$$
  4. Extract linear drift parameter $k_{\text{leak}}$.
- **Pass Criteria:** Normal cells exhibit $k_{\text{leak}} < 5.0\text{ mV/hr}$; micro-shorted cells exceed $20.0\text{ mV/hr}$ and are flagged.

---

## Benchmark Experiment 4: Chemistry Disambiguation Diagnostic Sequence
- **Objective:** Disambiguate cell chemistry across $\mathcal{M} \in \{\text{LFP}, \text{NMC}, \text{UNKNOWN}\}$.
- **Protocol:**
  1. Record resting open-circuit voltage $V_{\text{rest}}$ (LFP plateaus at $\sim 13.2\text{V}-13.3\text{V}$; NMC slopes at $14.0\text{V}-16.0\text{V}$).
  2. Execute sequential diagnostic tests: $5\text{A}$ pulse, $10\text{A}$ pulse, and thermal slope evaluation.
  3. Update categorical belief $\mathbf{P}_{\mathcal{M}}$ via Bayes' rule.
  4. Check stopping condition: $P(M) \ge 0.99 \implies$ `KNOWN`; if ambiguous after budget, declare `HOLD/RECYCLE`.
- **Pass Criteria:** Ground-truth LFP identified with $P(\text{LFP}) \ge 0.99$; unknown cells never classified with false certainty.

---

## Benchmark Experiment 5: SOH Bayesian Estimation
- **Objective:** Demonstrate variance shrinkage in SOH and $R_0$ beliefs across adaptive test cycles.
- **Protocol:**
  1. Initialize diffuse prior: $\mu_{\text{SOH}} = 0.75, \sigma_{\text{SOH}} = 0.15$.
  2. Execute successive diagnostic pulse and capacity tests selected by VOI.
  3. Update Gaussian precision after each test.
- **Pass Criteria:** Posterior standard deviation shrinks monotonically ($\sigma_{\text{SOH}, k+1} < \sigma_{\text{SOH}, k}$); final $\sigma_{\text{SOH}} \le 0.03$.

---

## Benchmark Experiment 6: Safety Barrier Enforcement Under Injected Overconfidence
- **Objective:** Verify safety barrier rejection of adversarial estimator attacks.
- **Protocol:**
  1. Inject an adversarial belief state: True $\text{SOH} = 55\%$, Injected $\mu_{\text{SOH}} = 75\%, \sigma_{\text{SOH}} = 0.01$.
  2. Submit belief state to SECONDShift Decision Engine.
  3. Confirm whether software safety barrier or physical hardware trips prevents unsafe operation.
- **Pass Criteria:** System rejects direct operation or hardware analog comparator autonomously trips when cell terminal drops below $10.0\text{ V}$.

---

## Benchmark Experiment 7: Value of Information (VOI) Decision Convergence
- **Objective:** Validate that diagnostic testing ceases when test cost exceeds expected risk reduction.
- **Protocol:**
  1. Compute EVSI for available test catalog: `REST_QUERY`, `PULSE_5A`, `PULSE_10A`, `CYCLE_TEST`.
  2. Select $\arg\max_t (\text{EVSI}(t) - C(t))$.
  3. Track stopping decision: Once $\text{EVSI}(t) \le C(t)$, transition directly to final state (`OPERATE`, `DERATE`, or `RETIRE`).
- **Pass Criteria:** System stops qualification in $\le 3$ test steps without redundant cycling.

---

## Benchmark Experiment 8: Derated Operation Boundary
- **Objective:** Verify safe assignment of marginal cells to DERATED operation ($0.5\text{C}$ current limit).
- **Protocol:**
  1. Test degraded cell: True $\text{SOH} = 74\%$, True $R_0 = 3.2\text{ m}\Omega$.
  2. Evaluate decision engine utility: Full operate rejected due to risk; derated operate accepted ($P(\text{Failure}) \le 1.0\%$).
- **Pass Criteria:** Action `DERATE` is selected with operating envelope derated by $50\%$.

---

## Benchmark Experiment 9: Baseline Comparison Run
- **Objective:** Benchmark SECONDShift against Fixed OEM Sequence, Scalar SOH, and Uncertainty Thresholding.
- **Protocol:**
  1. Evaluate identical 10-specimen test cohort across all four decision frameworks.
  2. Record False Acceptance Rate (FAR), Unnecessary Inspection Rate (UIR), diagnostic time, and net economic value.
- **Pass Criteria:** SECONDShift achieves $\text{FAR} < 1.0\%$ while retaining positive economic utility.

---

## Benchmark Experiment 10: Independent Hardware Safety Trip
- **Objective:** Verify autonomous analog contactor trip under extreme physical excursions.
- **Protocol:**
  1. Simulate or inject over-voltage ($15.0\text{V}$) and under-voltage ($9.5\text{V}$) conditions.
  2. Monitor LM393 output pin and contactor coil voltage.
  3. Verify contactor drops within $<20\text{ ms}$ completely independent of ESP32 commands.
- **Pass Criteria:** Contactor physical disconnection verified in $<20\text{ ms}$.
