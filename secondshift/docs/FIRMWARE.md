# HERMES Firmware Specification (ESP32-S3)

## 1. Overview & Architecture

The **HERMES ESP32-S3 Firmware** ([`hermes_esp32.ino`](file:///home/jagadeesh/Documents/RMK_REVOLT/secondshift/firmware/hermes_esp32/hermes_esp32.ino)) is a hard-real-time embedded control engine operating on FreeRTOS. It coordinates precise electrical measurement primitives, maintains hardware watchdog strobes, and strictly defers to the independent analog safety layer.

### Core Partitioning
- **Core 0 (Safety & Acquisition Core):**
  - High-priority Real-Time Task: 100 Hz continuous ADC / shunt acquisition.
  - Dedicated Watchdog Timer Task: 50 ms periodic strobe on GPIO 21.
  - Hardware Trip Interrupt Service Routine (ISR) on GPIO 5.
- **Core 1 (Protocol & Execution Core):**
  - Command Dispatcher: Parses serial JSON requests (`MEASURE_REST`, `CURRENT_PULSE`, `CYCLE_TEST`).
  - Pulse Sequencer: Microsecond-accurate MOSFET gate timing with hardware dead-time protection.
  - 10 Hz Telemetry Streamer: Monotonic timestamped packet formatting.

---

## 2. Real-Time Tasks & Scheduling

| Task Name | Core | Frequency | Priority | Function |
| :--- | :--- | :--- | :--- | :--- |
| `Task_WatchdogStrobe` | 0 | 20 Hz (50 ms) | 24 (Highest) | Toggles GPIO 21 to prevent TPS3823 watchdog timeout (200 ms limit). |
| `Task_SensorSampling` | 0 | 100 Hz (10 ms) | 20 | Samples ADS1115 (voltage) & INA226 (current); checks software safety margins. |
| `Task_ThermalMonitor` | 0 | 2 Hz (500 ms) | 10 | Queries DS18B20 1-Wire sensors; updates temperature registers. |
| `Task_CommandParser`  | 1 | Event-driven  | 15 | Reads JSON commands from USB-CDC UART buffer; validates parameters. |
| `Task_PulseController`| 1 | Microsecond   | 18 | Orchestrates MOSFET PWM ramp, hold, and cutoff transitions. |
| `Task_TelemetryStream`| 1 | 10 Hz (100 ms)| 8  | Emits structured telemetry packets to the host Python supervisor. |

---

## 3. Firmware State Machine

```
      +---------------------+
      |   BOOT / INITIALIZE |
      +---------------------+
                 | Self-tests pass & Bus alive
                 v
      +---------------------+
      |        READY        | <-------------------+
      +---------------------+                     |
         |               |                        |
         | CMD: PULSE    | CMD: REST              | Test Complete
         v               v                        |
  +---------------+ +---------------+             |
  | CURRENT_PULSE | | REST_MONITOR  | ------------+
  +---------------+ +---------------+
         |                  |
         +--------+---------+
                  | Safety Excursion (Over-V, Under-V, Over-T, Watchdog)
                  v
      +---------------------+
      |    FAULT_LOCKOUT    | (Contactor DROPPED, Gate LOW, Persistent)
      +---------------------+
```

### Safety Trip ISR Logic
```c
void IRAM_ATTR isr_hardware_trip() {
    // 1. Immediately drop contactor drive gate
    digitalWrite(PIN_CONTACTOR_REQ, LOW);
    // 2. Shut off electronic load PWM
    ledcWrite(PWM_CHANNEL_LOAD, 0);
    // 3. Set global atomic fault flag
    system_state = STATE_FAULT_LOCKOUT;
    fault_code = FAULT_ANALOG_COMPARATOR_TRIP;
}
```

---

## 4. Communication Protocol (JSON API)

Communication with the host Python layer (`hermes_driver.py`) takes place over a 115,200 baud USB-CDC serial link using newline-delimited JSON messages.

### Host to ESP32 Commands
1. **Rest Voltage Query:**
   ```json
   {"cmd": "MEASURE_REST", "duration_ms": 2000}
   ```
2. **Current Pulse Execution:**
   ```json
   {"cmd": "EXECUTE_PULSE", "current_amps": 5.0, "duration_ms": 5000, "sample_rate_hz": 100}
   ```
3. **Emergency Stop / Open Contactor:**
   ```json
   {"cmd": "EMERGENCY_STOP", "reason": "HOST_REQUEST"}
   ```

### ESP32 to Host Telemetry Response
```json
{
  "status": "COMPLETED",
  "test_id": "PULSE_001",
  "timestamp_ms": 1425890,
  "v_initial": 13.245,
  "v_min": 13.112,
  "v_final": 13.238,
  "delta_v": 0.133,
  "i_mean": 4.98,
  "r0_mohm": 26.7,
  "temp_initial_c": 24.5,
  "temp_peak_c": 24.8,
  "hardware_trip": false,
  "watchdog_ok": true
}
```

---

## 5. Firmware Watchdog & Fail-Safe Mechanics

1. **Watchdog Strobing Window:** The external TPS3823 watchdog supervisory IC requires pin transitions within $[100\text{ ms}, 200\text{ ms}]$. `Task_WatchdogStrobe` triggers every $50\text{ ms}$. If an interrupt storm or CPU freeze delays the strobe beyond $200\text{ ms}$, the TPS3823 asserts `/RESET`, simultaneously holding the contactor circuit open.
2. **Boot-Up Interlock:** Upon reboot or cold power-on, the ESP32 pins default to high-impedance (tri-state). Pull-down resistors on `PIN_CONTACTOR_REQ` guarantee that the contactor cannot energize until firmware explicitly initializes and runs diagnostics.
