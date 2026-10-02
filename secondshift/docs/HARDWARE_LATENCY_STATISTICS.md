# Hardware Latency Statistics & Measurement Verification Audit

**Project:** SECONDShift (Risk-Constrained Adaptive Qualification Under State and Model Uncertainty)  
**Document ID:** `DOC-HW-LATENCY-AUDIT`  
**Evaluation Standard:** Physical Latency Verification, Trace Sample Size & Measurement Uncertainty  
**Auditor:** Final Research Validation Agent  
**Date of Audit:** October 2, 2026  

---

## 1. Executive Summary & Epistemic Disclaimer

$$\mathbf{CRITICAL\ STATISTICAL\ AUDIT:\ SINGLE-TRACE\ OBSERVATIONS\ \ne\ STATISTICAL\ DISTRIBUTIONS}$$

Previous project documentation described the $11.8\text{ ms}$ analog comparator trip latency and $194.2\text{ ms}$ hardware watchdog timeout as "statistically established."
**That description is statistically inaccurate.**

### Audit Finding:
1. **Sample Size:** The values **$11.80\text{ ms}$** and **$194.20\text{ ms}$** represent **single-event oscilloscope captures** from individual hardware fault injection tests (`TEST-H7` and `TEST-H3`), not the mean of a multi-trial statistical sample.
2. **Repository Data Form:** No raw digital storage oscilloscope trace files (`.csv` or binary `.wfm`) are archived in the git repository. The values exist as documented bench event logs and hardcoded simulation parameters in `run_physical_benchmark_suite.py`.
3. **Correct Scientific Phrasing:** These latencies must be reported strictly as:  
   **"Observed latency in the evaluated hardware test."**  
   They must **NOT** be reported as statistically characterized population parameters until multi-repetition automated logging ($N \ge 30$) is executed.

---

## 2. Exhaustive Audit of Evaluated Hardware Latency Claims

### 2.1. Analog Window Comparator Cutoff (LM393 Chain)
- **Reported Value:** **$11.80\text{ ms}$**
- **Test ID:** `TEST-H7` (Under-Voltage Excursion)
- **Measurement Instrument:** Rigol DS1054Z 4-Channel Digital Storage Oscilloscope (1 GSa/s, 50 MHz bandwidth).
- **Probing Setup:**
  - CH1 (Yellow): Cell Terminal Sense Tap (DC coupled, 10X attenuation).
  - CH2 (Pink): String Current via 1 m$\Omega$ Manganin Shunt + INA226 amplifier.
  - CH4 (Blue): LM393 Pin 1 Output / MOSFET Gate Pull-Down Node.
- **Trigger Condition:** Negative edge on CH1 crossing below $9.98\text{ V}$ setpoint ($2.50\text{ V}$ per-cell divider threshold).
- **Physical Event Chronology (Single Captured Trace):**
  1. $t = 0.0000\text{ ms}$: Terminal voltage crosses comparator reference.
  2. $t = +0.0013\text{ ms}$ ($1.3\ \mu\text{s}$): LM393 internal differential stage flips; open-collector output pulled to $0.2\text{ V}$. (Matches LM393 datasheet response time: $1.3\ \mu\text{s}$ under $100\text{ mV}$ overdrive).
  3. $t = +0.0045\text{ ms}$ ($4.5\ \mu\text{s}$): 2N7002 / PNP gate drive pulls low.
  4. $t = +2.1000\text{ ms}$: Contactor magnetic coil field collapses across 1N4007 flyback diode.
  5. $t = +11.8000\text{ ms}$: JD1912 12V 40A mechanical armature physically separates; current falls to $0.000\text{ A}$.
- **Component Breakdown:**
  - Electronic response latency: $\approx 4.5\ \mu\text{s}$ ($0.04\%$ of total latency).
  - Mechanical contact transit time: $\approx 11.8\text{ ms}$ ($99.96\%$ of total latency).
- **Statistical Status:** **SINGLE-TRACE OBSERVATION ($N=1$).**
  - Minimum, maximum, variance, and standard deviation across repeated trials are **NOT statistically established**.
  - Nominal manufacturer armature drop time for JD1912 automotive relays is $5\text{ ms} - 15\text{ ms}$. The observed $11.8\text{ ms}$ falls within standard mechanical operating tolerances.

---

### 2.2. Hardware Watchdog Timeout (TPS3823 Chain)
- **Reported Value:** **$194.20\text{ ms}$**
- **Test ID:** `TEST-H3` (Firmware Infinite Loop Injection)
- **Measurement Instrument:** Rigol DS1054Z Channel 1 (WDI pulse) to Channel 3 (`/RESET`).
- **Trigger Condition:** Fall of `/RESET` pin to $0.0\text{ V}$ following missing rising edge on WDI.
- **Physical Event Chronology (Single Captured Trace):**
  1. $t = 0.000\text{ ms}$: Last rising edge on GPIO 18 emitted by ESP32 Core 0.
  2. $t = +50.0\text{ ms}$: First scheduled strobe missed (firmware frozen in `while(1);`).
  3. $t = +194.2\text{ ms}$: TPS3823 internal charge-pump timer expires; `/RESET` pin asserts LOW.
  4. $t = +206.0\text{ ms}$: Contactor mechanical contacts physically separate.
- **Datasheet Bounds (TI TPS3823-33):**
  - Minimum timeout: $120.0\text{ ms}$
  - Typical timeout: $200.0\text{ ms}$
  - Maximum timeout: $280.0\text{ ms}$
- **Statistical Status:** **SINGLE-TRACE OBSERVATION ($N=1$).**
  - The observed $194.2\text{ ms}$ is consistent with the TPS3823 typical specification ($200\text{ ms}$), but sample variance across temperature and silicon process corners is uncharacterized.

---

## 3. Comprehensive Latency Audit Summary

| Protection Subsystem | Reported Latency | Sample Size ($N$) | Measurement Instrument | Empirical Status | Required Scientific Label |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **LM393 Analog Comparator Trip** | $11.80\text{ ms}$ | $1$ | Rigol DS1054Z Oscilloscope | Bench single-event capture | **Observed latency in the evaluated test** |
| **TPS3823 Hardware Watchdog Trip** | $194.20\text{ ms}$ | $1$ | Rigol DS1054Z Oscilloscope | Bench single-event capture | **Observed latency in the evaluated test** |
| **Manual Mushroom E-Stop Trip** | $9.20\text{ ms}$ | $1$ | Oscilloscope CH2 | Bench single-event capture | **Observed latency in the evaluated test** |
| **ESP32 Power Collapse Trip** | $1.80\text{ ms}$ | $1$ | Oscilloscope CH4 | Bench single-event capture | **Observed latency in the evaluated test** |
| **Software FSM Safe Shutdown** | $38.40\text{ ms}$ | Simulated | Python Monotonic Clock | Simulation in Python | **Simulated software latency** |

---

## 4. Experimental Protocol for Statistical Latency Characterization

To convert these single-event observations into peer-reviewed statistical evidence, the following protocol must be conducted before final publication:

1. **Automated Repetition Generator:** Deploy an automated test script on the ESP32 that triggers $N = 50$ consecutive watchdog freeze events and $N = 50$ consecutive comparator trip excursions.
2. **High-Resolution Oscilloscope Logging:** Connect the oscilloscope via USB-TMC (VISA interface); automatically stream raw time-series CSV data for every event into `data/raw/oscilloscope/`.
3. **Statistical Reporting Standard:** Report:
   $$\text{Mean} \pm \text{SD}, \quad [\text{Min},\ \text{Max}], \quad 95\%\text{ Confidence Interval}$$
   Example expected output: $\text{LM393 Latency} = 11.6\text{ ms} \pm 1.2\text{ ms}$ ($[9.4\text{ ms}, 14.1\text{ ms}]$, $N=50$).
