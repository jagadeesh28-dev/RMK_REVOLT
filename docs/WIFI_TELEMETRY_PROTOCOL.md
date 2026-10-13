# NEXUS — Wi-Fi Telemetry & Command Protocol Specification

## 1. Scope & Protocol Overview

This document specifies the communication protocol between the physical NEXUS embedded bench (ESP32 node) and the SECONDShift backend server over local Wi-Fi (LAN).

The protocol supports:
1. **Upstream Telemetry**: Streaming physical electrical, thermal, and supervisor state observations from the ESP32 to the backend.
2. **Downstream Directives**: Transmitting supervisory commands (e.g., `STOP`, `CLEAR`, `HOLD`, `STATUS`) from the backend to the ESP32.
3. **Observability Streaming**: Server-Sent Events (SSE) and fast REST polling from the backend to the web console.

---

## 2. Canonical Telemetry Packet Schema

Upstream telemetry packets emitted by the ESP32 MUST conform to the canonical JSON schema below.

### 2.1 Example Canonical JSON Payload
```json
{
  "schema_version": "1.0",
  "device_id": "NEXUS-ESP32-01",
  "sequence": 1042,
  "timestamp_ms": 1728410042000,
  "voltage_v": 3.318,
  "current_a": 1.832,
  "power_w": 6.079,
  "temperature_c": 28.6,
  "mosfet_state": "ON",
  "hardware_state": "RUNNING",
  "hardware_fault": false,
  "sensor_valid": true,
  "wifi_rssi": -59
}
```

### 2.2 Field Definitions & Rules

| Field Name | Type | Mandatory? | Physical Unit / Permitted Values | Validation Rules |
|---|:---:|:---:|---|---|
| `schema_version` | String | Yes | `"1.0"` | Must match expected major version. |
| `device_id` | String | Yes | E.g. `"NEXUS-ESP32-01"` | Must belong to backend authorized device registry. |
| `sequence` | Integer | Yes | Count ($0 \le N \le 2^{32}-1$) | Must be strictly positive integer; tracked for gaps and duplicates. |
| `timestamp_ms` | Number | Yes | Milliseconds since epoch or boot | Non-negative numeric timestamp. Monotonic continuity checked. |
| `voltage_v` | Float / null | Yes | Volts ($\text{V}$) | $1.00 \le V \le 60.00\,\text{V}$. Non-numeric, NaN, and Inf rejected. Explicit `null` preserved. |
| `current_a` | Float / null | Yes | Amperes ($\text{A}$) | $-50.00 \le I \le 50.00\,\text{A}$ ($+ = \text{discharge}, - = \text{charge}$). Explicit `null` preserved. |
| `power_w` | Float / null | No | Watts ($\text{W}$) | Computed as $V \times I$. Preserves `null` if $V$ or $I$ is `null`. |
| `temperature_c` | Float / null | Yes | Celsius ($^\circ\text{C}$) | $-20.0 \le T \le 85.0^\circ\text{C}$. Explicit `null` preserved. |
| `mosfet_state` | String | Yes | `"ON"` or `"OFF"` | Reflects physical gate drive state. |
| `hardware_state` | String | Yes | `"RUNNING"`, `"IDLE"`, `"FAULT"`, `"SAFE_STOP"` | Supervisor FSM status. |
| `hardware_fault` | Boolean | Yes | `true` or `false` | True if autonomous supervisor tripped. |
| `sensor_valid` | Boolean | Yes | `true` or `false` | False if INA219 or DS18B20 fails CRC/reading. |
| `wifi_rssi` | Integer / null | No | $\text{dBm}$ (e.g. $-58$) | Signal strength metric. |

---

## 3. HTTP REST Endpoints

### 3.1 Telemetry Ingestion: `POST /api/telemetry`
- **Caller**: ESP32 Node
- **Headers**:
  - `Content-Type: application/json`
  - `X-Device-ID: NEXUS-ESP32-01` (optional)
- **Request Body**: Canonical Telemetry JSON
- **Responses**:
  - `200 OK`: Telemetry accepted and validated.
    ```json
    {
      "status": "ACCEPTED",
      "reason": "ACCEPTED",
      "details": {
        "sequence": 1042,
        "device_id": "NEXUS-ESP32-01",
        "server_timestamp": 1728410042.105,
        "quality": "VALID"
      },
      "command": null
    }
    ```
    *(If a supervisory command is pending, `"command"` contains the next directive to be executed by the node).*
  - `400 Bad Request`: Malformed JSON syntax or missing mandatory fields.
  - `422 Unprocessable Entity`: Validation failure (out-of-bounds voltage/current/temp, duplicate packet, hardware fault).

### 3.2 Live Telemetry Snapshot: `GET /api/telemetry/live`
- **Caller**: Dashboard / Monitoring Tools
- **Response**: Sanitized snapshot containing hardware connection status, electrical readings, thermal readings, supervisor status, and shadow decisions.

### 3.3 Server-Sent Events Stream: `GET /api/telemetry/stream`
- **Caller**: Web Frontend Dashboard
- **Headers**:
  - `Content-Type: text/event-stream`
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`
- **Event Body**: Real-time JSON events emitted as sequence increments occur.

### 3.4 Supervisory Command Dispatch: `POST /api/command`
- **Caller**: Authorized Backend / Operator UI
- **Request Body**:
  ```json
  {
    "action": "STOP"
  }
  ```
- **Authorized Actions**: `STOP`, `CLEAR`, `STATUS`, `AUTO`, `ON`, `OFF`, `HOLD`
- **Prohibited Endpoints**: Arbitrary GPIO controls (e.g. `/gpio/25/high`) are **strictly forbidden** and return `404 Not Found`.

---

## 4. Heartbeat & Connection State Machine

The backend `TelemetryIngestEngine` continuously evaluates packet age ($t_{\text{age}} = t_{\text{now}} - t_{\text{last\_seen}}$):

```
       Packet Received (age <= 3.0s)
  ┌─────────────────────────────────────┐
  │                                     │
  ▼                                     │
┌──────────────┐   age > 3.0s    ┌──────┴───────┐   age > 10.0s   ┌────────────────┐
│  CONNECTED   │ ──────────────> │    STALE     │ ──────────────> │  DISCONNECTED  │
│    (LIVE)    │                 │ (DATA AGING) │                 │  (LINK LOST)   │
└──────┬───────┘                 └──────────────┘                 └────────────────┘
       │                                                                  ▲
       │ Hardware Fault /                                                 │
       │ Supervisor Trip                                                  │
       ▼                                                                  │
┌──────────────┐                                                          │
│    FAULT     │ ─────────────────────────────────────────────────────────┘
│  (LATCHED)   │               Trip cleared and reconnected
└──────────────┘
```

- **Configurable Thresholds**:
  - `telemetry_timeout_s = 3.0` s
  - `disconnect_timeout_s = 10.0` s
- **Frontend Behavior**: If in `STALE` state, the dashboard displays an explicit amber `STALE DATA (X.Xs)` badge. In `DISCONNECTED` state, live readings are blanked to `N/A`.

---

## 5. Security & Authentication Model

1. **Local Network Confinement**: Designed for isolated laboratory/testbed LAN operation.
2. **Device Whitelisting**: Packets originating from unlisted `device_id` strings are quarantined (`UNAUTHORIZED_DEVICE`) and never enter the decision pipeline.
3. **Command Origin Gating**: Only supervisory actions from verified backend endpoints are queued; raw GPIO access is completely eliminated.
4. **Credential Isolation**: SSID and WPA2 passwords reside exclusively in untracked files (`secrets.h`, `.env`) and are excluded from version control.
