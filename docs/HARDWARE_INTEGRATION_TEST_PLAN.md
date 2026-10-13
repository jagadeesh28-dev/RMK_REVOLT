# NEXUS — Hardware Integration Test Plan (Phases W0 – W8)

## 1. Overview & Verification Scope

This test plan defines the formal test suite, fault injection procedures, and acceptance criteria for the Wi-Fi hardware integration of the NEXUS / RMK REVOLT battery qualification bench.

Testing proceeds strictly through gated phases:
- **Phase W0**: Repository Audit & Interface Compliance
- **Phase W1**: Wi-Fi Connection & Credential Privacy
- **Phase W2**: Telemetry Ingestion & Monotonic Sequences
- **Phase W3**: Backend Validation & Rejection Engine
- **Phase W4**: Frontend Real-time Reflection & Heartbeat State Machine
- **Phase W5**: Physical Sensor Validation & Range Feasibility
- **Phase W6**: Load Switching & Actuation Safety Barrier
- **Phase W7**: NEXUS Software Shadow Mode Integration
- **Phase W8**: Replay Determinism & HIL Runner Interoperability

---

## 2. Test Execution Matrix

| Test ID | Phase | Objective | Test Procedure / Input | Expected Result | Pass Criteria |
|---|:---:|---|---|---|:---:|
| `T_W0_01` | W0 | Schema compliance | Construct canonical `TelemetryFrame` from packet dict | Correct attributes populated; physical types preserved | `PASS` |
| `T_W1_01` | W1 | Credential protection | Inspect snapshots & serialized dictionaries | No `password`, `wifi_password`, `secret` leaked in snapshots | `PASS` |
| `T_W1_02` | W1 | `.gitignore` enforcement | Audit `.gitignore` for `secrets.h` and `.env` | File patterns present in `.gitignore` | `PASS` |
| `T_W2_01` | W2 | Ingestion of valid packet | Submit valid NDJSON frame to `TelemetryIngestEngine` | Accepted (`200 OK`), stats counter increments | `PASS` |
| `T_W2_02` | W2 | Sequence incrementing | Ingest 5 consecutive packets with sequence $100 \dots 104$ | All 5 accepted; zero sequence gaps reported | `PASS` |
| `T_W3_01` | W3 | Device whitelist validation | Submit packet from unregistered device `"ROGUE-99"` | Rejection with `UNAUTHORIZED_DEVICE` | `PASS` |
| `T_W3_02` | W3 | Missing mandatory field | Submit packet lacking `sequence` field | Rejection with `INVALID_SEQUENCE_FIELD` | `PASS` |
| `T_W3_03` | W3 | NaN / Infinity rejection | Submit packets with `voltage_v: NaN` and `current_a: Inf` | Rejection with `VALIDATION_FAILED` | `PASS` |
| `T_W3_04` | W3 | Sequence gap detection | Submit sequence 10 followed immediately by sequence 15 | Accepted; `sequence_gaps = 4` recorded | `PASS` |
| `T_W3_05` | W3 | Duplicate sequence rejection | Submit duplicate sequence 50 twice | Second packet rejected as `DUPLICATE_PACKET` | `PASS` |
| `T_W3_06` | W3 | Physical range violation | Submit $V = -1.5\,\text{V}$, $I = 150\,\text{A}$, $T = 115^\circ\text{C}$ | All rejected by physical bounds validator | `PASS` |
| `T_W3_07` | W3 | None != 0 preservation | Submit frame with optional `power_w` omitted | Raw history preserves missingness; zero not substituted | `PASS` |
| `T_W4_01` | W4 | Heartbeat timeouts | Ingest frame, wait $1.1\,\text{s}$, then wait additional $1.5\,\text{s}$ | State transitions `CONNECTED` $\to$ `STALE` $\to$ `DISCONNECTED` | `PASS` |
| `T_W4_02` | W4 | Hardware fault latching | Ingest frame with `hardware_fault: true` | State transitions to `FAULT` | `PASS` |
| `T_W4_03` | W4 | Status snapshot format | Generate status snapshot via `build_live_telemetry_snapshot` | Conforms to UI schema with `available: true`, `nexus_hardware` | `PASS` |
| `T_W5_01` | W5 | Sensor validity flag | Submit packet with `sensor_valid: false` | Rejected by validator; sensor fault error logged | `PASS` |
| `T_W6_01` | W6 | Command queueing | Queue `HOLD` followed by priority `STOP` | Priority `STOP` preempts queue; directive issued | `PASS` |
| `T_W6_02` | W6 | Unsafe command rejection | Submit arbitrary action `"SET_PIN_25_HIGH"` | `ValueError` raised; arbitrary GPIO blocked | `PASS` |
| `T_W7_01` | W7 | Shadow mode evaluation | Ingest valid frame; run `evaluate_shadow_decision` | Epistemic state (`UNCERTAIN`), Decision (`HOLD`), zero actuation | `PASS` |
| `T_W8_01` | W8 | Hardware adapter contract | Connect `WifiHardware`, read telemetry, dispatch command | Implements `HardwareInterface`; zero crashes | `PASS` |
| `T_W8_02` | W8 | Historical NDJSON replay | Replay `esp32_wifi_prototype_run_001.ndjson` via CLI | 15/15 frames validated; qualification decision reproduced | `PASS` |

---

## 3. Network Failure & Recovery Procedure

1. **Baseline**: Start bench and backend server; establish `CONNECTED` status.
2. **Wi-Fi Loss**: Deactivate Wi-Fi access point or disconnect bench network interface.
   - *ESP32 Verification*: Local supervisor FSM continues sampling at $10\,\text{Hz}$; if load is active, autonomous cutoff triggers if voltage or current limits are breached.
   - *Backend Verification*: After $3.0\,\text{s}$, backend flags `STALE`. After $10.0\,\text{s}$, backend logs `WIFI_DISCONNECT` and flags `DISCONNECTED`.
   - *Frontend Verification*: Dashboard renders amber `STALE DATA` badge with age, then updates to `DISCONNECTED`.
3. **Wi-Fi Restoration**: Re-enable Wi-Fi access point.
   - *ESP32 Verification*: Embedded FSM detects link availability and transitions `WIFI_STATE_RECONNECTING` $\to$ `WIFI_STATE_CONNECTED`.
   - *Backend Verification*: Ingestion engine logs `WIFI_RESTORED` event with packet gap count and first recovered sequence number.
   - *Frontend Verification*: Dashboard returns to green `LIVE` connection badge.

---

## 4. Replay & Regression Verification

Every physical bench test session must be serialized as a timestamped NDJSON replay artifact (e.g. `esp32_wifi_prototype_run_001.ndjson`).

The automated test runner must execute:
```bash
python -m pytest secondshift/tests/test_wifi_telemetry_integration.py -v
```
All tests must pass unconditionally before enabling controlled physical actuation.
