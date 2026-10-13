# NEXUS Hardware Telemetry & Network Integration Architecture

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/HARDWARE_TELEMETRY_INTEGRATION.md`  
**Classification**: Embedded Systems & Telemetry Engineering Architecture  

---

## 1. System Pipeline Overview

```
 [PHYSICAL SENSORS]
 INA219 (I2C: 0x40)  --> Voltage / Current
 DS18B20 (1-Wire: D4) --> Temperature
         |
         v
 [ESP32 FIRMWARE]
 Autonomous Protection Loop (100 Hz local check)
 Telemetry Transmission Engine (HTTP POST via Wi-Fi)
         |
         v (Wi-Fi 802.11 b/g/n, HTTP POST /api/telemetry)
 [BACKEND INGESTION ENGINE]
 TelemetryIngestionEngine
   - Device Authorization & Token Scrubbing
   - Sequence Continuity & Monotonicity Check
   - TelemetryValidator (Bounds, NaN/Inf, Physics)
   - Rolling Physical History Buffer (maxlen=300)
   - Shadow-Mode NEXUS Inference (Epistemic & Action)
         |
         v
 [STATUS ADAPTER]
 status_adapter.build_live_telemetry_snapshot()
   - Classifies Class A (Live), Class B (Derived), Class C (Historical)
   - Exposes Graph Data Contract series (v, i, p, t, risk, soh, r0)
   - Enforces Physical Zero vs. Missing None
         |
         v (SSE /api/telemetry/stream & GET /api/status)
 [INDUSTRIAL FRONTEND CONSOLE]
 dashboard.py (HTML5 / SVG / CSS3 / ES6)
   - Real-time SVG polyline charting of true points (no interpolation)
   - Explicit structured empty-states for unexecuted qualifications
   - Dedicated historical reference panel for Phase 5/6.1.1 baseline
```

---

## 2. Networking & Subnet Architecture

- **Host Network Architecture**:
  - The laptop runs the Windows Mobile Hotspot adapter (`SYNQRA_HOST`), binding to IP `192.168.137.1` on port `8088`.
  - The ESP32 connects to `SYNQRA_HOST` and obtains a DHCP lease on `192.168.137.0/24` (e.g. `192.168.137.91` or `192.168.137.249`).
- **Telemetry Protocol**:
  - Format: NDJSON / JSON over HTTP POST to `http://192.168.137.1:8088/api/telemetry`.
  - Content-Type: `application/json`.
  - Rate: 1 Hz to 2 Hz nominal stream.
  - Authentication: Pre-shared token (`DEVICE_API_TOKEN`) verified by `TelemetryIngestEngine` and scrubbed before logging.

---

## 3. Dual-Authority Functional Safety Architecture

Safety is not delegated to the dashboard or the remote software layer. Hardware retains authoritative local protection:

1. **ESP32 Autonomous Protection (Authority 1)**:
   - Evaluated locally every 10 ms independent of Wi-Fi or backend availability.
   - Voltage cutoffs: Undervoltage ($V < 6.00\text{ V}$), Overvoltage ($V > 8.50\text{ V}$).
   - Overcurrent cutoff: $I > 5.0\text{ A}$.
   - Overtemperature cutoff: $T > 55.0\text{ }^\circ\text{C}$.
   - Sensor fault detection: INA219 disconnected ($V \le 0.1\text{ V}$) or DS18B20 CRC failure ($T = -127\text{ }^\circ\text{C}$).
   - Gate action: Immediate hardware pull-down of GPIO18 isolating the load MOSFET.
2. **Backend Hard Safety Barrier (Authority 2)**:
   - Supervisor interlock validates bounds on every received frame.
   - If any hardware fault or boundary trip is reported, operational decisions are clamped to `HOLD` with actuation intent `KEEP_ISOLATED`.
3. **Supervisory Dashboard (Observer Only)**:
   - The dashboard is an observation and audit interface.
   - It cannot override the hardware safety barrier or force-enable the load MOSFET when a fault is present.

---

## 4. Fault Recovery Lifecycle

The firmware and backend implement a state machine that handles fault conditions deterministically:

```
    [IDLE] 
       |
       |  (Physical fault occurs: e.g. SENSOR_INVALID)
       v
    [FAULT]  --> MOSFET forced OFF, latch fault reason, stream FAULT state
       |
       |  (Physical condition returns to normal)
       v
  [RECOVERY QUALIFICATION] --> Wait for N consecutive healthy samples
       |
       |  (Healthy verification threshold reached)
       v
    [IDLE]   --> State returns to IDLE, fault_reason = NONE, ready for test
```

- When the ESP32 is in `FAULT`, the backend and frontend both report:
  - `HARDWARE STATE: FAULT`
  - `HARDWARE FAULT: FAULT LATCHED`
  - `FAULT REASON: SENSOR_INVALID`
  - `SAFETY BARRIER: SAFETY TRIP ACTIVE`
- When sensor readings recover and the ESP32 transitions back to `IDLE`:
  - `HARDWARE STATE: IDLE`
  - `HARDWARE FAULT: NO FAULT`
  - `FAULT REASON: NONE`
  - `SAFETY BARRIER: CLEAR (OPERATIONAL)`
- Stale fault caching is strictly prevented by real-time state synchronization.
