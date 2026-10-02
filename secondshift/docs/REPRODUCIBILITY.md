# SECONDShift Reproducibility Guide & Verification Workflow

This document provides step-by-step instructions to reproduce all empirical benchmark results, adversarial attack suites, and visualization artifacts on any compatible Linux workstation.

---

## 1. Environment Setup

### Prerequisites
- Operating System: Linux (Ubuntu 20.04/22.04 LTS or Debian recommended)
- Python: Version $\ge 3.10$
- Package Manager: Conda or standard `venv`

### Conda Environment Activation
```bash
conda activate /home/jagadeesh/miniconda3/envs/EB_2935
```

### Required Dependencies
```bash
pip install numpy scipy pandas matplotlib pytest
```

---

## 2. Verification Suite Execution

From the repository root (`/home/jagadeesh/Documents/RMK_REVOLT`), execute the following commands in sequence:

### Step 1: Run Pytest Test Suite
Verifies unit logic for triage gates, chemistry disambiguation, Bayesian variance shrinkage, hard safety barrier masking, independent hardware comparator trips, and ERDS calculation:
```bash
PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python -m pytest secondshift/tests/ -v
```
*Expected Outcome:* `6 passed in <0.5s` (Exit Code 0).

---

### Step 2: Run Physical Benchmark Suite (Experiments 1–10)
Executes all ten physical benchmark qualification runs, tracking adaptive test convergence, derated boundaries, and baseline comparisons:
```bash
PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python secondshift/experiments/run_physical_benchmark_suite.py
```
*Expected Outcome:* All 10 experiments report `PASS`. Emits `secondshift/data/processed/physical_benchmark_results.json`.

---

### Step 3: Run Adversarial Estimator Overconfidence Attacks
Executes Attacks 1–4, testing system robustness against severely biased prior beliefs and internal resistance deceptions:
```bash
PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python secondshift/experiments/run_adversarial_overconfidence.py
```
*Expected Outcome:* Emits `secondshift/data/processed/overconfidence_attack_results.json`.

---

### Step 4: Run Chemistry Uncertainty & Epistemic Refusal Stress Tests
Simulates 250 qualification cycles across 5 cohorts (Known LFP, Known NMC, Unknown Chemistry, Wrong Label, Mixed 50/50):
```bash
PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python secondshift/experiments/run_chemistry_attacks.py
```
*Expected Outcome:* Emits `secondshift/data/processed/chemistry_attack_results.json`. Verifies FAR = 0.0% across all cohorts.

---

### Step 5: Run Hardware vs Simulation Consistency Audit
Quantifies model discrepancies across OCV plateaus, dynamic resistance non-linearities, thermal convection rates, and trip latencies:
```bash
PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python secondshift/simulation/hardware_consistency_audit.py
```
*Expected Outcome:* Emits `secondshift/data/processed/simulation_consistency_audit.json`.

---

### Step 6: Generate Full Visual Figure Suite
Renders the complete set of high-resolution publication figures into `secondshift/docs/figures/`:
```bash
PYTHONPATH=. /home/jagadeesh/miniconda3/envs/EB_2935/bin/python secondshift/experiments/generate_visualizations.py
```
*Expected Outcome:* Produces Figures 1 through 13 in PNG format.
