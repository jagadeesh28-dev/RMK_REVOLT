# SECONDShift Software Architecture Specification

## 1. Modular Hierarchy & Package Structure

The SECONDShift software stack resides entirely under `secondshift/software/` and strictly decouples state observation from ground-truth knowledge.

```
secondshift/software/
├── chemistry/
│   └── chemistry_engine.py         # Epistemic Chemistry & Model Disambiguation Engine
├── estimators/
│   ├── bayesian_state_estimator.py # Conjugate Normal-Gamma SOH & R0 Estimator
│   └── model_uncertainty.py       # Multi-Model Marginal Failure Risk Integrals
├── hermes/
│   ├── hermes_driver.py           # Hardware abstraction layer & Mock Simulator
│   └── measurement_primitives.py  # Monotonic sensor query routines
├── safety/
│   └── hard_safety_barrier.py     # Deterministic risk gating & action filtering
├── triage/
│   └── baseline_characterizer.py  # Mechanical/fast electrical admissibility checks
├── voi/
│   └── evsi_calculator.py         # Gauss-Hermite Quadrature EVSI calculation
└── secondshift/
    ├── baselines.py               # Comparative baseline decision strategies
    ├── closed_loop_runner.py      # Adaptive qualification orchestration
    ├── decision_engine.py         # Core SECONDShift decision maker
    └── metrics_calculator.py      # Safety, economic, and operational KPI calculation
```

---

## 2. Core Modules & Responsibilities

### 2.1 Layer 1: Triage Gate (`software/triage/baseline_characterizer.py`)
- **Class:** `TriageGate`
- **Method:** `evaluate_specimen(specimen_id, visual_inspection, terminal_voltage, rest_rate_mv_hr)`
- **Gates:**
  1. Mechanical integrity check (swelling, venting, casing breach).
  2. Voltage range check: $V_{\text{term}} \in [10.0\text{V}, 14.6\text{V}]$.
  3. Micro-short self-discharge rate: $|dV/dt_{\text{rest}}| \le 20.0\text{ mV/hr}$.
- **Result:** Emits `TriageResult(status=PASS/REJECT, reason=...)`.

### 2.2 Layer 2A: Chemistry Disambiguation Engine (`software/chemistry/chemistry_engine.py`)
- **Class:** `EpistemicChemistryEngine`
- **State Vector:**
  $$\mathbf{P}_{\mathcal{M}} = [P(\text{LFP} \mid \mathbf{y}), P(\text{NMC} \mid \mathbf{y}), P(\text{UNKNOWN} \mid \mathbf{y})]$$
- **Disambiguation Thresholds:**
  - `KNOWN`: $P(M \mid \mathbf{y}) \ge 0.99$
  - `PROBABLE`: $0.90 \le P(M \mid \mathbf{y}) < 0.99$
  - `AMBIGUOUS`: $P(M \mid \mathbf{y}) < 0.90$
- **Invariance Rule:** Direct `OPERATE` is strictly forbidden unless chemistry state is `KNOWN` ($P(M \mid \mathbf{y}) \ge 0.99$).

### 2.3 Layer 2B: Bayesian State Estimator (`software/estimators/bayesian_state_estimator.py`)
- **Class:** `BayesianStateEstimator`
- **Estimated State:** $\mathbf{x} = [\text{SOH}, R_0]^T$
- **Update Mechanism:** Conjugate Normal-Gamma precision updates:
  $$\tau_{\text{post}} = \tau_{\text{prior}} + \tau_{\text{meas}}, \quad \mu_{\text{post}} = \frac{\tau_{\text{prior}}\mu_{\text{prior}} + \tau_{\text{meas}} y}{\tau_{\text{post}}}$$
- **Shrinkage Tracking:** Monotonically records belief state evolution and variance reductions across diagnostic steps.

### 2.4 Layer 2C: Multi-Model Failure Risk Integration (`software/estimators/model_uncertainty.py`)
- **Class:** `ModelUncertaintyEstimator`
- **Law of Total Probability Formulation:**
  $$P(\text{Failure} \mid \mathbf{y}) = \sum_{M \in \mathcal{M}} P(\text{Failure} \mid \mathbf{y}, M) P(M \mid \mathbf{y})$$
- Where conditional risk under chemistry model $M$ integrates joint state probability:
  $$P(\text{Failure} \mid \mathbf{y}, M) = 1 - P\Big(\text{SOH} \ge \text{SOH}_{\text{crit}}^{(M)} \;\wedge\; R_0 \le R_{0,\text{crit}}^{(M)} \;\Big|\; \mathbf{y}, M\Big)$$

### 2.5 Layer 2D: Hard Safety Barrier (`software/safety/hard_safety_barrier.py`)
- **Class:** `HardSafetyBarrier`
- **Target Safety Limit:** $\alpha_{\text{max}} = 0.01$ (1.0% failure risk).
- **Mask Function:**
  $$Q_{\text{masked}}(a) = \begin{cases} Q(a) & \text{if } P(\text{Failure} \mid \mathbf{y}) \le \alpha_{\text{max}} \text{ and } \text{ChemistryState} = \text{KNOWN} \\ -10^8 & \text{otherwise} \end{cases}$$

### 2.6 Layer 2E: Expected Value of Sample Information (`software/voi/evsi_calculator.py`)
- **Class:** `EVSICalculator`
- **Method:** 5-point Gauss-Hermite Quadrature integration over the predictive distribution of prospective test outcomes:
  $$\text{EVSI}(t) = \int \max_{a \in \mathcal{A}} \mathbb{E}[U(a, \mathbf{x}) \mid \mathbf{y}, \tilde{y}] \, p(\tilde{y} \mid \mathbf{y}) \, d\tilde{y} - \max_{a \in \mathcal{A}} \mathbb{E}[U(a, \mathbf{x}) \mid \mathbf{y}]$$
- Evaluates test benefit against diagnostic cost: $\text{NetBenefit}(t) = \text{EVSI}(t) - C(t)$.

### 2.7 Layer 2F: SECONDShift Decision Engine (`software/secondshift/decision_engine.py`)
- **Class:** `SecondShiftDecisionEngine`
- **Actions:** $\mathcal{A} = \{\text{TEST}, \text{OPERATE}, \text{DERATE}, \text{HOLD}, \text{RETIRE}\}$.
- Coordinates Triage, Chemistry Disambiguation, Safety Barrier, and VOI optimization to select the next action.

---

## 3. Ground-Truth Quarantine & Hardware Abstraction

To guarantee zero information leakage:
1. `data/raw/ground_truth_registry.json` is accessed **only** by [`MockHermesHardware`](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/software/hermes/hermes_driver.py).
2. The decision engine, triage gate, and estimators interact strictly via abstract telemetry queries (`measure_rest_voltage`, `perform_current_pulse`, etc.).
3. Measurement noise $\mathcal{N}(0, \sigma^2)$ is added to physical emulations, matching hardware sensors.
