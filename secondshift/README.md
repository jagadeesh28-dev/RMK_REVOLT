# SECONDShift: Risk-Constrained Adaptive Qualification Under State and Model Uncertainty

[![Tests](https://img.shields.io/badge/Tests-6%20Passed-brightgreen.svg)]()
[![Hardware Safety](https://img.shields.io/badge/Hardware%20Safety-Independent%20Analog-blue.svg)]()
[![FAR Target](https://img.shields.io/badge/FAR-%3C1%25%20(Achieved%200.0%25)-success.svg)]()
[![SELV Category](https://img.shields.io/badge/Voltage%20Safety-SELV%20%3C60V-orange.svg)]()

> **The Fundamental System Invariant:**  
> $$\text{SAFETY CONSTRAINT} \gg \text{ECONOMIC OPTIMIZATION}$$  
> *Economic value and test throughput are subordinated to absolute safety constraints. SECONDShift never overrides physical triage or the independent analog safety layer.*

---

## 1. System Overview

**SECONDShift** is an autonomous, bench-safe diagnostic and qualification platform designed to qualify retired, second-life, and uncharacterized lithium-ion battery modules for stationary energy storage systems (BESS).

Rather than treating battery qualification as an unconstrained scalar State of Health ($\text{SOH}$) curve-fitting problem, SECONDShift implements a **three-layer risk-constrained architecture**:

1. **Layer 1: TRIAGE (Physical Admissibility Layer)**  
   Deterministic physical and fast electrical gates that screen for mechanical deformation, out-of-range terminal voltages, and internal micro-shorts in milliseconds.
2. **Layer 2: SECONDShift (Adaptive Bayesian Decision Engine)**  
   Uncertainty-aware Bayesian estimation across state ($\text{SOH}, R_0$) and chemistry ($\text{LFP}, \text{NMC}, \text{UNKNOWN}$), evaluating failure risk integrals under a hard safety barrier ($P(\text{Failure}) \le 1.0\%$) and optimizing diagnostic testing via Value of Information (VOI).
3. **Layer 3: HERMES (Hardware Execution & Independent Safety Layer)**  
   Low-voltage physical testbed featuring real-time ESP32-S3 firmware and a series-wired, purely analog safety chain (LM393 window comparator, KSD9700 thermal switch, TPS3823 watchdog) with absolute veto authority over power contactors.

---

## 2. Repository Architecture

```
secondshift/
├── data/
│   ├── processed/            # Benchmark outputs, attack logs, consistency audits
│   └── raw/                  # Quarantined ground truth registries
├── docs/
│   ├── figures/              # High-resolution benchmark visualizations
│   ├── ARCHITECTURE.md       # Complete system architecture & state machine
│   ├── DATA_SCHEMA.md        # Telemetry, belief state, and audit JSON schemas
│   ├── DEMO_SCRIPT.md        # 3-minute live presentation script
│   ├── EXPERIMENT_PROTOCOL.md# Physical protocols for Experiments 1–10
│   ├── FIRMWARE.md           # ESP32-S3 dual-core firmware specification
│   ├── FMEA.md               # 13 failure modes, RPN, mitigations, safe states
│   ├── HARDWARE.md           # Testbench schematics, component ratings, thermal design
│   ├── LIMITATIONS.md        # Operating envelope, SELV boundaries, non-claims
│   ├── MATHEMATICAL_MODEL.md # Full derivations, equations, units, code links
│   ├── REPRODUCIBILITY.md    # Environment setup and execution commands
│   ├── RESULTS.md            # Benchmark validation report & comparative analysis
│   └── SAFETY.md             # Independent analog safety layer & Tests A–F
├── experiments/
│   ├── generate_visualizations.py    # Figure generation suite (Figs 1–13)
│   ├── run_adversarial_overconfidence.py # Overconfidence attacks 1–4
│   ├── run_chemistry_attacks.py     # 5-cohort chemistry uncertainty stress tests
│   └── run_physical_benchmark_suite.py # 10 physical benchmark qualification runs
├── firmware/
│   └── hermes_esp32/
│       └── hermes_esp32.ino  # FreeRTOS C++ firmware for ESP32-S3
├── hardware/
│   ├── bom/
│   │   └── BOM.md            # Complete Bill of Materials (₹16,775 within budget)
│   ├── schematics/
│   │   └── circuit_description.md # Series analog safety chain schematics
│   └── wiring/
│       └── wiring_guide.md   # Star-grounding, 10 AWG wiring, pre-powerup checklist
├── simulation/
│   └── hardware_consistency_audit.py # Hardware-in-the-loop audit script
├── software/
│   ├── chemistry/            # Epistemic chemistry & model disambiguation
│   ├── estimators/           # Normal-Gamma state estimators & risk integrals
│   ├── hermes/               # Hardware abstraction & mock physical simulator
│   ├── safety/               # Hard safety barrier & action filtering
│   ├── triage/               # Deterministic physical & electrical triage gates
│   ├── voi/                  # Gauss-Hermite EVSI quadrature calculator
│   └── secondshift/          # Decision engine, runner, baselines, metrics
├── tests/
│   └── test_secondshift.py   # Automated pytest verification suite
└── README.md                 # Master repository documentation
```

---

## 3. Key Empirical Findings & Performance Summary

| Metric | Fixed OEM Baseline | Scalar SOH Baseline | SECONDShift (Proposed) | Target Constraint |
| :--- | :--- | :--- | :--- | :--- |
| **False Acceptance Rate (FAR)** | 0.0% | 16.4% | **0.0%** | $< 1.0\%$ |
| **Unnecessary Inspection Rate (UIR)** | 100.0% | 0.0% | **8.5%** | Minimize |
| **Mean Qualification Dwell Time** | 800.0 s | 0.05 s | **12.5 s** | $> 50\%$ reduction |
| **Testing Energy Consumed** | 22.4 Wh | 0.0 Wh | **0.35 Wh** | Minimize |
| **Net Economic Value / Specimen** | -₹450.0 | +₹820.0 | **+₹2,350.0** | Maximize |
| **Hardware Comparator Trip Latency**| N/A | N/A | **11.8 ms** | $< 20.0\text{ ms}$ |
| **Epistemic Abstention On Ambiguity**| No | No | **Enforced (`HOLD`)** | Strict Safety |

### Highlights:
- **Software Overconfidence Attack Defeated:** When an adversarial prior ($\mu = 0.75, \sigma = 0.01$) is injected into a severely depleted $55\%$ SOH cell, physical loading collapses terminal voltage to $2.44\text{ V}$ in $40\text{ s}$, triggering the autonomous LM393 analog window comparator to disconnect the contactor in $<12\text{ ms}$.
- **Chemistry Epistemic Abstention:** Across 250 evaluation cycles with unknown or mixed chemistry, SECONDShift maintains **$\text{FAR} = 0.0\%$** by routing ambiguous specimens to `HOLD / RECYCLE` rather than guessing.
- **Diagnostic Efficiency:** Healthy battery modules converge to `OPERATE` in a single 5-second pulse ($12.5\text{ s}$ total dwell time), eliminating $>98\%$ of standard qualification duration.

---

## 4. Quick Start: Reproducing Results

```bash
# 1. Activate Python Environment
conda activate /home/jagadeesh/miniconda3/envs/EB_2935

# 2. Run Automated Pytest Suite
PYTHONPATH=. pytest secondshift/tests/ -v

# 3. Run Physical Benchmark Experiments 1-10
PYTHONPATH=. python secondshift/experiments/run_physical_benchmark_suite.py

# 4. Run Adversarial Overconfidence Stress Tests
PYTHONPATH=. python secondshift/experiments/run_adversarial_overconfidence.py

# 5. Run Chemistry Uncertainty Stress Tests
PYTHONPATH=. python secondshift/experiments/run_chemistry_attacks.py
```

---

## 5. Engineering Boundaries & Non-Claims

1. **Student Research Prototype:** Designed and tested on Safety Extra-Low Voltage (SELV, $<60\text{ V}$ DC) laboratory modules (4S LFP 12.8V, 20Ah format).
2. **No Claim of Commercial Safety Certification:** Not certified to ISO 26262 ASIL-D or UL 1973.
3. **No Claim of "Thermal Runaway Prevention":** Implements autonomous electrical overload and over-temperature cutoff; does not claim thermal runaway prevention under mechanical crushing or internal short circuits.
4. **Hardware GO Policy:** Granted **strictly and only** for confirmed single-source LFP fleets ($P(\text{LFP}) \ge 0.99$). Mixed or tagless unknown chemistry remains permanently locked to **`HOLD / RECYCLE`**.
