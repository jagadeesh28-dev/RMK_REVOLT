# Explainable Battery Qualification Console & Dashboard Architecture

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/DASHBOARD_ARCHITECTURE.md`  
**Phase**: Phase 3 — Qualification Data Model + Dashboard Integration  
**Status**: AUDITED & SCIENTIFICALLY FROZEN (Phase 3 Final Acceptance)  

---

## 1. Architectural Role & Design Principles

The SECONDShift Dashboard (`secondshift/software/ui/dashboard.py`) is an industrial test-station console that transforms raw sensor monitoring into an **Explainable Battery Qualification Console**.

### Non-Negotiable Invariants:
1. **Zero Control Feedback**: The dashboard is strictly read-only (`observability only`). It never executes actuation commands, never modifies state machines, and cannot influence physical testing.
2. **Safety Loop Independence**: The physical safety barrier (`HardSafetyBarrier`) and telemetry supervisor execute completely decoupled from the UI. A crash, freeze, or disconnection of the web browser or HTTP server does NOT affect hardware safety.
3. **No Fake Intelligence**: The UI never presents placeholder numbers (such as `0%`, `100%`, or fabricated ML confidences) as scientific truth. Unavailable modules (e.g. RUL prognostics) are explicitly labeled:
   $$\text{RUL: NOT YET IMPLEMENTED}$$
4. **Declared vs. Inferred Separation**: Intake specimen chemistry is kept strictly isolated from model beliefs.
5. **Decoupled Operational vs. Information Decisions**: Operational commitments (`OPERATE`, `DERATE`, `HOLD`, `RETIRE`) are visually and semantically distinct from diagnostic acquisition (`NO_TEST`, `REQUEST_TEST`).

---

## 2. End-to-End Data Pipeline

```
  PHYSICAL HARDWARE / SIMULATOR
                │  (Telemetry frames via Serial / Mock / Replay)
                ▼
      HardSafetyBarrier (Authoritative trip check)
                │
                ▼
     TelemetryValidator & EventLogger (Layer 1 & 2 Admissibility)
                │
                ▼
     HILRunner / ClosedLoopRunner (Bayesian estimation & stopping logic)
                │
                ▼
     QualificationSession & DecisionAuditRecord (Phase 3 Canonical Records)
                │
                ▼
  Canonical Status Adapter (secondshift/software/ui/status_adapter.py)
                │  - Explicit allow-list filtering
                │  - Ground-truth key isolation (defense-in-depth)
                │  - Atomic write to last_run_status.json
                ▼
      Dashboard HTTP Server (/api/status & /api/benchmarks)
                │  (Zero-dependency stdlib http.server)
                ▼
    Industrial HMI Console (Vanilla HTML5 / CSS / SVG / JS)
```

---

## 3. Console Sections (Sections A through K)

The console is organized into authoritative, evidence-driven panels:

### Top Verdict Row
Displays four primary status cards:
1. **SAFETY BARRIER**: `CLEAR` / `BLOCKED` / `TRIP` (authoritative override state).
2. **OPERATIONAL DECISION**: `OPERATE` / `DERATE` / `HOLD` / `RETIRE`.
3. **INFORMATION ACTION**: `NO_TEST` / `REQUEST_TEST` (diagnostic recommendations).
4. **EPISTEMIC STATE**: `SUPPORTED_HEALTHY`, `UNCERTAIN`, `DISTRIBUTION_SHIFTED`, `KNOWN_DEGRADED`, or `INSUFFICIENT_DATA`.

### Decision Explanation & Scientific Evidence Banner
Synthesizes a human-readable explanation of why the current decision was reached, displaying active `ReasonCode` pills (e.g. `CURRENT_FLOW_BELOW_MINIMUM`, `ADDITIONAL_TEST_VALUE_HIGH`).

### Live Telemetry Tiles
Displays active measurements with unit tags and Layer 1 validity chips:
- **VOLTAGE**: Measured cell terminal potential in Volts ($V$).
- **CURRENT**: Active current in Amperes ($A$).
- **POWER**: Active electrical power in Watts ($W = V \times I$), or `N/A` if invalid.
- **TEMPERATURE**: Cell surface temperature in degrees Celsius ($^\circ\text{C}$).

---

### Section A — Battery Specimen & Protocol
Presents the identity of the physical specimen under test:
- Battery ID & Cell ID.
- Declared Chemistry (intake metadata).
- Nominal Voltage & Capacity rating.
- Specimen Source & Intake Lot.
- Active Protocol ID, Software Version, and Configuration Version.

### Section C — Data Quality & Measurement Admissibility
Provides granular visibility into why measurements are accepted or rejected:
- Sensor Validity (`VALID` / `INVALID`).
- Telemetry Frame Validity (`VALID` / `INVALID`).
- Event Validity & Sequence continuity.
- Inference Admissibility (`ADMISSIBLE` / `INADMISSIBLE`).
- Current Flow Status (`VALID` / `INVALID (BELOW MINIMUM)`).
- Diagnostic Pulse Validity (`VALID` / `INVALID`).
- Transient Voltage Responses ($\Delta V_{\text{total}}$, $\Delta V_{\text{ohmic}}$), or `N/A` if invalid.
- Admissibility Reason Codes.

### Section D — Test Progress & Segments
Tracks physical execution on the test station:
- Session ID & Lifecycle Status (`CREATED`, `RUNNING`, `COMPLETED`, `SAFE_STOP`).
- Current Segment Type (`CHARGE`, `REST`, `DISCHARGE`, `PULSE`, `HOLD`).
- Segment Validation Status & Aggregate Dataset Status (`VALID`, `PARTIALLY_VALID`, `INVALID`).
- Elapsed Qualification Duration (s).
- Next Expected Action.

### Section E — Chemistry Identification
Distinguishes intake metadata from electrochemical inference:
- Declared Chemistry.
- Inferred Chemistry (or `NOT YET ESTIMATED`).
- Confidence State (`KNOWN`, `AMBIGUOUS`, `UNKNOWN`, `NOT_YET_ESTIMATED`).
- Confidence Score & Posterior Belief Distribution (e.g. `LFP: 96% | NMC: 4%`).

### Section F & G — State Estimation & Prognostics
- State of Health (SOH) estimate $\mu_{\text{SOH}}$ with uncertainty band $\pm \sigma_{\text{SOH}}$.
- High-frequency internal resistance $R_0$ in $\text{m}\Omega$, or `NOT AVAILABLE` if pulse was rejected.
- Remaining Useful Life (RUL): `NOT YET IMPLEMENTED` (Phase 3 placeholder).
- RUL Uncertainty: `NOT YET IMPLEMENTED`.
- Graphical progress tracks for SOH and Marginal Failure Risk.

### Section H, I, J — Adaptive Decision Engine
- Sequential Decision Stages: Triage $\rightarrow$ Uncertainty $\rightarrow$ Bayesian $\rightarrow$ Safety $\rightarrow$ Decision.
- Operational Decision (`OPERATE` / `DERATE` / `HOLD` / `RETIRE`).
- Information Action (`NO_TEST` / `REQUEST_TEST`).
- Actuation Intent (Requested vs Confirmed).
- Marginal Failure Risk (%).

### Section K — Hard Safety Barrier
Authoritative safety supervisor status:
- Hardware Trip Status (`NO (CLEARED)` vs `YES (TRIPPED)`).
- Sensor Fault Indicator.
- Safe Stop Engagement.
- Active Trip Reason.
- Operating Envelope Thresholds (Voltage limits $2.00\,\text{V} - 3.75\,\text{V}$, Current limits $\pm 50\,\text{A}$, Max temperature $45^\circ\text{C}$).
- Active Supervisory Interlocks.

---

## 4. Workspaces & Visualization

The console provides four top-level navigation workspaces:
1. **CONSOLE (`overview`)**: The live, explainable qualification dashboard detailed above.
2. **TEST GRAPH (`trend`)**: Graphical SVG curves plotting Decision Iterations for Voltage, Current, Power, Temperature, Marginal Risk, SOH, and $R_0$.
3. **DECISION TRACE (`trace`)**: Complete chronological audit trail showing each stage iteration, state estimate, risk, and reason code.
4. **BENCHMARKS (`bench`)**: Read-only display of historical recorded scenarios E01–E14, clearly badged as historical recorded benchmarks (never live physical validation).

---

## 5. Offline Operation & Hardware Modes

The dashboard operates identically under three hardware modes:
- **`MOCK`**: Simulated software battery models.
- **`REPLAY`**: Recorded physical telemetry feeds replayed through the validator.
- **`SERIAL`**: Live bidirectional communication with physical ESP32 / load bench.

No live hardware is required to develop, test, or demonstrate the console.
