# NEXUS ESP32 — Fault Recovery State-Machine Validation Report

**Project**: RMK REVOLT / SECONDShift Platform  
**System**: NEXUS — Risk-Constrained Adaptive Second-Life EV Battery Qualification System  
**Roles**: Senior Embedded Systems Engineer, Firmware Validation Engineer, Functional Safety Engineer, Hardware Integration Engineer  
**Date**: October 8, 2026  
**Status**: `FAULT_RECOVERY_SOFTWARE_VERIFIED`  

---

## 1. Observed Defect

### Defect Description
When the physical battery testbed firmware in `ESP32_CODE/sketch_oct5a/sketch_oct5a.ino` entered `STATE_FAULT` while operating in `STATE_IDLE` (due to an electrical transient or temporary sensor disturbance), and that physical fault condition subsequently cleared (e.g., cell voltage relaxed back into nominal range, current dropped to zero, or temperature dissipated), the firmware remained permanently locked in `STATE_FAULT` rather than recovering to `STATE_IDLE`.

### Reproduction Sequence
```text
STATE_IDLE (MOSFET OFF)
       │
       ▼  (Transient condition: e.g. momentary voltage sag < 6.40 V)
STATE_FAULT (MOSFET forced OFF)
       │
       ▼  (Transient clears: voltage recovers to nominal 7.40 V)
EXPECTED: Automatic qualification -> STATE_IDLE (MOSFET remains OFF)
ACTUAL (Old Code): Permanently locked in STATE_FAULT
```

---

## 2. Root Cause Analysis

Inspection of `ESP32_CODE/sketch_oct5a/sketch_oct5a.ino` revealed three root architectural causes:
1. **Absence of Recovery Logic in `checkSafety()`**: The safety supervisor function `checkSafety()` was designed purely as a trip generator. When sensors read healthy values, it reset trip debounce counters to zero, but provided zero transition logic to evaluate recovery out of `STATE_FAULT`.
2. **Absence of FAULT Evaluation in Main `loop()`**: Inside `loop()`, state execution handlers existed for `systemState == STATE_RUNNING` and `systemState == STATE_COOLDOWN`, but no branch existed for `systemState == STATE_FAULT`.
3. **Manual-Only Clearance Path**: The only transition out of `STATE_FAULT` was the `clearFault()` function, which required an explicit external ASCII command string (`"CLEAR"`) sent over USB Serial or via a JSON supervisory action from the backend. When operating autonomously, the firmware could never recover from a transient condition without operator intervention.

---

## 3. Existing State Machine (Legacy)

### Legacy States
- `STATE_IDLE`
- `STATE_RUNNING`
- `STATE_COOLDOWN`
- `STATE_FAULT`

### Legacy Transition Topology
```text
  ┌──────────────┐   "ON" / "AUTO"    ┌───────────────┐
  │  STATE_IDLE  │ ─────────────────> │ STATE_RUNNING │
  └──────────────┘                    └───────┬───────┘
         ▲                                    │ (LOAD_ON_TIME_MS: 5s)
         │                                    ▼
         │      "OFF" / "STOP"        ┌────────────────┐
         ├─────────────────────────── │ STATE_COOLDOWN │
         │                            └───────┬────────┘
         │                                    │ (LOAD_OFF_TIME_MS: 3s)
         │                                    ▼
         │                            ┌───────────────┐
         │                            │ STATE_RUNNING │
         │                            └───────────────┘
         │
         │ manual "CLEAR" only
         │
  ┌──────┴───────┐   trip thresholds breached (UV, OV, OC, OT, SENSOR)
  │ STATE_FAULT  │ <──────────────────────────────────────────────────
  └──────────────┘
```
**Defect**: No edge existed from `STATE_FAULT` to `STATE_IDLE` without an external manual `"CLEAR"` command.

---

## 4. Corrected State Machine (New)

### Safe Recovery Topology
```text
                ┌──────────────┐
                │  STATE_IDLE  │
                └──────┬───────┘
                       │
                 fault detected (trip debounce N=3)
                       │
                       ▼
                ┌──────────────┐
                │ STATE_FAULT  │ ◄──────────────────┐
                └──────┬───────┘                    │
                       │                            │
             ┌─────────┴─────────┐                  │
             │                   │                  │
       latched fault    recoverable fault           │
             │                   │                  │
             ▼                   ▼                  │
        MANUAL CLEAR     checkFaultRecovery()       │
          REQUIRED               │                  │
                                 ▼                  │
                         Physical healthy?          │
                       (Hysteresis verified)        │
                                 │                  │
                        NO ──────┴────── YES        │
                        │                 │         │
                        ▼                 ▼         │
                   reset count    recoveryCount++   │
                        │                 │         │
                        │           count >= 5?     │
                        │            │         │    │
                        │           NO        YES   │
                        │            │         │    │
                        └────────────┘         ▼    │
                                          ┌─────────┴────────┐
                                          │ Transition: IDLE │
                                          │ MOSFET = OFF     │
                                          │ Preserve History │
                                          └──────────────────┘
```

---

## 5. Fault Classification Taxonomy

The system explicitly distinguishes between **Recoverable Faults** (which may safely qualify for auto-recovery) and **Latched Faults** (which require physical repair, reboot, or manual clearance):

| Fault Reason | Class | Description | Recovery Policy |
| :--- | :--- | :--- | :--- |
| `UNDER_VOLTAGE` | **RECOVERABLE** | Transient pack sag during load activation or resting bounce | Auto-recover when $V \ge 6.55\,\text{V}$ for 5 consecutive samples |
| `OVER_VOLTAGE` | **RECOVERABLE** | Transient inductive bounce or regenerative spike | Auto-recover when $V \le 8.35\,\text{V}$ for 5 consecutive samples |
| `OVER_CURRENT` | **RECOVERABLE** | Inrush surge or load excursion de-energized by cutoff | Auto-recover when $\|I\| \le 0.10\,\text{A}$ for 5 consecutive samples |
| `OVER_TEMPERATURE` | **RECOVERABLE** | Thermal buildup dissipated during dwell | Auto-recover when $T \le 55.0^\circ\text{C}$ for 5 consecutive samples |
| `SENSOR_INVALID` | **RECOVERABLE** | Transient I2C noise or single 1-Wire CRC glitch | Auto-recover when sensors valid for 5 consecutive samples |
| `INA219_NOT_DETECTED` | **LATCHED** | I2C sensor hardware missing at boot | Requires hardware inspection / reboot |
| `DS18B20_NOT_DETECTED` | **LATCHED** | 1-Wire sensor hardware missing at boot | Requires hardware inspection / reboot |
| `HARDWARE_TRIP_LATCHED` | **LATCHED** | External hardware comparator or blown fuse trip | Requires operator inspection |
| `EMERGENCY_STOP` | **LATCHED** | Operator emergency stop | Requires deliberate manual recovery |
| *Unknown / Unclassified* | **LATCHED** | Any unclassified fault reason | Fail-safe default: remain latched |

---

## 6. Recovery Qualification Criteria

To prevent chattering and oscillations between `FAULT` and `IDLE`, recovery requires meeting strict hysteresis boundaries across $N = 5$ consecutive valid samples ($5\,\text{s}$ stable dwell time at $1\,\text{Hz}$):

### Hysteresis Thresholds
- **Under-Voltage**:
  - Trip Threshold: $< 6.40\,\text{V}$ (confirmed over 3 samples)
  - Recovery Threshold: $\ge 6.55\,\text{V}$ ($+150\,\text{mV}$ hysteresis)
- **Over-Voltage**:
  - Trip Threshold: $> 8.50\,\text{V}$ (confirmed over 3 samples)
  - Recovery Threshold: $\le 8.35\,\text{V}$ ($-150\,\text{mV}$ hysteresis)
- **Over-Temperature**:
  - Trip Threshold: $\ge 60.0^\circ\text{C}$ (confirmed over 3 samples)
  - Recovery Threshold: $\le 55.0^\circ\text{C}$ ($-5.0^\circ\text{C}$ hysteresis)
- **Over-Current**:
  - Trip Threshold: $> 2.50\,\text{A}$ (confirmed over 3 samples)
  - Recovery Threshold: $\le 0.10\,\text{A}$ (MOSFET confirmed de-energized)
- **Dwell Time**:
  - `RECOVERY_CONFIRM_COUNT = 5` samples at $1000\,\text{ms}$ interval = $5000\,\text{ms}$ continuous health verification.

---

## 7. Firmware Code Changes

Modified file: `ESP32_CODE/sketch_oct5a/sketch_oct5a.ino`

1. **Recovery Constants Added**:
   ```cpp
   const float BATTERY_UNDERVOLTAGE_RECOVERY = 6.55;
   const float BATTERY_OVERVOLTAGE_RECOVERY  = 8.35;
   const float MAX_TEMPERATURE_RECOVERY_C    = 55.0;
   const float MAX_CURRENT_RECOVERY_A        = 0.10;
   const int   RECOVERY_CONFIRM_COUNT        = 5;
   ```
2. **Audit Variables Added**:
   ```cpp
   String faultReason = "NONE";
   String lastFaultReason = "NONE";
   bool faultRecovered = false;
   unsigned long faultEntryTime = 0;
   unsigned long faultClearTime = 0;
   int recoverySampleCount = 0;
   ```
3. **Execution Branch in `loop()`**:
   ```cpp
   if (systemState != STATE_FAULT) {
     checkSafety();
   } else {
     checkFaultRecovery();
   }
   ```
4. **Continuous Fail-Safe in `loop()`**:
   ```cpp
   else if (systemState == STATE_FAULT) {
     if (mosfetState) {
       setMOSFET(false);
     }
   }
   ```
5. **Deterministic Functions Implemented**:
   - `bool isFaultRecoverable(const String &reason);`
   - `bool isPhysicalConditionHealthy();`
   - `void checkFaultRecovery();`
6. **Hardened `clearFault()`**:
   - Reject manual clear if `!isPhysicalConditionHealthy()`.
7. **Canonical NDJSON Telemetry Enriched**:
   - `last_fault`, `fault_recovered`, `recovery_count`, `fault_entry_ms`, `fault_clear_ms`.

---

## 8. Unit & Simulation Verification (TEST-FR-01 through TEST-FR-15)

Implemented in `secondshift/tests/test_fault_recovery.py`:

| Test ID | Scenario | Expected Behavior | Result |
| :--- | :--- | :--- | :--- |
| `TEST-FR-01` | Healthy IDLE | Remains in IDLE; MOSFET remains OFF | **PASS** |
| `TEST-FR-02` | Valid fault detected | Debounced trip enters FAULT; MOSFET forced OFF | **PASS** |
| `TEST-FR-03` | Fault condition persists | System remains in FAULT indefinitely | **PASS** |
| `TEST-FR-04` | Fault condition clears | Requires 5 valid samples; safely transitions FAULT -> IDLE | **PASS** |
| `TEST-FR-05` | Single good sample | Does NOT prematurely exit FAULT | **PASS** |
| `TEST-FR-06` | Fault returns during dwell | Recovery counter immediately resets to 0; remains in FAULT | **PASS** |
| `TEST-FR-07` | Recovery invariant | FAULT -> IDLE enforces `mosfet_state == false` | **PASS** |
| `TEST-FR-08` | CLEAR on active fault | Manual CLEAR rejected while physical condition persists | **PASS** |
| `TEST-FR-09` | Latched fault | Hardware detection faults never auto-recover | **PASS** |
| `TEST-FR-10` | Recoverable fault taxonomy | All 5 recoverable fault types recover upon qualification | **PASS** |
| `TEST-FR-11` | Sensor invalidity | `sensor_valid == false` prevents recovery qualification | **PASS** |
| `TEST-FR-12` | Multiple concurrent faults | Recovery blocked if any single condition remains breached | **PASS** |
| `TEST-FR-13` | Fault auditability | `last_fault_reason` and `fault_recovered` retained in IDLE | **PASS** |
| `TEST-FR-14` | Audit logging | State transitions and recovery events logged to ledger | **PASS** |
| `TEST-FR-15` | Repeated cycles | 5 consecutive trip/recovery cycles execute deterministically | **PASS** |

---

## 9. Hardware Verification Procedure

When testing on physical ESP32 bench:
1. **Low-Energy Test**:
   - Boot ESP32 with 2S battery pack ($7.40\,\text{V}$). Verify `STATE_IDLE`, `MOSFET = OFF`.
2. **Controlled Fault Injection**:
   - Temporarily adjust programmable bench power supply or potentiometer below $6.40\,\text{V}$ (e.g. $6.20\,\text{V}$).
   - Observe serial log: after 3 cycles ($3\,\text{s}$), firmware transitions `IDLE -> FAULT` with reason `"UNDER_VOLTAGE"`. Verify GPIO 25 reads $0.0\,\text{V}$ (MOSFET OFF).
3. **Controlled Recovery**:
   - Restore voltage to $7.40\,\text{V}$.
   - Observe serial log: consecutive healthy sample counter counts $1/5 \to 2/5 \to 3/5 \to 4/5 \to 5/5$.
   - On sample 5, firmware transitions `FAULT -> IDLE`.
   - Verify GPIO 25 remains $0.0\,\text{V}$ (MOSFET strictly OFF).

---

## 10. Wi-Fi Telemetry & Backend Integration

Validated in `secondshift/tests/test_wifi_telemetry_integration.py::test_w9_fault_recovery_telemetry_flow`:
1. **IDLE Ingestion**:
   - Transmits packet with `state: "IDLE"`, `fault: "NONE"`.
   - Backend ingests packet (`accepted: True`); snapshot displays `telemetry_state: "LIVE"`, `hardware_state: "IDLE"`, `hardware_fault: False`.
2. **FAULT Ingestion**:
   - Transmits packet with `state: "FAULT"`, `fault: "UNDER_VOLTAGE"`.
   - Backend isolates frame from SOH/RUL inference (`accepted: False`, `hardware_fault: True`).
   - Snapshot displays `hardware_state: "FAULT"`, `is_fault: True`, `fault_reason: "UNDER_VOLTAGE"`.
3. **RECOVERY Ingestion**:
   - After 5 healthy frames, ESP32 transmits `state: "IDLE"`, `fault: "NONE"`, `last_fault: "UNDER_VOLTAGE"`, `fault_recovered: True`.
   - Backend marks connection `LIVE`, `is_fault: False`, `hardware_state: "IDLE"`, `hardware_fault: False`.
   - Audit trail in `raw_history` preserves forensic record of prior fault.

---

## 11. Frontend Behavior

The dashboard live status component (`secondshift/software/ui/status_adapter.py`) receives live snapshots via HTTP `/api/telemetry/live`:
- **In Normal IDLE**: Green status badge: `SYSTEM IDLE — NOMINAL`.
- **In Active FAULT**: Red blinking badge: `FAULT: UNDER_VOLTAGE — MOSFET ISOLATED`.
- **Upon Safe Recovery**: Amber transition badge resolving to Green: `IDLE — RECOVERED (PRIOR: UNDER_VOLTAGE)`.
- **Safety Preemption**: Actuation buttons (`ON`, `AUTO`) remain locked during `FAULT` and require manual operator dispatch to start a new test even after recovery.

---

## 12. Safety Invariant Verification

**CRITICAL SAFETY PROPERTY**: Fault recovery MUST NOT automatically turn the load ON.
- Verified across all unit and simulation tests:
  $$\forall t \in \text{Recovery}, \quad \text{mosfetState}(t) = \text{OFF}$$
  $$\text{state}(t_{\text{recovered}}) = \text{STATE\_IDLE} \implies \text{mosfetState}(t_{\text{recovered}}) = \text{OFF}$$
- Transition to `STATE_RUNNING` requires an explicit subsequent `ON` or `AUTO` command.
- Active faults prevent recovery and reject manual `CLEAR`.

---

## 13. Permanent Regression Test

Implemented as `test_regression_idle_fault_disappears_recovers_to_idle_mosfet_off`:
```python
def test_regression_idle_fault_disappears_recovers_to_idle_mosfet_off(fsm):
    # START: IDLE
    assert fsm.system_state == SystemState.STATE_IDLE
    assert fsm.mosfet_state is False

    # ACTION: Trigger recoverable over-current fault
    fsm.step(voltage=7.40, current=3.00, temp=25.0, sensor_valid=True, now_ms=1000)
    fsm.step(voltage=7.40, current=3.00, temp=25.0, sensor_valid=True, now_ms=2000)
    fsm.step(voltage=7.40, current=3.00, temp=25.0, sensor_valid=True, now_ms=3000)
    assert fsm.system_state == SystemState.STATE_FAULT

    # ACTION: Remove fault condition (current drops to 0.0A)
    for i in range(1, 5):
        fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=3000 + i * 1000)
        assert fsm.system_state == SystemState.STATE_FAULT

    fsm.step(voltage=7.40, current=0.0, temp=25.0, sensor_valid=True, now_ms=8000)

    # ASSERT: state == IDLE, MOSFET == OFF, fault history preserved
    assert fsm.system_state == SystemState.STATE_IDLE
    assert fsm.mosfet_state is False
    assert fsm.last_fault_reason == "OVER_CURRENT"
    assert fsm.fault_recovered is True
```
**Outcome**: Passed in test run ($16 / 16$ suite tests passed).

---

## 14. Evidence & Log References
- Firmware Source: [sketch_oct5a.ino](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/ESP32_CODE/sketch_oct5a/sketch_oct5a.ino)
- Python Simulator: [fault_recovery_fsm.py](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/hardware/fault_recovery_fsm.py)
- Unit & Regression Test Suite: [test_fault_recovery.py](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/tests/test_fault_recovery.py)
- Wi-Fi Integration Test Suite: [test_wifi_telemetry_integration.py](file:///c:/Users/JAGADEESH%20M/OneDrive/Documents/RMK_REVOLT/secondshift/tests/test_wifi_telemetry_integration.py)
- Test Run Output: `266 passed in 6.25s` across workspace.

---

## 15. Known Limitations
1. **Boot Sensor Absence**: `INA219_NOT_DETECTED` and `DS18B20_NOT_DETECTED` require hardware physical power cycling or manual command `"CLEAR"` after physical sensor wiring is reconnected.
2. **Current Shunt Range**: Shunt calibration in INA219 is configured for $\pm 3.2\,\text{A}$ ($32\,\text{V}, 2\,\text{A}$ range). Fault threshold of $2.50\,\text{A}$ must be recalibrated if shunts are altered for higher-current battery packs.
3. **No SOH Invalidation on Transient Recovery**: Second-life machine learning prognostic models treat transient recoverable faults as non-admissible inference windows, resuming feature extraction only after stable nominal operation is restored.

---

## Final Status Gate

```text
============================================================
FINAL READINESS GATE:
FAULT_RECOVERY_SOFTWARE_VERIFIED
============================================================
```
