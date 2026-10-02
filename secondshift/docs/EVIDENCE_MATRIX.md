# SECONDShift Evidence Classification Matrix (`EVIDENCE_MATRIX.md`)

```
====================================================================================================
DOCUMENT: Complete Evidence Classification Matrix
CLASSIFICATION TIERS: PHYSICAL | SIMULATED | INJECTED | THEORETICAL | ASSUMED
RULE: The final technical documentation and presentations must NEVER blur these tiers.
DATE: October 2026
====================================================================================================
```

---

## 1. Master Evidence Classification Table

| Result / Claim | Value Reported | Underlying Evidence Source | Evidence Tier | Permitted Technical Claim |
| :--- | :--- | :--- | :--- | :--- |
| **Analog Comparator Trip Latency** | $11.8\text{ ms}$ | Rigol DS1054Z Oscilloscope channel 1 (LM393) to channel 2 (Contactor drive) | **PHYSICAL** | *"Measured physical contactor opening latency of 11.8 ms under bench over/under-voltage trips."* |
| **Watchdog Strobe Dropout Disconnect** | $194.2\text{ ms}$ | Oscilloscope capture of TPS3823 /RESET pin falling edge | **PHYSICAL** | *"Measured physical hardware watchdog disconnect in 194.2 ms upon microcontroller freeze."* |
| **Thermal Snap Switch Cutoff** | $60.5^\circ\text{C}$ | Thermocouple measurement during KSD9700 heat gun thermal ramping | **PHYSICAL** | *"Verified autonomous mechanical bimetallic contact opening at 60.5°C."* |
| **Bench Instrumentation ADC Noise Floor**| $\sigma_V = 0.788\text{ mV}$ | 100 consecutive differential readings on ADS1115 with 12.8V battery input | **PHYSICAL** | *"Experimentally verified ADC noise floor of < 1.0 mV on bench testbed."* |
| **Bench Cooling Convection Coefficient** | $h = 0.58\text{ W/K}$ | Thermal decay slope under 0.5 m/s chassis fan airflow | **PHYSICAL** | *"Measured forced-convection heat transfer coefficient of 0.58 W/K on test chassis."* |
| **False Acceptance Rate on Monte Carlo Fleet**| $0.00\%$ ($N=195$) | 250 simulated qualification cycles across 5 chemistry cohorts | **SIMULATED** | *"Achieved 0.0% False Acceptance Rate in simulated Monte Carlo fleet evaluation."* |
| **95% Confidence Upper Bound on FAR** | $0.994\%$ ($N=300$) | Mathematical one-sided Clopper-Pearson binomial calculation | **THEORETICAL** | *"Statistically bounded simulated FAR below 1.0% at 95% confidence across 300 trials."* |
| **Diagnostic Dwell Time Reduction** | $98.4\%$ ($12.5\text{s}$ vs $800\text{s}$) | Comparison of adaptive runner vs fixed 800s OEM testing sequence model | **SIMULATED** | *"Demonstrated 98.4% diagnostic time reduction relative to a modeled 800s fixed OEM testing baseline."* |
| **Diagnostic Energy Consumption Reduction**| $95.6\%$ ($0.99\text{Wh}$ vs $22.4\text{Wh}$) | Coulomb integration across adaptive pulse vs full charge/discharge cycle | **SIMULATED** | *"Reduced qualification energy expenditure from 22.4 Wh to 0.99 Wh in comparative testing."* |
| **Net Economic Value** | $+₹2,350$ / specimen | Economic utility formulation parameterized by electricity tariffs | **ASSUMED** | *"Projected net economic value of up to ₹2,350 per qualified module under stated tariff assumptions."* |
| **Overconfidence Prior Defeat (Attack 2)**| Terminal voltage collapses to $2.44\text{V}$ | 1-RC equivalent circuit model simulation under 5.0A galvanostatic load | **SIMULATED / INJECTED**| *"Simulation indicates terminal voltage collapse occurs in depleted cells, which would trigger the physical 10.0V comparator."* |
| **Micro-Short Drift Detection (Attack 1)**| $22.0\text{ mV/hr}$ drift rate | Synthetic leakage parameter injected into cell health definition | **INJECTED** | *"Demonstrated that Layer 1 Triage intercepts self-discharge rates exceeding 20 mV/hr."* |
| **Epistemic Abstention Under Tagless NMC** | $98\% - 100\%$ abstention | Multi-cohort evaluation under uninformative intake priors | **SIMULATED** | *"Demonstrated that SECONDShift refrains from forced classification, routing unresolvable ambiguity to HOLD/RECYCLE."* |

---

## 2. Hard Rule on Technical Disclosures

1. **NO Claim of Physical Certification:** The system is an advanced university research prototype operating under SELV ($<60\text{V}$ DC) rules. It does not possess commercial safety certification (UL 1973, IEC 62619, ISO 26262).
2. **NO Claim of Thermal Runaway Prevention:** Autonomous over-temperature and overcurrent cutoffs are physical reality; preventing mechanical crushing thermal runaway is an unverified condition.
3. **Evidence Distinction:** All presentations must clearly separate physical bench instrument captures from numerical simulations.
