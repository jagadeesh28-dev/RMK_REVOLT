# SECONDShift Hardware Integration Architecture

**Document Version:** 1.0.0  
**Status:** ARCHITECTURALLY VERIFIED & HARDWARE-READY  
**Scope:** Decoupled 5-Layer Software-Hardware Integration Interface

---

## 1. Architectural Overview

The SECONDShift platform employs a strict, five-layer unidirectional and decoupled architecture designed to bridge the gap between validated Bayesian research algorithms and physical battery test execution on the HERMES testbed.

Under this architecture:
- **Research software NEVER touches physical GPIO, hardware addresses, or low-level registers.**
- **Physical hardware drivers NEVER access ground-truth registries or simulation parameters.**
- **Telemetry validation operates as a strict, non-negotiable gatekeeper between physical sensors and mathematical state estimation.**
- **Actuation is governed by a supervisory fail-safe policy layer that guarantees safety constraints override economic optimization.**

```
+=============================================================================+
|                       SECONDShift 5-LAYER ARCHITECTURE                      |
+=============================================================================+
|                                                                             |
|  [ LAYER 1: HARDWARE ADAPTERS ]                                             |
|  +---------------------+  +----------------------+  +---------------------+ |
|  |    MockHardware     |  |    SerialHardware    |  |    ReplayHardware   | |
|  |  (Synthetic Pack)   |  |   (Physical UART)    |  |   (Recorded Log)    | |
|  +---------------------+  +----------------------+  +---------------------+ |
|             |                         |                         |           |
|             +-------------------------+-------------------------+           |
|                                       | Raw Sensor Bytes / NDJSON           |
|                                       v                                     |
|  [ LAYER 2: MEASUREMENT NORMALIZATION & VALIDATION ]                        |
|  +-----------------------------------------------------------------------+  |
|  |                         TelemetryValidator                            |  |
|  |   - Rejects NaN, Inf, physical range violations, stale timestamps     |  |
|  |   - Checks sensor health flags, sequence continuity, clock drift      |  |
|  |   - Outputs: Canonical Strongly-Typed TelemetryFrame                  |  |
|  +-----------------------------------------------------------------------+  |
|                                       |                                     |
|                                       | Validated Physical Measurements     |
|                                       v (V, I, T, dV/dt, status)            |
|  [ LAYER 3: SCIENTIFIC RESEARCH CORE (HARDWARE-AGNOSTIC) ]                  |
|  +-----------------------------------------------------------------------+  |
|  | 1. Stage 0 Triage Gate (Mechanical & Electrochemical Feasibility)     |  |
|  | 2. Chemistry Disambiguation Engine (Bayesian Model Uncertainty)       |  |
|  | 3. Bayesian State Estimator (Degradation Tracking: SOH & R0)          |  |
|  | 4. Hard Safety Barrier (Non-Compensatory Catastrophic Cutoff)         |  |
|  | 5. Value of Information (EVSI Quad vs Test Cost Stopping Rule)       |  |
|  +-----------------------------------------------------------------------+  |
|                                       |                                     |
|                                       | Research Decision (OPERATE, DERATE, |
|                                       |                     HOLD, RETIRE)   |
|                                       v                                     |
|  [ LAYER 4: SAFETY & ACTUATION POLICY ]                                     |
|  +-----------------------------------------------------------------------+  |
|  |                         ActuationPolicy                               |  |
|  |   - Maps decisions to abstract intents (ENABLE_LOAD, LIMIT_LOAD...)   |  |
|  |   - Enforces fail-safe overrides: Validation failure -> HOLD/ISOLATE  |  |
|  |   - SystemStateMachine: Enforces legal lifecycle transitions          |  |
|  |   - EventLogger: Structured JSONL audit trail                         |  |
|  +-----------------------------------------------------------------------+  |
|                                       |                                     |
|                                       | Abstract CommandFrame               |
|                                       v                                     |
|  [ LAYER 5: HARDWARE COMMAND ADAPTER ]                                      |
|  +-----------------------------------------------------------------------+  |
|  |                      Hardware Command Dispatch                        |  |
|  |   - Serial NDJSON dispatch to ESP32 microcontroller                   |  |
|  |   - Interlock confirmation & command ACK/NACK parsing                 |  |
|  |   - Independent Hardware Safety Supervisory Monitoring                |  |
|  +-----------------------------------------------------------------------+  |
|                                                                             |
+=============================================================================+
```

---

## 2. Layer-by-Layer Detailed Specification

### Layer 1: Hardware Transport & Adapters (`secondshift/hardware/`)
Layer 1 abstracts physical device communication behind a uniform `HardwareInterface` contract:
- `connect() -> bool`: Initializes serial port or stream resource.
- `disconnect() -> None`: Safely releases serial bus and parks actuators in isolated state.
- `read_telemetry(timeout_s: float) -> Optional[TelemetryFrame]`: Reads and deserializes incoming sensor frame.
- `send_command(command: Dict[str, Any]) -> bool`: Dispatches formatted actuation command frame.
- `get_status() -> Dict[str, Any]`: Returns transport connection health, frame counters, and fault flags.

**Concrete Adapters:**
1. **`MockHardware`**: Emulates low-voltage 4-cell packs with selectable chemistry (LFP, NMC, UNKNOWN), state of health, and internal resistance. Provides controllable fault injection modes (MISSING_SENSOR, STALE_TELEMETRY, COMM_DROPOUT, UVP_FAULT, OVP_FAULT, CURRENT_FAULT).
2. **`SerialHardware`**: Connects via physical UART (115200 baud, 8N1) to an ESP32 microcontroller using Newline-Delimited JSON (NDJSON). Handles partial packet fragmentation, buffering, and timeouts. Supports stream injection for unit test mockability without physical serial ports.
3. **`ReplayHardware`**: Reads pre-recorded field or laboratory telemetry files (`.csv`, `.json`, `.jsonl`), preserving sequence numbers and timestamps. Guarantees 100% deterministic test execution.

---

### Layer 2: Measurement Normalization & Validation (`secondshift/interfaces/`)
Layer 2 is the firewall protecting mathematical algorithms from corrupted or adversarial telemetry.

**Core Invariants:**
1. **Zero Silent Repair:** Corrupt numbers are NEVER replaced with defaults, imputed values, or interpolations.
2. **Strict Physical Boundary Checking:**
   - Module terminal voltage: $1.0\text{ V} \le V_{\text{mod}} \le 60.0\text{ V}$
   - Individual cell voltage: $1.0\text{ V} \le V_{\text{cell}} \le 4.5\text{ V}$
   - String current: $-50.0\text{ A} \le I \le +50.0\text{ A}$
   - Module surface temperature: $-20.0^\circ\text{C} \le T \le +85.0^\circ\text{C}$
3. **Temporal Integrity & Staleness:** Rejects frames where $\text{age} = t_{\text{current}} - t_{\text{frame}} > 2.0\text{ s}$ or where clock skew puts the frame $>5.0\text{ s}$ into the future (unless explicitly configured for recorded replay).
4. **Sequence Tracking:** Detects duplicate frames, sequence regressions ($S_{k} < S_{k-1}$), and dropped frame gaps.

---

### Layer 3: Scientific Research Engine (Hardware-Agnostic Core)
Layer 3 contains the mathematical and decision-theoretic core:
1. **Stage 0 Triage Gate (`TriageGate`):** Evaluates physical and electrochemical feasibility (e.g. TR-03 undervoltage cutoff at 2.0V prevents copper dendrite internal short-circuit hazards).
2. **Chemistry Disambiguation Engine (`ChemistryDisambiguationEngine`):** Computes Bayesian model posterior $P(M \mid \mathbf{z})$ across LFP, NMC, and UNKNOWN, evaluating confidence state (KNOWN, PROBABLE, AMBIGUOUS).
3. **Bayesian State Estimator (`BayesianStateEstimator`):** Tracks joint degradation belief $(\mu_{\text{SOH}}, \sigma^2_{\text{SOH}}, \mu_{R0}, \sigma^2_{R0})$ using recursive Kalman updates.
4. **Hard Safety Barrier (`HardSafetyBarrier`):** Decoupled safety barrier evaluating marginal probability of failure:
   $$P(\text{Failure} \mid \mathbf{z}) = \sum_{M} P(\text{Failure} \mid \mathbf{z}, M) P(M \mid \mathbf{z}) \le 1.0\%$$
5. **Value of Information Engine (`ValueOfInformationEngine`):** Evaluates Expected Value of Sample Information (EVSI) against test cost $C_{\text{test}}$, stopping testing when EVSI $\le 0$.

---

### Layer 4: Actuation Policy & State Machine (`secondshift/safety/`)
Translates research outputs (`OPERATE`, `DERATE`, `HOLD`, `RETIRE`) into abstract physical actuator intents (`ENABLE_LOAD`, `LIMIT_LOAD`, `ISOLATE`, `KEEP_ISOLATED`).

**Fail-Safe Invariants:**
- If telemetry is missing, stale, contains NaN/Inf, or reports a sensor fault, the policy **FORBIDS** `ENABLE_LOAD` and defaults immediately to `KEEP_ISOLATED` (HOLD) or `ISOLATE` (EMERGENCY_ISOLATE).
- An 11-state Finite State Machine (`SystemStateMachine`) prevents illegal state hops (e.g., direct transition from FAULT or DISCONNECTED to OPERATE is architecturally impossible).
- An emergency latch requires explicit manual operator clearing following an analog comparator or watchdog trip.

---

### Layer 5: Hardware Command Adapter (`secondshift/interfaces/command_schema.py`)
Encapsulates abstract command frames into JSON payloads dispatched over serial transport to the physical controller.
- Prevents supervisory research software from setting GPIO pin numbers or raw PWM registers directly.
- Microcontroller firmware validates commanded current limits against independent analog hardware interlocks before energizing power contactors.

---

## 3. Strict Boundary Guarantees

| Boundary Requirement | Implementation Mechanism | Verification Test |
| :--- | :--- | :--- |
| **Epistemic Blind Separation** | Production modules never import or reference `ground_truth_registry.json`. | `test_ast_ground_truth_isolation`, `test_runtime_ground_truth_interception` |
| **Zero Direct Hardware Sniffing** | Pipeline reads only normalized `TelemetryFrame` structures; cannot read private hardware attributes. | `test_no_direct_hardware_attribute_sniffing` |
| **Production Path Determinism** | Zero calls to pseudo-random number generators in Layers 1–5. | `DETERMINISM_AUDIT.md`, `test_hil_pipeline_replay_determinism` |
| **Fail-Safe Integrity** | Telemetry or communication errors immediately isolate load contactors. | `test_actuation_policy_translation_and_failsafe`, `test_hil_pipeline_failsafe_hold_on_sensor_fault` |
