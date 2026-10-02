# NEXT EXPERIMENT MATRIX & TRANSLATIONAL ROADMAP

**Project:** SECONDShift — Risk-Constrained Adaptive Qualification Under State and Model Uncertainty  
**Audit Date:** 2026-10-02  
**Status:** COMPLETE & ROADMAPPED  
**Repository Document:** `secondshift/docs/NEXT_EXPERIMENTS.md`  

---

## 1. Executive Summary

This document formalizes the **Top 3 High-Priority Future Experiments** required to advance SECONDShift across three distinct evaluation domains:
1. **Academic Publication Track:** Satisfying peer-reviewer statistical power and sample size mandates.
2. **Hardware Credibility Track:** Satisfying systems and electrical engineering reliability mandates.
3. **Commercial Deployment Track:** Satisfying second-life BESS investor and customer due-diligence mandates.

---

## 2. Priority Experiment 1: Academic Publication Track (Reviewer Mandate)

### Title: Large-Sample Statistical Validation Fleet ($N \ge 300$)
- **Primary Research Question:** Does SECONDShift empirically sustain a Clopper-Pearson 95% one-sided upper confidence bound on False Acceptance Rate ($\text{FAR}$) strictly below $1.0\%$ across a diverse, physically retired second-life cell population?
- **Required Equipment & Infrastructure:**
  - Automated 16-channel battery test fixture (Arbin or Chroma cycler front-end).
  - Climate test chamber (ESPEC, $-10^\circ\text{C}$ to $+60^\circ\text{C}$).
  - High-precision reference coulometer.
  - Estimated Budget: **₹8,50,000 INR** ($~\$10,200\text{ USD}$) or institutional laboratory access.
- **Specimen Requirements:**
  - $N = 300$ physically retired automotive and industrial cells.
  - Composition: 180 LFP (e.g., Gotion/CALB 20Ah–50Ah), 90 NMC (e.g., LG/Samsung 18650/21700), 30 uncharacterized / mixed modules.
  - Must include at least 100 ground-truth unsafe specimens ($SOH < 70\%$ or $R_0 > 3.5\text{ m}\Omega$).
- **Expected Outcome:** Zero false acceptances across all 100 unsafe specimens ($0/100$), yielding $\text{FAR}_{95\%, \text{UCB}} = 2.95\%$ on $N=100$, or $0/299$ failure-free tests to achieve $\text{FAR}_{95\%, \text{UCB}} \le 1.00\%$.
- **Failure Criteria:** If $\ge 2$ unsafe cells are falsely qualified into `OPERATE`, or if $\text{FAR}_{\text{obs}} > 1.0\%$, the hypothesis is falsified.
- **Go / No-Go Gate for Journal Submission:** Unconditional GO if $\text{FAR}_{\text{obs}} \le 0.5\%$ and mean dwell time reduction $>80\%$.

---

## 3. Priority Experiment 2: Hardware Credibility Track (Engineer Mandate)

### Title: High-Current Relay Welding & Solid-State Disconnect Durability
- **Primary Research Question:** Can the independent analog safety barrier maintain disconnect reliability under severe contactor stress, high inrush current, and repetitive fault trips without contact welding or TVS diode breakdown?
- **Required Equipment & Infrastructure:**
  - Programmable electronic load with fast slew rate ($>10\text{ A}/\mu\text{s}$).
  - 4-channel mixed-signal oscilloscope (100 MHz, high-voltage differential probes).
  - High-speed thermal infrared camera (FLIR).
  - Estimated Budget: **₹1,20,000 INR** ($~\$1,450\text{ USD}$).
- **Specimen Requirements:**
  - 10 sacrificial commercial 12V 50Ah LFP packs.
  - 5 mechanical automotive relays (JD1912) vs 5 solid-state Silicon Carbide (SiC) bidirectional disconnect boards.
- **Expected Outcome:**
  - Benchmark mechanical relay degradation: identify contact erosion resistance increase after 500 fault trips.
  - Verify SiC solid-state switch trip latency is $<5.0\ \mu\text{s}$ (3 orders of magnitude faster than mechanical relay $11.8\text{ ms}$).
- **Failure Criteria:** Any single occurrence of contact welding where current continues flowing $>50\text{ ms}$ after comparator trip constitutes a catastrophic system failure.
- **Go / No-Go Gate for Hardware Scale-Up:** Complete transition from mechanical relays to solid-state SiC disconnect before deploying above 24V DC.

---

## 4. Priority Experiment 3: Commercial Deployment Track (Investor / Customer Mandate)

### Title: 1,000-Cycle Stationary Storage Durability of SECONDShift-Qualified Modules
- **Primary Research Question:** Do second-life modules qualified as `OPERATE` under SECONDShift's rapid screening exhibit stable, predictable cycling life in a real-world stationary BESS without premature capacity knee-point collapse or thermal divergence?
- **Required Equipment & Infrastructure:**
  - 5 kW / 10 kWh commercial BESS prototype rack with solar inverter integration.
  - Multi-channel BMS with continuous CAN bus data logging.
  - Fire-isolated outdoor testing container.
  - Estimated Budget: **₹4,50,000 INR** ($~\$5,400\text{ USD}$).
- **Specimen Requirements:**
  - 16 SECONDShift-qualified 48V/50Ah LFP modules (assembled from qualified cells).
  - 4 control modules qualified via standard exhaustive cycler (Baseline A).
- **Expected Outcome:**
  - Complete 1,000 continuous C/2 charge-discharge cycles (equivalent to 3 years of daily solar peak shaving).
  - Retain $>80\%$ of second-life intake capacity ($>60\%$ of original nameplate capacity) with zero thermal runaway events.
- **Failure Criteria:** Any module experiencing thermal runaway, internal micro-shorting, or capacity loss $>5\%$ per 100 cycles fails qualification.
- **Go / No-Go Gate for Commercial Launch:** Commercial pilot deployment authorization granted if capacity loss remains $<0.03\%$ per cycle across 500 initial test cycles.
