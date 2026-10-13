# NEXUS — Wi-Fi Hardware Telemetry Integration Architecture

## 1. Executive Summary & Objective

This document specifies the technical architecture for the real hardware integration connecting the physical NEXUS battery qualification bench (ESP32 node, INA219 current/voltage sensor, DS18B20 1-Wire temperature probe, and low-side N-channel MOSFET load switch) to the NEXUS / SECONDShift software platform over Wi-Fi.

The integration establishes a trustworthy, sequenced, timestamped, and validated physical telemetry stream from the physical bench to the backend and live frontend dashboard, enabling shadow-mode algorithmic evaluation without compromising physical electrical safety.

---

## 2. Core Architectural Invariants

### 2.1 The Autonomous Safety Barrier
- **Hardware Supervisor Authority**: The ESP32 firmware executes a non-blocking supervisor state machine (`RUNNING`, `IDLE`, `FAULT`, `SAFE_STOP`) that independently enforces undervoltage cutoff ($V < 2.00\,\text{V}$), overvoltage cutoff ($V > 3.75\,\text{V}$), overcurrent cutoff ($|I| > 3.00\,\text{A}$), and overtemperature cutoff ($T > 45.0^\circ\text{C}$).
- **Network Independence**: Wi-Fi connection state does **NOT** influence or disable local hardware safety. If the Wi-Fi link drops, the local hardware supervisor continues uninterrupted physical monitoring and will trip the MOSFET immediately upon any fault condition.
- **Frontend Isolation**: The frontend dashboard possesses **ZERO** direct hardware control. Actuation requests must flow through the backend `ActuationPolicy`, schema validation, command lifecycle tracking, and the ESP32 hardware supervisor.

### 2.2 Strict Invariant: Missingness vs. Zero
- $\text{None} \ne 0.0$.
- Missing voltage is **NOT** $0.0\,\text{V}$.
- Missing current is **NOT** $0.0\,\text{A}$.
- Missing temperature is **NOT** $0.0^\circ\text{C}$.
- Missing $R_0$ resistance is **NOT** $0.0\,\Omega$.
- The backend `TelemetryIngestEngine` and `TelemetryValidator` preserve explicit `None` representations and never substitute default zeros.

### 2.3 Strict Credential Hygiene
- All network credentials (`WIFI_SSID`, `WIFI_PASSWORD`, `BACKEND_HOST`, `BACKEND_PORT`, `DEVICE_API_TOKEN`) are strictly private secrets.
- Tracked templates are provided via `ESP32_CODE/sketch_oct5a/secrets.h.example` and `.env.example`.
- Untracked local copies `secrets.h` and `.env` are enforced via `.gitignore`.
- Passwords and private tokens are never printed in serial logs, backend stdout, UI snapshots, telemetry packets, or git commits.

---

## 3. End-to-End System Pipeline

```
REAL BATTERY SPECIMEN (LFP / NMC)
              │
              ▼
    ┌──────────────────┐
    │     INA219       │  I2C (0x40): Bus Voltage (V), Shunt Current (A), Power (W)
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │    DS18B20       │  1-Wire (GPIO 4): Surface Temperature (°C)
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │      ESP32       │  • Autonomous Safety Supervisor FSM
    │  PHYSICAL BENCH  │  • Non-blocking Dual-Stream: USB Serial (115200) + Wi-Fi HTTP POST
    └────────┬─────────┘  • Monotonic sequence counter & millisecond timestamps
             │
             │ Wi-Fi LAN (WPA2-PSK) / HTTP POST to /api/telemetry
             ▼
    ┌──────────────────┐
    │     BACKEND      │  • TelemetryIngestEngine (Layer 1/2)
    │  (SECONDShift)   │  • Device Authentication & Registry Validation
    │                  │  • Sequence Gap & Monotonicity Tracking
    └────────┬─────────┘  • Dual Buffering: RAW Audit Buffer vs. ACCEPTED Telemetry Buffer
             │
             ▼
    ┌──────────────────┐
    │  NEXUS PIPELINE  │  • TelemetryValidator (Layer 2)
    │   (SHADOW MODE)  │  • TriageGate & Measurement Admissibility
    │                  │  • Feature Engine (Physical ΔVtotal, ΔVohmic, R0)
    └────────┬─────────┘  • Epistemic Belief & Operational Decision
             │
             │ SSE Stream (/api/telemetry/stream) & Poll (/api/status)
             ▼
    ┌──────────────────┐
    │     FRONTEND     │  • Live Electrical (V, I, P) & Thermal (T) Reflection
    │    DASHBOARD     │  • Wi-Fi & Backend Link State (CONNECTED / STALE / DISCONNECTED / FAULT)
    │                  │  • Explicit STALE DATA indicator with age
    └──────────────────┘  • Strict Separation: Epistemic State vs. Operational Decision
```

---

## 4. Component Implementations

### 4.1 Embedded Node (`ESP32_CODE/sketch_oct5a/sketch_oct5a.ino`)
- **Dual-Stream Emission**: Simultaneously transmits canonical NDJSON frames over USB UART (`Serial`) and Wi-Fi HTTP POST (`http://<BACKEND_HOST>:<PORT>/api/telemetry`).
- **Non-Blocking Network FSM**:
  - `WIFI_STATE_BOOT`: Initial hardware verification and Wi-Fi subsystem initialization.
  - `WIFI_STATE_CONNECTING`: Non-blocking Wi-Fi association attempts.
  - `WIFI_STATE_CONNECTED`: Connection active, HTTP client configured.
  - `WIFI_STATE_RECONNECTING`: Exponential backoff network reconnection.
  - `WIFI_STATE_OFFLINE`: Autonomous local execution if Wi-Fi network is absent.
- **Acquisition vs. Transmission Rate**: Sensor acquisition executes at $10\,\text{Hz}$ locally for fast safety comparator trips, while network transmission is throttled to $1\,\text{Hz}$ to avoid socket saturation.

### 4.2 Ingestion Engine (`secondshift/hardware/telemetry_ingest.py`)
- **Device Authentication**: Rejects unregistered device IDs (`UNAUTHORIZED_DEVICE`).
- **Integrity Validation**: Rejects malformed JSON, NaN/Infinity, out-of-bounds electrical limits, duplicate sequences, and sequence regressions.
- **Heartbeat State Machine**:
  - `CONNECTED`: Telemetry frame received within `telemetry_timeout_s` ($3.0\,\text{s}$).
  - `STALE`: Packet age exceeds `telemetry_timeout_s` but is below `disconnect_timeout_s` ($10.0\,\text{s}$).
  - `DISCONNECTED`: Packet age exceeds `disconnect_timeout_s`.
  - `FAULT`: ESP32 reports active `hardware_fault` or supervisor trip.
- **Dual Buffer Design**:
  - `raw_history`: Exact uncleaned raw payload preserved for forensic replay.
  - `accepted_frames`: Strongly-typed, validated `TelemetryFrame` instances.

### 4.3 Hardware Adapter (`secondshift/hardware/wifi_hardware.py`)
- Implements `HardwareInterface` contract (`connect`, `disconnect`, `is_connected`, `read_telemetry`, `send_command`, `get_status`).
- Interoperates with `HILRunner` and CLI (`secondshift run --mode wifi`).

### 4.4 Dashboard Integration (`secondshift/software/ui/dashboard.py`)
- **HTTP Server**: Serves UI on port 8080 with endpoints `/api/status`, `/api/telemetry/live`, `/api/telemetry/stream` (Server-Sent Events), and `/api/command`.
- **UI Elements**:
  - Header node chip: `#hw-conn`, `#hw-dev-chip`, `#hw-seq-chip`, `#hw-stale-badge`.
  - Panel `#pn-nexus-hw`: Device ID, Wi-Fi link, Backend link, Telemetry state, Age, Sequence, Packet gaps, RSSI, MOSFET switch, FSM state, Fault latches, Sensor validity.
  - Live measurements: High-contrast electrical and thermal tiles.

---

## 5. Execution Commands

### Run Dashboard with Live Telemetry Intake
```bash
python -m secondshift.software.ui.dashboard 8080
```

### Run Closed-Loop Qualification via Wi-Fi Hardware
```bash
python -m secondshift.cli run --mode wifi --device-id NEXUS-ESP32-01 --cell-id SPECIMEN_01
```

### Validate Historical Wi-Fi Replay Artifact
```bash
python -m secondshift.cli validate-telemetry --input secondshift/data/raw/esp32_wifi_prototype_run_001.ndjson --allow-stale
```

### Execute Wi-Fi Replay Qualification
```bash
python -m secondshift.cli run --mode replay --replay-file secondshift/data/raw/esp32_wifi_prototype_run_001.ndjson
```
