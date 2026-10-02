# COMPREHENSIVE SYSTEM LIMITATIONS & SCIENTIFIC BOUNDARIES

**Project:** SECONDShift — Risk-Constrained Adaptive Qualification Under State and Model Uncertainty  
**Audit Date:** 2026-10-02  
**Status:** REWRITTEN & PUBLICATION-READY  
**Repository Document:** `secondshift/docs/LIMITATIONS.md`  

---

## 1. Executive Statement of Limitations

Scientific defensibility requires explicit demarcation of operational envelopes, empirical limitations, and potential failure regimes. SECONDShift is an academic research platform, not a certified industrial appliance. 

Below are the 17 audited operational and methodological limitations governing this work.

---

## 2. Inventory of Methodological & Technical Limitations

### Limitation 1: Small Physical Sample Size ($N=12$)
- **Description:** Empirical benchmark qualification is evaluated on a curated 12-specimen laboratory cohort (8 LFP, 3 NMC, 1 Unknown).
- **Impact on Findings:** Limits statistical generalizability to diverse second-life scrap streams. Paired decision accuracy difference against Baseline A is underpowered (McNemar $p = 0.6250 > 0.05$).
- **Mitigations Attempted:** Synthesized 250-trial Monte Carlo stress fleets (`run_chemistry_attacks.py`) and 14 adversarial injection scenarios.
- **Unresolved Risk:** Hidden failure modes unique to unmodeled degradation paths may not appear in an $N=12$ cohort.
- **Proposed Future Experiment:** Sized benchmark execution on $N \ge 300$ physically retired commercial cells from diverse municipal fleet sources.

---

### Limitation 2: Hardware Execution via Simulation Mock in Repository
- **Description:** In-repository execution relies on `MockHermesHardware` rather than an active live serial communication driver to a physical bench cycler.
- **Impact on Findings:** Telemetry traces in automated test suites are numerically emulated rather than physically captured during repository CI runs.
- **Mitigations Attempted:** Physical hardware validation was conducted on external prototype testbed; single-trace oscilloscope latencies ($11.8\text{ ms}$ and $194.2\text{ ms}$) were cataloged in documentation.
- **Unresolved Risk:** Firmware communication dropouts, USB serial latency, and real-time buffer overflows are bypassed in repository testing.
- **Proposed Future Experiment:** Integrate a physical Hardware-in-the-Loop (HIL) serial test fixture with automated oscilloscope trigger logging into repository CI.

---

### Limitation 3: Inability to Distinguish Zero Population FAR from Zero Sample FAR
- **Description:** Zero observed False Acceptances ($0/7$ unsafe packs accepted) bounds the population False Acceptance Rate to a 95% one-sided upper confidence bound of $34.82\%$, not $<1.0\%$.
- **Impact on Findings:** Absolute claims of $<1.0\%$ population safety cannot be substantiated from small sample data alone.
- **Mitigations Attempted:** Exact Clopper-Pearson confidence intervals are formally computed and disclosed in all tables and reports.
- **Unresolved Risk:** The true population FAR under noisy real-world scrap could be as high as $34.8\%$.
- **Proposed Future Experiment:** High-throughput automated testing of $N \ge 299$ ground-truth unsafe retired modules without a single false acceptance to prove $\text{FAR}_{95\%, \text{UCB}} \le 1.0\%$.

---

### Limitation 4: Lack of Long-Term Secondary Aging & Cycling Data
- **Description:** SECONDShift qualifies cells at the point of intake; it does not track long-term calendar or cycle degradation after deployment in second-life BESS.
- **Impact on Findings:** A cell qualified as `OPERATE` might experience accelerated knee-point degradation or premature impedance rise after 200 secondary cycles.
- **Mitigations Attempted:** Conservative SOH cutoffs ($70\%$ for full operation, $65\%$ for derating) provide a buffer above typical retirement thresholds.
- **Unresolved Risk:** Non-linear secondary degradation curves could cause unexpected field failures.
- **Proposed Future Experiment:** 1,000-cycle continuous second-life durability cycling on 20 qualified packs under C/2 stationary storage duty cycles.

---

### Limitation 5: Dependency on Chemistry Likelihood Parameter Tuning
- **Description:** Bayesian chemistry inference relies on hardcoded Gaussian likelihood templates for post-pulse voltage polarization ($V_{\text{pol}} = 22\text{ mV}$ for LFP, $38\text{ mV}$ for NMC).
- **Impact on Findings:** Mismatches between physical cell chemistry parameters and templates can cause misclassification or excessive abstention.
- **Mitigations Attempted:** Co-designed parameter calibration against baseline cell relaxation curves and enforced strict `UNKNOWN` abstention.
- **Unresolved Risk:** In extreme ambient temperatures or aged cells with thick SEI layers, LFP relaxation may shift to $30\text{ mV}$, confusing the classifier.
- **Proposed Future Experiment:** Continuous adaptive non-parametric kernel density estimation (KDE) over empirical relaxation curves.

---

### Limitation 6: Sensitivity to OCV Relaxation Timing and Temperature
- **Description:** Accurate open-circuit voltage (OCV) and relaxation kinetics require stabilized thermal and electrochemical states.
- **Impact on Findings:** Testing cells immediately after transport or high-current thermal shock introduces significant OCV drift ($>10\text{ mV}$).
- **Mitigations Attempted:** Integrated Stage 0 resting thermal stabilization check and 45-second relaxation dwell monitoring.
- **Unresolved Risk:** Rapid triage under winter ambient temperatures ($<5^\circ\text{C}$) will distort overpotential relaxation kinetics.
- **Proposed Future Experiment:** Climate chamber characterization of relaxation kinetics from $-10^\circ\text{C}$ to $+55^\circ\text{C}$.

---

### Limitation 7: Known Failure Modes Where SECONDShift Fails to Reject
- **Description:** Under specific stochastic draws (e.g., Seed 123 in Monte Carlo testing), a borderline NMC cell disguised as LFP with high internal resistance passed due to drawn sensor noise canceling the polarization gap.
- **Impact on Findings:** Empirically proves that noise can occasionally mask chemistry signatures.
- **Mitigations Attempted:** Mandating multi-stage pulse profiles (short pulse + coulometric cycle) before final qualification.
- **Unresolved Risk:** An adversary deliberately tuning pre-charge voltage to mimic the LFP plateau could evade single-pulse detection.
- **Proposed Future Experiment:** Implement a compulsory multi-frequency pseudo-random binary sequence (PRBS) excitation step before granting `OPERATE`.

---

### Limitation 8: Incomplete Chemistry Coverage
- **Description:** Explicit likelihood models are provided only for LFP and NMC. Chemistries such as LCO, NCA, LMO, LTO, and Sodium-ion are unmodeled.
- **Impact on Findings:** Non-LFP/NMC cells cannot be qualified for reuse; they are invariably routed to `HOLD` or `RETIRE`.
- **Mitigations Attempted:** The $\mathcal{M} = \text{UNKNOWN}$ hypothesis class acts as an epistemic catchment basin to safely hold unmodeled chemistries.
- **Unresolved Risk:** Commercial value is lost by rejecting viable Sodium-ion or NCA packs.
- **Proposed Future Experiment:** Expand the multi-hypothesis library to include 6 distinct electrochemistries with validated OCV-SOC lookup tables.

---

### Limitation 9: SELV Voltage Limitation ($<60\text{ V}$)
- **Description:** The HERMES hardware prototype is designed strictly for Safety Extra-Low Voltage ($<60\text{ V}$ DC, 4S module format).
- **Impact on Findings:** Cannot directly test full automotive 400V or 800V traction packs without module-level teardown.
- **Mitigations Attempted:** Focus on modular second-life triage where decommissioned packs are disassembled into 48V or 12V modules.
- **Unresolved Risk:** Module teardown introduces manual labor and handling overhead.
- **Proposed Future Experiment:** Design a galvanically isolated 400V qualification testbed with automotive High-Voltage Interlock Loops (HVIL).

---

### Limitation 10: Contact Bounce and Relay Degradation Not Modeled
- **Description:** Physical automotive electromechanical relays (JD1912) experience contact bounce (1–3 ms) and contact erosion over thousands of switching operations.
- **Impact on Findings:** Repeated high-current pulse interruption can degrade contact resistance and cause contact welding.
- **Mitigations Attempted:** Snubber flyback diodes and TVS diodes suppress back-EMF spikes.
- **Unresolved Risk:** A welded contactor completely defeats the independent analog disconnect safety barrier!
- **Proposed Future Experiment:** Replace mechanical contactors with bidirectional solid-state MOSFET switches (SiC or GaN) with active desaturation detection.

---

### Limitation 11: ADC Noise Floor Assumptions vs Real-World Industrial EMI
- **Description:** Simulation assumes Gaussian ADC noise ($\sigma_V = 1.0\text{ mV}$). Industrial factory environments suffer heavy variable-frequency drive (VFD) switching noise and mains hum.
- **Impact on Findings:** Real-world EMI can corrupt delicate $dV/dt$ micro-short slope detection ($15\text{ mV/hr}$).
- **Mitigations Attempted:** Implemented 16-bit differential ADC (ADS1115) with analog RC input filtering and FIR averaging.
- **Unresolved Risk:** High common-mode factory noise could trigger false triage rejections.
- **Proposed Future Experiment:** Conduct radiated and conducted EMI testing in an industrial battery pack manufacturing plant.

---

### Limitation 12: Thermal Gradient Assumptions in Multi-Cell Modules
- **Description:** Thermal modeling assumes a lumped-parameter thermal node per cell, neglecting 3D spatial temperature gradients within tightly packed modules.
- **Impact on Findings:** Core temperature of internal pouch cells may exceed surface thermocouple readings by $>10^\circ\text{C}$.
- **Mitigations Attempted:** Surface temperature threshold is conservatively set to $45^\circ\text{C}$ (far below typical $60^\circ\text{C}$ limits).
- **Unresolved Risk:** Core overheating during high-current pulses in dense brick modules.
- **Proposed Future Experiment:** Embed fiber-optic Bragg grating (FBG) internal temperature sensors in test modules during validation.

---

### Limitation 13: Economic Model Assumptions
- **Description:** Life-cycle economic valuations rely on fixed Indian commercial tariffs (₹10/kWh), scrap buyback rates (₹1,200/kWh), and liability penalties (₹60,000).
- **Impact on Findings:** Net value fluctuates significantly in different global geographies.
- **Mitigations Attempted:** Parametric tornado sensitivity analysis bounded ranges from ₹6 to ₹14/kWh and ₹25,000 to ₹1,50,000 liability.
- **Unresolved Risk:** In markets with subsidized power or cheap virgin cells, second-life economics may become unviable.
- **Proposed Future Experiment:** Dynamic market-linked optimization engine ingesting real-time metal exchange (LME) and local power exchange tariffs.

---

### Limitation 14: Lack of Formal Regulatory Safety Certification
- **Description:** SECONDShift is an academic prototype and has not undergone formal laboratory certification to UL 1974 (Standard for Evaluation for Repurposing Batteries), IEC 62619, or ISO 26262.
- **Impact on Findings:** System cannot be legally deployed in commercial stationary storage manufacturing without third-party listing.
- **Mitigations Attempted:** Designed architecture to adhere to key safety principles of UL 1974 (quarantine triage, independent cutoff).
- **Unresolved Risk:** Regulatory non-compliance in commercial deployment.
- **Proposed Future Experiment:** Formal pre-compliance audit conducted with a certified testing laboratory (e.g., TÜV Rheinland or UL Solutions).

---

### Limitation 15: Non-Prevention of Internal Metallurgical Shorts
- **Description:** SECONDShift disconnects electrical load upon detecting over-voltage, under-voltage, or excessive thermal rise. It cannot extinguish or halt chemical fires initiated by mechanical crush, nail penetration, or pre-existing self-propagating internal lithium dendrites.
- **Impact on Findings:** Absolute claims of "thermal runaway prevention" are chemically and physically invalid.
- **Mitigations Attempted:** Explicit retraction of "prevention" claims; relabeled as "autonomous electrical abuse mitigation."
- **Unresolved Risk:** A cell with latent dendritic growth could short circuit internally hours after passing triage.
- **Proposed Future Experiment:** Couple electrical qualification with high-resolution acoustic emission or ultrasonic pulse screening.

---

### Limitation 16: Asymmetry of False Rejection Cost in Low-Liability Markets
- **Description:** In scenarios where field failure liability is exceptionally low ($L_{\text{failure}} < ₹1,850$), SECONDShift's conservative false rejection rate ($20\%$ on benchmark) incurs higher opportunity loss than Baseline A's aggressive qualification.
- **Impact on Findings:** The conservative safety bias is only economically optimal when failure carries substantial liability or warranty exposure.
- **Mitigations Attempted:** Quantified economic crossover points in `ECONOMIC_SENSITIVITY_AUDIT.md`.
- **Unresolved Risk:** Aggressive operators prioritizing short-term module volume may reject SECONDShift's conservative screening.
- **Proposed Future Experiment:** Tiered risk-appetite policy tuning where safety risk threshold $\epsilon$ is adjustable based on end-use application severity.

---

### Limitation 17: Computational & Edge Microcontroller Constraints
- **Description:** The Gauss-Hermite numerical quadrature and full covariance matrix updates require double-precision floating-point arithmetic.
- **Impact on Findings:** Executing real-time EVSI calculations directly on an 8-bit or low-end 32-bit MCU without FPU introduces latency ($>500\text{ ms}$).
- **Mitigations Attempted:** FreeRTOS architecture partitions tasks: Core 0 handles deterministic real-time sampling while Core 1 / host PC executes Bayesian updates.
- **Unresolved Risk:** Microcontroller memory exhaustion if test history buffers grow unbounded.
- **Proposed Future Experiment:** Pre-computed offline lookup tables (LUTs) for VOI policies mapped to an ARM Cortex-M4 or M33 embedded DSP.
