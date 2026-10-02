# SECONDShift Canonical Telemetry Schema Specification

**Document Version:** 1.0.0  
**Interface Layer:** Layer 2 (Measurement Normalization & Ingestion)  
**Encoding:** JSON / Newline-Delimited JSON (NDJSON)

---

## 1. Schema Definition (`TelemetryFrame`)

The `TelemetryFrame` is the canonical, strongly-typed data contract between Layer 1 hardware transports and the Layer 3 scientific research engine.

### Data Model & Physical Units:

```python
@dataclass
class TelemetryFrame:
    device_id: str                      # Alphanumeric hardware node ID
    sequence_number: int                # Monotonic packet counter (0 .. 2^31-1)
    timestamp: float                    # POSIX timestamp in seconds (epoch)
    voltage_v: Optional[float]          # Total pack terminal voltage (V)
    current_a: Optional[float]          # String current (A) [+ = discharge, - = charge]
    temperature_c: Optional[float]      # Maximum module surface temperature (°C)
    cell_voltages_v: List[float]        # Individual cell voltages [V]
    cell_temperatures_c: List[float]    # Thermistor temperature readings [°C]
    estimated_soc: Optional[float]      # Coulomb-counted or OCV-based SOC (0.0 to 1.0)
    sensor_status: Dict[str, str]       # Subsystem health map {"voltage": "OK", ...}
    communication_status: str           # Transport link quality enum
    calibration_status: str             # Sensor calibration state enum
    source: str                         # Origin: REAL_HARDWARE, MOCK, REPLAY
    quality_flags: List[str]            # Validation quality tags (VALID, STALE, etc.)
    raw_payload: Optional[Dict[str, Any]]
```

---

## 2. Enumerated Status Types

### 2.1 `TelemetryQuality`
- `VALID`: Structurally sound, within physical boundaries, and temporally fresh.
- `MISSING`: Required sensor field is null, missing, or frame dropped.
- `STALE`: Frame timestamp age exceeds $2.0\text{ s}$.
- `OUT_OF_RANGE`: Measurement violates physical electro-thermal limits.
- `SENSOR_FAULT`: Sensor diagnostics flag an internal hardware failure.
- `COMMUNICATION_FAULT`: Link packet regression, framing error, or bus timeout.
- `CALIBRATION_REQUIRED`: Sensor zero-offset or gain drift flag set.

### 2.2 `SensorHealthStatus`
- `OK`: Sensor operates within calibrated accuracy limits.
- `DEGRADED`: Noise floor elevated, calibration warning active.
- `FAULT`: Open circuit, short circuit, or ADC rail clip detected.
- `UNAVAILABLE`: Sensor channel unpopulated or disconnected.

### 2.3 `CommunicationStatus`
- `CONNECTED`: Active UART connection with continuous stream.
- `DEGRADED`: Intermittent parity errors or retransmission events.
- `DROPOUT`: Frame stream interrupted for $>1.0\text{ s}$.
- `DISCONNECTED`: Physical transport layer closed.

---

## 3. Telemetry Validation Fault Codes

The `TelemetryValidator` applies non-negotiable checks and outputs structured fault diagnostics:

| Fault Code | Category | Condition | Quality Tag | Action |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_STRUCT_01` | Structural | Missing or non-string `device_id` | `OUT_OF_RANGE` | Reject |
| `ERR_STRUCT_02` | Structural | Missing or non-integer `sequence_number` | `OUT_OF_RANGE` | Reject |
| `ERR_STRUCT_03` | Structural | Missing or non-float `timestamp` | `OUT_OF_RANGE` | Reject |
| `ERR_NUM_01` | Numeric | Field contains `NaN` or `Infinity` | `OUT_OF_RANGE` | Reject |
| `ERR_RANGE_01` | Physical | Module voltage $V_{\text{mod}} \notin [1.0, 60.0]\text{ V}$ | `OUT_OF_RANGE` | Reject |
| `ERR_RANGE_02` | Physical | Cell voltage $V_{\text{cell}} \notin [1.0, 4.5]\text{ V}$ | `OUT_OF_RANGE` | Reject |
| `ERR_RANGE_03` | Physical | Current $I \notin [-50.0, 50.0]\text{ A}$ | `OUT_OF_RANGE` | Reject |
| `ERR_RANGE_04` | Physical | Temperature $T \notin [-20.0, 85.0]^\circ\text{C}$ | `OUT_OF_RANGE` | Reject |
| `ERR_SENS_01` | Hardware | Sensor status is `FAULT` or `UNAVAILABLE` | `SENSOR_FAULT` | Reject |
| `ERR_COMM_01` | Transport | Link in `DROPOUT` or `DISCONNECTED` | `COMM_FAULT` | Reject |
| `ERR_TIME_01` | Temporal | Timestamp age $> 2.0\text{ s}$ (Stale telemetry) | `STALE` | Reject |
| `ERR_TIME_02` | Temporal | Timestamp in future by $> 5.0\text{ s}$ (Clock skew) | `STALE` | Reject |
| `ERR_SEQ_01` | Continuity | Sequence regression ($S_k < S_{k-1}$) | `COMM_FAULT` | Reject |
| `WARN_SEQ_01` | Warning | Duplicate sequence number | `VALID` | Pass (Logged) |
| `WARN_SEQ_02` | Warning | Sequence gap ($S_k > S_{k-1} + 1$, frame drop) | `VALID` | Pass (Logged) |

---

## 4. Payload Examples

### 4.1 Valid Ingestion Frame
```json
{
  "device_id": "SECONDShift-BENCH-01",
  "sequence_number": 512,
  "timestamp": 1772539210.0,
  "voltage_v": 13.28,
  "current_a": 1.50,
  "temperature_c": 24.5,
  "cell_voltages_v": [3.32, 3.32, 3.32, 3.32],
  "cell_temperatures_c": [24.5, 24.5, 24.5, 24.5],
  "estimated_soc": 0.65,
  "sensor_status": {"voltage": "OK", "current": "OK", "temperature": "OK"},
  "communication_status": "CONNECTED",
  "source": "REAL_HARDWARE"
}
```

### 4.2 Rejected Frame (Sensor Fault & Undervoltage)
```json
{
  "device_id": "SECONDShift-BENCH-01",
  "sequence_number": 513,
  "timestamp": 1772539211.0,
  "voltage_v": 0.85,
  "current_a": 0.00,
  "temperature_c": 24.5,
  "cell_voltages_v": [0.85],
  "sensor_status": {"voltage": "FAULT", "current": "OK", "temperature": "OK"},
  "communication_status": "CONNECTED",
  "source": "REAL_HARDWARE"
}
```
**Validation Output:**
- `valid`: `false`
- `quality`: `"SENSOR_FAULT"`
- `errors`: `["ERR_RANGE_01: Module voltage 0.850V outside [1.0, 60.0]V", "ERR_RANGE_02: Cell 0 voltage 0.850V outside [1.0, 4.5]V", "ERR_SENS_01: Sensor 'voltage' status is FAULT"]`
