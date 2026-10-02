# SECONDShift ESP32 Firmware & Hardware Interface Specification

**Document Version:** 1.0.0  
**Target Hardware:** ESP32-WROOM-32D / HERMES Low-Voltage Qualification Testbed  
**Protocol:** Newline-Delimited JSON (NDJSON) over UART  
**Baud Rate:** 115200 bps (8-N-1)

---

## 1. Physical Layer & Electrical Interface

### 1.1 UART Serial Parameters
- **Baud Rate:** 115200 bps
- **Data Bits:** 8
- **Parity:** None
- **Stop Bits:** 1
- **Flow Control:** None (Software ACK/NACK handshake)
- **Delimiters:** Unix newline (`\n`, `0x0A`)
- **Max Packet Length:** 1024 bytes per line

### 1.2 Physical Sensor Bus & Pinout Mapping
- **Voltage Measurement:** ADS1115 16-bit I2C ADC (Address: `0x48`), differential inputs across 4 cells, range: 0.0V–4.5V.
- **Current Measurement:** INA226 16-bit high-side current & power monitor (Address: `0x40`), 0.002 $\Omega$ shunt, range: -50A to +50A.
- **Temperature Sensing:** 10 k$\Omega$ NTC thermistors via 12-bit internal ADC (GPIO34, GPIO35) with Steinhart-Hart linearization.
- **Contactor Drive:** Active-high MOSFET gate drivers on GPIO25 (Charge Contactor) and GPIO26 (Discharge Contactor).
- **Watchdog Strobe:** Dedicated GPIO18 toggling TPS3823 watchdog strobe pin `WDI`.

---

## 2. Telemetry Frame Specification (ESP32 $\to$ Host)

Every sample interval (nominally 10 Hz or 1 Hz idle), the ESP32 outputs an NDJSON telemetry packet conforming to the canonical `TelemetryFrame` schema.

### JSON Schema:
```json
{
  "device_id": "HERMES_BENCH_01",
  "sequence_number": 1042,
  "timestamp": 1772539200.125,
  "voltage_v": 13.284,
  "current_a": 0.000,
  "temperature_c": 24.8,
  "cell_voltages_v": [3.321, 3.320, 3.322, 3.321],
  "cell_temperatures_c": [24.7, 24.8, 24.9, 24.8],
  "estimated_soc": 0.65,
  "sensor_status": {
    "voltage": "OK",
    "current": "OK",
    "temperature": "OK"
  },
  "communication_status": "CONNECTED",
  "calibration_status": "CALIBRATED",
  "source": "REAL_HARDWARE"
}
```

### Field Definitions:
| Field | Type | Unit | Description | Valid Range |
| :--- | :--- | :--- | :--- | :--- |
| `device_id` | string | - | Unique bench/module hardware identifier | Non-empty string |
| `sequence_number` | integer | - | Monotonically increasing 32-bit counter | 0 to $2^{31}-1$ |
| `timestamp` | float | s | POSIX timestamp or monotonic seconds | $> 0$ |
| `voltage_v` | float | V | Total pack terminal voltage | 1.0 to 60.0 V |
| `current_a` | float | A | String current (+ = discharge, - = charge) | -50.0 to +50.0 A |
| `temperature_c` | float | °C | Maximum module surface temperature | -20.0 to +85.0 °C |
| `cell_voltages_v` | list[float] | V | Array of individual series cell voltages | 1.0 to 4.5 V per cell |
| `cell_temperatures_c` | list[float] | °C | Array of cell-level thermistor readings | -20.0 to +85.0 °C |
| `sensor_status` | dict | - | Per-subsystem health (`OK`, `DEGRADED`, `FAULT`) | Subsystem status |
| `communication_status` | string | - | Link state (`CONNECTED`, `DEGRADED`, `FAULT`) | Enum string |
| `source` | string | - | Data origin (`REAL_HARDWARE`) | Enum string |

---

## 3. Command Frame Specification (Host $\to$ ESP32)

Commands from the supervisory SECONDShift runner are dispatched as single-line NDJSON payloads.

### JSON Schema:
```json
{
  "type": "command",
  "command_id": "c98f12a4",
  "action": "OPERATE",
  "requested_mode": "ENABLE_LOAD",
  "interlock_required": true,
  "current_limit_a": 10.0,
  "pulse_duration_s": null,
  "timestamp": 1772539200.500,
  "reason": "Known chemistry (99.8%), marginal risk 0.38% <= 1.0%"
}
```

### Supported Abstract Modes:
1. `ENABLE_LOAD`: Close main discharge contactor up to `current_limit_a`.
2. `LIMIT_LOAD`: Close discharge contactor with derated current ceiling (e.g. 5.0A).
3. `EXECUTE_PULSE`: Fire diagnostic current pulse of duration `pulse_duration_s` (10s) and amplitude `current_limit_a` for chemical disambiguation.
4. `ISOLATE`: Open all contactors immediately (RETIRE / FAULT).
5. `KEEP_ISOLATED`: Maintain open contactor interlock (HOLD / QUARANTINE).

---

## 4. Handshake & Acknowledgement Protocol

1. **Host Dispatches Command:** Host sends single-line JSON command terminated by `\n`.
2. **Firmware Response:** ESP32 must respond within 100 ms with an ACK or NACK packet:
   ```json
   {"type": "ack", "command_id": "c98f12a4", "status": "ACCEPTED", "timestamp": 1772539200.512}
   ```
   If parameter bounds or hardware interlocks fail:
   ```json
   {"type": "nack", "command_id": "c98f12a4", "status": "REJECTED", "error": "ERR_INTERLOCK_OVERCURRENT", "timestamp": 1772539200.515}
   ```
3. **Heartbeat Cadence:** Host dispatches a heartbeat pulse every 500 ms. If no valid packet arrives within 1500 ms, ESP32 autonomously opens all contactors.

---

## 5. Independent Hardware Safety Layer (Independent of ESP32)

The physical platform incorporates two dedicated hardware safety supervisors that function completely outside ESP32 firmware:

```
+-----------------------------------------------------------------------+
| INDEPENDENT HARDWARE SAFETY TRIP ARCHITECTURE                         |
+-----------------------------------------------------------------------+
|                                                                       |
|   Cell Sensing Lines                                                  |
|          |                                                            |
|          +---------> [ LM393 Dual Analog Comparator ]                 |
|          |           - Hardware UVP trip (< 2.00 V)                   |
|          |           - Hardware OVP trip (> 4.35 V)                   |
|          |           - Hardware OTP trip (> 60.0 °C)                  |
|          |           - Trip Latency: 11.8 ms (PHYSICAL EXPERIMENT)    |
|          |                       |                                    |
|          |                       v [ HARDWARE TRIP LATCH ]            |
|          |                               |                            |
|          |                               v                            |
|          |                       [ POWER CONTACTOR ] ===> OPEN LOAD   |
|          |                               ^                            |
|          v                               |                            |
|   [ ESP32 MCU ]                          |                            |
|          |                               |                            |
|          +-(GPIO18 Strobe)-> [ TPS3823 Hardware Watchdog ]            |
|                              - Trip Latency: 194.2 ms                 |
|                              - Cuts contactor coil power on freeze    |
|                                                                       |
+-----------------------------------------------------------------------+
```

1. **LM393 Dual Analog Comparator:**
   - **UVP Threshold:** 2.00 V reference divider.
   - **OVP Threshold:** 4.35 V reference divider.
   - **OTP Threshold:** 60.0 °C analog NTC comparator.
   - **Trip Mechanism:** Direct gate pull-down on contactor MOSFET latch.
   - **Demonstrated Physical Trip Latency:** **11.8 ms** (no software dependency).

2. **TPS3823 Microprocessor Supervisory Watchdog:**
   - **Timeout Window:** 200 ms maximum.
   - **Heartbeat Pin:** GPIO18 toggled on every valid loop iteration.
   - **Demonstrated Physical Trip Latency:** **194.2 ms** on firmware crash or freeze.
