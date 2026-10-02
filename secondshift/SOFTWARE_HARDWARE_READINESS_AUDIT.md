# SOFTWARE-TO-HARDWARE READINESS AUDIT

**Project:** SECONDShift — Risk-Constrained Adaptive Qualification Under State and Model Uncertainty  
**Audit Date:** 2026-10-02  
**Role:** Lead Embedded-Systems & Research-Software Architect  
**Status:** COMPLETE & PRE-INTEGRATION FREEZE  
**Document ID:** `SOFTWARE_HARDWARE_READINESS_AUDIT.md`  

---

## 1. Executive Summary & Objective

This audit investigates the existing SECONDShift software architecture to determine its readiness for future physical integration with real battery hardware, embedded microcontrollers (ESP32), and analog safety interlocks.

**Core Invariant:** The validated scientific decision engine, mathematical risk integrals, deterministic triage gates, and Bayesian estimators must remain completely hardware-agnostic and uncompromised. Hardware integration must occur through strictly layered adapters without modifying the scientific core.

---

## 2. Five-Layer Target Architecture

The integration architecture establishes five strictly decoupled layers:

```
[ LAYER 1: HARDWARE ADAPTER ]
  - Serial transport (UART / USB CDC)
  - Packet framing (newline-delimited JSON)
  - Connection management & heartbeat
  - Raw byte ingestion & transmission
             │
             ▼ Raw Telemetry Dict
[ LAYER 2: MEASUREMENT NORMALIZATION ]
  - Telemetry validation (schema, NaN, Inf, bounds)
  - Timestamp & sequence verification
  - Sensor health & fault classification
  - Unit enforcement (V, A, °C, s)
             │
             ▼ Validated TelemetryFrame
[ LAYER 3: SECONDShift RESEARCH ENGINE (HARDWARE-AGNOSTIC) ]
  - Stage 0 Deterministic Triage (TR-01 to TR-09)
  - Multi-hypothesis Bayesian Chemistry Disambiguation (LFP, NMC, UNK)
  - Normal-Gamma State Estimation (SOH, R0)
  - Hard Probabilistic Safety Barrier (P(Fail) <= 0.01)
  - Value of Information (EVSI) Stopping Policy
             │
             ▼ Research Decision: OPERATE / DERATE / RETIRE / HOLD
[ LAYER 4: SAFETY & ACTUATION POLICY ]
  - Abstract intent mapping:
      OPERATE -> ENABLE_LOAD
      DERATE  -> LIMIT_LOAD
      RETIRE  -> ISOLATE
      HOLD    -> KEEP_ISOLATED
  - Fail-safe state enforcement under communication loss
             │
             ▼ Abstract CommandFrame
[ LAYER 5: HARDWARE COMMAND ADAPTER ]
  - Protocol formatting for embedded controller
  - Interlock verification & checksumming
  - Serial command transmission
```

---

## 3. Section-by-Section Forensic Audit

### A. Existing Architecture
The existing runtime architecture consists of:
- `ClosedLoopRunner` (`software/secondshift/closed_loop_runner.py`): Top-level orchestrator.
- `HermesMeasurementEngine` (`software/hermes/measurement_primitives.py`): Measurement abstractions.
- `MockHermesHardware` (`software/hermes/hermes_driver.py`): In-memory physical hardware emulator.
- Core scientific modules: `TriageGate`, `ChemistryDisambiguationEngine`, `BayesianStateEstimator`, `ModelUncertaintyEvaluator`, `HardSafetyBarrier`, `ValueOfInformationEngine`, `SECONDShiftDecisionEngine`.

### B. Existing Hardware Dependencies
- Direct calls to `self.hw.read_sensors()` returning unvalidated dictionary structures:
  `{"voltages": [...], "current": float, "temperatures": [...], "relay_enabled": bool, "hardware_tripped": bool, "trip_reason": str}`.
- Actuation commands are executed via direct method invocations: `self.hw.set_load_current(current_a)` and `self.hw.set_cell_state(cell_idx, state)`.
- No abstracted serial transport, packet framing, or baud rate configuration exists in runtime code.

### C. Existing Simulation Dependencies
- `MockHermesHardware` contains internal simulation models:
  - Synthetic OCV piecewise curves for LFP and NMC.
  - Lumped-parameter thermal model: $\dot{Q} = I^2 R_0 dt - h(T - T_{\text{amb}})$.
  - Simulated watchdog timer feeding and hardware trips.
- In `HermesMeasurementEngine`, `sim_mode=True` skips real time delays (`self._sleep` increments `_sim_clock` and sleeps 1 ms).

### D. Existing Research-Engine Dependencies
- The research decision engine operates on normalized engineering units:
  - Voltages in Volts ($V$)
  - Resistances in Ohms ($\Omega$) or milliohms ($\text{m}\Omega$)
  - Temperatures in Celsius ($^\circ\text{C}$)
  - Capacity in retention ratio ($\text{SOH} \in [0.0, 1.2]$)
- The scientific core is already largely hardware-agnostic; its only coupling is that `ClosedLoopRunner` directly imports `HermesMeasurementEngine` rather than consuming normalized telemetry frames.

### E. Ground-Truth Leakage Risks
- **Risk Identified:** In `data/raw/ground_truth_registry.json`, true cell SOH, $R_0$, and chemistry are stored.
- **Current State:** Quarantined to test harness and `MockHermesHardware`. Estimators and triage gates do NOT import this file.
- **Hardware Requirement:** In real hardware mode and replay mode, the software must be strictly prohibited from attempting to load or reference `ground_truth_registry.json`.

### F. Randomness Sources in Repository
- `software/hermes/hermes_driver.py` (L128): `np.random.normal(0, 0.001)` (1 mV simulated ADC noise).
- `software/hermes/measurement_primitives.py` (L245): `np.random.normal(0, observation_noise_sigma)` (coulometric SOH observation noise).
- `experiments/run_blind_physical_validation.py` (L80-81): Baseline A observation noise.
- `experiments/run_chemistry_attacks.py` (L29): Seeded Monte Carlo fleet generator.
- **Production Finding:** Adding synthetic `np.random.normal` to real physical telemetry would introduce artificial variance. In real hardware mode, measurement noise is physically intrinsic and must NOT be augmented with software pseudo-random draws.

### G. Determinism Risks
- Unseeded calls to `np.random.normal` in measurement primitives introduce stochastic divergence if invoked during replay.
- In replay and production mode, telemetry processing must be 100% deterministic: identical input frames must yield identical state updates and actuation decisions.

### H. API Coupling
- `ClosedLoopRunner` combines measurement acquisition, test loop iteration, and decision execution into a single synchronous loop.
- Decoupling requires separating the acquisition of telemetry frames from the execution of the Bayesian update steps.

### I. Missing Hardware Interfaces
1. Strongly typed canonical `TelemetryFrame` dataclass.
2. Structured `TelemetryValidator` with explicit fault flags (`STALE`, `NAN`, `OUT_OF_RANGE`, `COMMUNICATION_FAULT`).
3. Abstract `HardwareInterface` contract (`connect`, `disconnect`, `read_telemetry`, `send_command`, `get_status`).
4. Robust `SerialHardware` transport adapter with newline-delimited JSON parsing and auto-reconnect.
5. Deterministic `ReplayHardware` reading recorded CSV/JSON telemetry.
6. Abstract `ActuationPolicy` translating research decisions into `CommandFrame`.
7. Hardware-in-the-Loop (`HILRunner`) pre-hardware test engine.
8. Structured JSONL `EventLogger`.
9. Explicit 11-state System State Machine.
10. Hardware configuration file `config/hardware.yaml`.

### J. Recommended Refactoring Plan
- **DO NOT** modify the mathematical or scientific files in `software/`.
- Introduce new decoupled packages:
  - `secondshift/interfaces/`: Contracts, schemas, validation, logging, state machine.
  - `secondshift/hardware/`: Mock hardware, serial hardware, replay hardware, HIL runner.
  - `secondshift/safety/`: Actuation policy, interlock rules.
- Provide backward-compatible adapters so existing benchmarks and tests continue to pass 100% without modification.

### K. Files That Must NOT Be Modified (Scientific Core Frozen)
- `software/triage/triage_gate.py`
- `software/chemistry/chemistry_engine.py`
- `software/estimators/bayesian_state_estimator.py`
- `software/estimators/model_uncertainty.py`
- `software/safety/hard_safety_barrier.py`
- `software/voi/evsi_calculator.py`
- `software/secondshift/decision_engine.py`
- All paper sections in `secondshift/paper/`

### L. Files That Can Safely Be Extended or Created
- New files in `secondshift/interfaces/`
- New files in `secondshift/hardware/`
- New files in `secondshift/safety/`
- `config/hardware.yaml`
- `secondshift/cli.py` & `secondshift/__main__.py`
- New test suites in `tests/`
