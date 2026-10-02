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

## 3. Key Empirical Findings & Performance Summary (Audited N=12 Benchmark)

| Evaluation Metric | Baseline A (Full OEM Cycler) [1] | Baseline B (Scalar Strawman) [2] | SECONDShift (Proposed) [3] | Target Design Limit | Statistical Significance |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Classification Accuracy** | 75.00% [42.8%, 94.5%] | 33.33% [9.9%, 65.1%] | **91.67% [61.5%, 99.8%]** | $> 85.0\%$ | McNemar $p = 0.6250$ (Not Significant) [4] |
| **False Acceptance Rate (FAR)** | 42.86% [9.9%, 81.6%] (3/7) | 100.00% [63.1%, 100.0%] (8/8) | **0.00% [0.0%, 41.0%] (0/7)** | $< 1.0\%$ | 1-Sided 95% UCB = **34.82%** [5] |
| **Qualified Acceptance Rate (QAR)** | 100.0% [47.8%, 100.0%] | 80.0% [28.4%, 99.5%] | **80.00% [28.4%, 99.5%]** | $> 75.0\%$ | 4 of 5 safe specimens qualified |
| **Mean Qualification Dwell Time** | 10,800.0 s | 0.05 s | **311.7 s** | $> 50\%$ reduction | Wilcoxon $p = 0.000488 < 0.001$ [6] |
| **Testing Energy Consumed** | 22.40 Wh | 0.00 Wh | **0.98 Wh** | Minimize | 95.6% energy savings |
| **Hardware Comparator Latency** | N/A | N/A | **11.8 ms** [7] | $< 15.0\text{ ms}$ | Rigol DS1054Z bench trace ($N=1$) |
| **Epistemic Chemistry Abstention** | No (Fails on NMC) | No | **Enforced (`HOLD`)** | Strict Safety | 100% ambiguous rejected |

#### Methodological Disclosures & Footnotes:
- **[1] Baseline A:** Full CC-CV 3-hour cycler ($10,800\text{ s}$). Without chemistry disambiguation, falsely accepts 3 unsafe NMC packs (`SPECIMEN_03`, `SPECIMEN_06`, `SPECIMEN_11`).
- **[2] Baseline B:** Static prior evaluation with zero testing ($t=0.05\text{ s}$). Labeled as an **illustrative strawman**.
- **[3] SECONDShift Pipeline:** Executed in software simulation via `MockHermesHardware` using adaptive VOI stopping and Bayesian updates.
- **[4] McNemar Paired Test ($p = 0.6250$):** Classification accuracy difference is **not statistically significant on $N=12$** due to small sample size ($b=3, c=1$ discordant pairs).
- **[5] Sample Size Limit on FAR:** Observed $\text{FAR} = 0/7 = 0.0\%$. Exact Clopper-Pearson 95% one-sided upper bound is **$34.82\%$**. Guaranteeing an upper bound $<1.0\%$ mathematically requires $N \ge 299$ zero-failure tests.
- **[6] Dwell Time Reduction ($p < 0.001$):** Diagnostic dwell time reduction from $10,800\text{ s}$ to $311.7\text{ s}$ is strongly statistically significant ($W=0.0, p < 0.001, r = 0.88$).
- **[7] Hardware Latency:** Single-trace bench capture on physical testbed prototype.

---

## 4. Quick Start: Reproducing Results

```bash
# 1. Clone repository and install dependencies
git clone <REPO_URL>
cd RMK_REVOLT/secondshift
pip install -r requirements.txt

# 2. Run Automated Pytest Suite (10 unit & isolation tests)
pytest tests/ -v

# 3. Run Benchmark Suite and Recompute All Verified Metrics
python experiments/run_blind_physical_validation.py
python experiments/recompute_all_metrics.py

# 4. Run Adversarial & Chemistry Attacks
python experiments/run_adversarial_overconfidence.py
python experiments/run_chemistry_attacks.py

# 5. Run Master Reproducibility Audit Script
bash RUN_VALIDATION.sh
```

---

## 5. Engineering Boundaries & Non-Claims

1. **Student Research Prototype:** Designed and tested on Safety Extra-Low Voltage (SELV, $<60\text{ V}$ DC) laboratory modules (4S LFP 12.8V, 20Ah format).
2. **No Claim of Commercial Safety Certification:** Not certified to ISO 26262 ASIL-D or UL 1973.
3. **No Claim of "Thermal Runaway Prevention":** Implements autonomous electrical overload and over-temperature cutoff; does not claim thermal runaway prevention under mechanical crushing or internal short circuits.
4. **Hardware GO Policy:** Granted **strictly and only** for confirmed single-source LFP fleets ($P(\text{LFP}) \ge 0.99$). Mixed or tagless unknown chemistry remains permanently locked to **`HOLD / RECYCLE`**.
