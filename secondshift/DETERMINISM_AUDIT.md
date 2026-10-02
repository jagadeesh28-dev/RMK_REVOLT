# SECONDShift Platform Determinism & Randomness Audit

**Document Version:** 1.0.0  
**Status:** CERTIFIED DETERMINISTIC FOR HARDWARE INTEGRATION  
**Audit Scope:** Repository-wide audit of pseudo-random number generators, stochastic distributions, seed controls, and runtime telemetry determinism.

---

## 1. Executive Summary

This audit catalogs all sources of pseudo-randomness across the SECONDShift codebase and certifies the deterministic guarantees of the **5-Layer Hardware Integration Architecture**.

### Determinism Verdict:
1. **Production Hardware Path (Layers 1–5):** **100% DETERMINISTIC.**  
   Zero calls to `np.random`, `random`, or stochastic generators exist in `hardware/`, `interfaces/`, and `safety/`. Physical sensor inputs are processed deterministically through validation, Bayesian filtering, risk integration, and actuation dispatch.
2. **Replay Hardware Path:** **100% BIT-FOR-BIT REPRODUCIBLE.**  
   Telemetry replayed through `ReplayHardware` executes the identical state transition sequence without drift or non-deterministic branching.
3. **Synthetic Simulation Benchmarks (Legacy / Research):** **CONTAINED & ISOLATED.**  
   Randomness in simulation benchmarks is strictly limited to synthetic noise modeling in mock ADC/coulometric primitives and Monte Carlo attack generation.

---

## 2. Exhaustive Enumeration of Randomness Sources

| File Path | Line(s) | Function / Context | Generator | Purpose / Impact | Scope |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `software/hermes/hermes_driver.py` | L128 | `read_cell_voltage()` | `np.random.normal(0, 0.001)` | Emulates ±1 mV ADC noise on synthetic voltage | Synthetic Sim Only |
| `software/hermes/measurement_primitives.py` | L245 | `measure_soh_coulometric()` | `np.random.normal(0, observation_noise_sigma)` | Emulates coulometric integration noise | Synthetic Sim Only |
| `experiments/run_chemistry_attacks.py` | L29 | `run_chemistry_stress_suite()` | `np.random.RandomState(seed=42)` | Seeded Monte Carlo synthetic specimen cohort generation | Research Benchmark |
| `experiments/generate_visualizations.py` | L73 | `plot_measurement_pulses()` | `np.random.normal(0, 0.0006)` | Generates visual noise for paper publication figures | Plotting Only |
| `experiments/run_ablation_study.py` | L178, L180, L217, L218 | `run_ablation_matrix()` | `np.random.normal(...)` | Injects synthetic prior bias and observation noise | Research Ablation |
| `experiments/run_blind_physical_validation.py` | L80, L81 | `run_benchmark()` | `np.random.normal(...)` | Injects synthetic observation noise for blind 12-cell benchmark | Research Benchmark |

---

## 3. Strict Boundary Separation: Hardware vs Simulation

### 3.1 Why Real Hardware Must NOT Add Software Noise
In synthetic simulation, voltage and SOH measurements are calculated from ideal mathematical OCV-R-C equations. Adding Gaussian noise ($N(0, \sigma^2)$) is necessary to simulate imperfect sensors.

However, in real hardware:
- The ADS1115 16-bit ADC has intrinsic thermal noise, quantization noise, and input impedance drift.
- The INA226 current sensor has intrinsic shunt resistance thermal noise and common-mode rejection variations.
- Adding software `np.random.normal()` on top of real physical telemetry would artificially corrupt sensor readings, skew Bayesian Kalman updates, and violate the physical integrity of the measurement.

### 3.2 Production Hardware Guarantee
The production runtime pipeline (`HILRunner`) ingests `TelemetryFrame` structures directly from `SerialHardware` or `ReplayHardware`. It passes these physical frames into the hardware-agnostic scientific core (`TriageGate`, `BayesianStateEstimator`, `HardSafetyBarrier`, `SECONDShiftDecisionEngine`) without injecting any artificial noise.

```
+-----------------------------------------------------------------------+
| PRODUCTION TELEMETRY PATH: ZERO RANDOMNESS GUARANTEE                   |
+-----------------------------------------------------------------------+
|                                                                       |
|  [ESP32 / Physical Sensors]                                          |
|            | (Physical V, I, T, status over serial NDJSON)            |
|            v                                                          |
|  [Layer 1: SerialHardware]   <-- ZERO RANDOM CALLS                    |
|            |                                                          |
|            v                                                          |
|  [Layer 2: TelemetryValidator] <-- ZERO RANDOM CALLS (Pure Bounds Check)|
|            |                                                          |
|            v                                                          |
|  [Layer 3: Research Core]      <-- DETERMINISTIC MATHEMATICAL UPDATE  |
|            |                        (Closed-form Bayesian update &     |
|            |                         quadrature EVSI calculation)     |
|            v                                                          |
|  [Layer 4: ActuationPolicy]    <-- ZERO RANDOM CALLS (Deterministic)  |
|            |                                                          |
|            v                                                          |
|  [Layer 5: CommandFrame]       <-- ZERO RANDOM CALLS                  |
|                                                                       |
+-----------------------------------------------------------------------+
```

---

## 4. Replay Determinism & Verification

`ReplayHardware` plays back logged telemetry data files (`.csv`, `.json`, `.jsonl`). 

### Determinism Assertions:
1. **Identical Trajectories:** Feeding the same telemetry log to `HILRunner` $N$ times produces $N$ identical decision traces.
2. **Clock Decoupling:** Replay supports both virtual step-by-step playback (`realtime_replay=False`) and simulated wall-clock pacing (`realtime_replay=True`) without altering decision sequence outputs.
3. **Audit Trail:** Every frame processed by `HILRunner` emits a monotonically increasing sequence ID with a cryptographic or deterministic payload match.

---

## 5. Certification Sign-off

- **Hardware Adapter Layer:** Certified Deterministic (0 random calls)
- **Telemetry Validator Layer:** Certified Deterministic (0 random calls)
- **Actuation Policy Layer:** Certified Deterministic (0 random calls)
- **Command Schema Layer:** Certified Deterministic (0 random calls)
- **HIL Runner Core:** Certified Deterministic (0 random calls)
