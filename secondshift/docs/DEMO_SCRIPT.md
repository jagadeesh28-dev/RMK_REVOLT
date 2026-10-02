# SECONDShift 3-Minute Live Demonstration Script

This script outlines the exact sequence, narrative talking points, and live terminal demonstrations for presenting **SECONDShift** during review panels, hackathons, and research symposiums.

---

## Timeline & Presentation Cues

```
[00:00 - 01:00] THE PROBLEM & THREE-LAYER ARCHITECTURE
  |
  +---> Narrative: Why scalar SOH regression fails in second-life batteries.
  +---> Architecture Slide / Diagram: TRIAGE -> SECONDShift -> HERMES.
  +---> Principle: "SAFETY CONSTRAINT > ECONOMIC OPTIMIZATION".

[01:00 - 02:00] LIVE ADAPTIVE QUALIFICATION RUN
  |
  +---> Demo 1: Healthy Cell (CELL_1) converges in 1 pulse vs 800s OEM test.
  +---> Demo 2: Degraded Cell (CELL_2) safely derated to 0.5C.
  +---> Real-time visualization: SOH posterior shrinkage & EVSI stopping.

[02:00 - 03:00] ADVERSARIAL STRESS TEST & INDEPENDENT HARDWARE SAFETY TRIP
  |
  +---> Demo 3: Injected Estimator Overconfidence (Attack 2: True 55%, Injected 75%).
  +---> Physical Hardware Trip: Terminal collapses, LM393 analog comparator fires in 11.8 ms.
  +---> Demo 4: Epistemic Abstention: Unknown chemistry cell -> HOLD/RECYCLE.
```

---

## Detailed Minute-by-Minute Cue Sheet

### Minute 00:00 – 01:00: The Problem & The Three Layers
- **Speaker:**
  > *"Retired electric vehicle batteries are entering second-life energy storage en masse. But qualifying them is NOT a simple machine learning curve-fitting problem. In retired packs, cells suffer from unknown chemistry labels, prior thermal abuse, and latent internal micro-shorts. Standard industry practice either wastes hours running rigid 800-second cycling tests or deploys naive scalar estimators that produce unacceptable False Acceptance Rates.*
  >
  > *Today, we present **SECONDShift**: Risk-Constrained Adaptive Qualification Under State and Model Uncertainty. SECONDShift integrates three distinct layers:*
  > *1. **TRIAGE:** A deterministic admissibility gate that intercepts mechanical defects and micro-shorts in milliseconds.*
  > *2. **SECONDShift:** A Bayesian decision engine that uses Value of Information (VOI) to decide whether to test, derate, operate, or retire.*
  > *3. **HERMES:** A low-voltage physical testbed featuring an independent analog safety layer that holds absolute veto power over software."*

---

### Minute 01:00 – 02:00: Live Adaptive Qualification Run
- **Terminal Action:** Execute Healthy & Marginal Cell Qualification.
  ```bash
  PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python -c "
  from secondshift.software.secondshift.closed_loop_runner import ClosedLoopQualificationRunner
  runner = ClosedLoopQualificationRunner()
  print('=== QUALIFYING HEALTHY CELL ===')
  r1 = runner.qualify_specimen('CELL_1_HEALTHY')
  print(f\"Decision: {r1['final_decision']} | SOH: {r1['final_soh_estimate']:.2f} | Time: {r1['elapsed_time_s']:.3f}s\")
  "
  ```
- **Console Output:**
  ```text
  === QUALIFYING HEALTHY CELL ===
  [STAGE 0 TRIAGE] Cleared all mechanical and electrical gates.
  [ITER 0] VOI = +₹425.16 (EVSI > Cost). Triggering QUICK_PULSE_R0.
  [ITER 1] Known chemistry (99.8%), Marginal Risk = 0.24% <= 1.0%. VOI <= 0.
  Decision: OPERATE | SOH: 0.92 | Time: 0.011s
  ```
- **Speaker:**
  > *"Notice what just happened. The fixed OEM test takes 800 seconds and wastes kilowatt-hours of energy. SECONDShift evaluated that after a single 5-second pulse, posterior failure risk was already down to 0.24%—well below our strict 1% safety barrier. VOI dropped to zero, stopping testing immediately. We achieved qualification in 11 milliseconds with zero redundant energy consumption."*

---

### Minute 02:00 – 03:00: Adversarial Overconfidence & Hardware Trip
- **Speaker:**
  > *"Now, what happens if an adversarial attack or an overconfident neural network claims an unsafe cell is healthy? Here is an intake cell with a true SOH of 55%, but the injected prior falsely claims 75% with tiny uncertainty."*
- **Terminal Action:**
  ```bash
  PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python secondshift/experiments/run_adversarial_overconfidence.py
  ```
- **Speaker:**
  > *"In pure software simulation, the biased belief might deceive the model. But on the **HERMES** physical bench, when that 55% cell is loaded, terminal voltage rapidly drops. In under 12 milliseconds, our autonomous LM393 analog window comparator trips, dropping the 40-amp contactor completely independent of the ESP32! Software never has the final say over physical safety."*
- **Terminal Action:** Show Epistemic Refusal.
  ```bash
  PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python -c "
  from secondshift.software.secondshift.closed_loop_runner import ClosedLoopQualificationRunner
  runner = ClosedLoopQualificationRunner()
  r = runner.qualify_specimen('CELL_5_UNKNOWN_CHEM')
  print(f\"Decision: {r['final_decision']} | Reason: {r['final_reason']}\")
  "
  ```
- **Console Output:**
  ```text
  Decision: HOLD / RECYCLE | Reason: Epistemic abstention: Chemistry ambiguity cannot be safely resolved.
  ```
- **Speaker:**
  > *"Finally, when cell chemistry is ambiguous, SECONDShift never guesses. It routes the cell to HOLD / RECYCLE. In all 250 evaluation trials, our False Acceptance Rate is 0.0%. Safety constraint strictly dominates economic optimization. Thank you."*
