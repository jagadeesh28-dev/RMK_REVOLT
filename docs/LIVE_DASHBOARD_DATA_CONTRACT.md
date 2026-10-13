# NEXUS Live Dashboard Data Contract & Classification Policy

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/LIVE_DASHBOARD_DATA_CONTRACT.md`  
**Classification**: Engineering Specification & Scientific Data Governance  
**Governing Rule**: Physical Truth Over Cosmetic Completeness & Strict Non-Fabrication Invariant

---

## 1. Non-Negotiable Data Classification Hierarchy

To eliminate ambiguity, prevent scientific misrepresentation, and guarantee rigorous industrial traceability, all data ingested, processed, and displayed across the NEXUS system is strictly classified into four mutually exclusive categories:

```
+-----------------------------------------------------------------------------+
|                                DATA HIERARCHY                               |
+-----------------------------------------------------------------------------+
|  [CLASS A] REAL LIVE HARDWARE DATA                                          |
|            Direct physical measurements streamed from ESP32 node            |
|            (voltage, current, power, temperature, MOSFET, FSM state, fault) |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|  [CLASS B] CURRENT DERIVED NEXUS DATA                                       |
|            Calculated at runtime from active current session telemetry      |
|            (admissibility, R0, ΔV, SOH, epistemic belief, decision trace)   |
|            *Only populated when identifiable dynamic evidence exists*       |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|  [CLASS C] HISTORICAL / FROZEN VALIDATION EVIDENCE                          |
|            Established frozen scientific research benchmarks                |
|            (Phase 5 feature admission, Phase 6.1.1 LOFO ablation, limits)   |
|            *Strictly segregated in dedicated reference panels*              |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|  [UNAVAILABLE] EXPLICIT NON-COMPUTABLE STATE                                |
|            Informative empty state with explicit scientific rationale       |
|            *Never substituted with zeroes or synthetic interpolations*      |
+-----------------------------------------------------------------------------+
```

---

## 2. Invariance & Anti-Fabrication Principles

1. **Physical Zero vs. Missing None**:
   - `0.000 A` or `0.000 W` is an admissible, physically valid measurement (e.g. resting specimen with load isolated). Zero is **never** replaced by historical non-zero values.
   - Missing or non-identifiable parameters (e.g., SOH in rest mode, unmeasured R0) must remain strictly `None` / `[UNAVAILABLE]`, never cast to `0.0`.
2. **Connectivity $\neq$ Battery Qualification**:
   - A live Wi-Fi telemetry stream from an ESP32 proves **hardware and telemetry connectivity**.
   - It does **not** prove battery qualification, health state, or second-life suitability until an intentional diagnostic qualification protocol (e.g. current pulse excitation) is executed and evaluated by the decision engine.
3. **No Synthetic Time Series**:
   - Time-series charts display **only actual recorded points**.
   - If 1 point exists, 1 point is plotted. If 50 points exist, 50 points are plotted. Points are **never** fabricated through interpolation or synthetic smoothing merely to make graphs look full.
4. **Historical Isolation**:
   - Historical evidence from Phase 5 / Phase 6.1.1 is strictly presented as reference data under the tag `[CLASS C HISTORICAL — NOT CURRENT HARDWARE]`.
   - Historical evidence is **never** injected into the live telemetry stream or presented as current battery metrics.

---

## 3. UI Quantity Traceability Matrix

| UI Quantity | Backend JSON Field | Physical / Analytical Source | Current Availability | Display Category | Action When Unperformed |
|---|---|---|:---:|:---:|---|
| **Voltage** | `telemetry.voltage_v` | INA219 via ESP32 I2C | **LIVE** | `[CLASS A LIVE]` | Displays real ESP32 voltage (e.g. 6.748 V) |
| **Current** | `telemetry.current_a` | INA219 via ESP32 I2C | **LIVE** | `[CLASS A LIVE]` | Displays real ESP32 current (e.g. 0.000 A) |
| **Power** | `telemetry.power_w` | Computed from live V & I | **LIVE** | `[CLASS A LIVE]` | Displays real power (e.g. 0.000 W) |
| **Temperature** | `telemetry.temperature_c` | DS18B20 1-Wire sensor | **LIVE** | `[CLASS A LIVE]` | Displays real temperature (e.g. 32.13 °C) |
| **Hardware State** | `nexus_hardware.hardware_state` | ESP32 local safety FSM | **LIVE** | `[CLASS A LIVE]` | Reflects true state (`IDLE` / `FAULT` / `RUNNING`) |
| **Fault Reason** | `nexus_hardware.fault_reason` | ESP32 fault detector | **LIVE** | `[CLASS A LIVE]` | Reflects true reason (`NONE` / `SENSOR_INVALID` / etc.) |
| **MOSFET State** | `nexus_hardware.mosfet_state` | Hardware gate driver | **LIVE** | `[CLASS A LIVE]` | Reflects true gate state (`OFF` / `ON`) |
| **Sequence** | `nexus_hardware.sequence` | ESP32 packet counter | **LIVE** | `[CLASS A LIVE]` | Displays true monotonic packet number |
| **Packet Loss** | `nexus_hardware.packet_gaps` | Ingest gap detector | **LIVE** | `[CLASS A LIVE]` | Displays sequence discontinuities |
| **Wi-Fi RSSI** | `nexus_hardware.wifi_rssi` | ESP32 Wi-Fi radio | **LIVE** | `[CLASS A LIVE]` | Displays real signal strength in dBm |
| **Data Quality** | `data_quality.quality_state` | TelemetryValidator | **LIVE DERIVED** | `[CLASS B DERIVED]` | `VALID` or `DEGRADED` based on sensor admissibility |
| **Delta V Total** | `data_quality.delta_v_total` | Pulse feature extraction | **UNAVAILABLE** | `[CLASS B DERIVED]` | Explicitly `None` pending diagnostic pulse |
| **SOH Estimate** | `bayesian.soh_estimate` | Bayesian estimator | **UNAVAILABLE** | `[CLASS B DERIVED]` | Displays `NO CURRENT SOH ESTIMATE` |
| **R0 Ohmic** | `bayesian.r0_mohm` | Ohmic step estimator | **UNAVAILABLE** | `[CLASS B DERIVED]` | Displays `NO CURRENT R0 ESTIMATE` |
| **Marginal Risk** | `decision.marginal_risk` | Risk model evaluation | **UNAVAILABLE** | `[CLASS B DERIVED]` | Displays `NO CURRENT RISK TRACE` |
| **Decision Trace** | `decision_trace` | Audit event logger | **UNAVAILABLE** | `[CLASS B DERIVED]` | Displays structured `NO QUALIFICATION DECISION RECORDED` |
| **Historical Baseline** | `historical_baseline` | Phase 5 / 6.1.1 freeze | **REFERENCE** | `[CLASS C HISTORICAL]` | Rendered in dedicated reference panels only |

---

## 4. Canonical Graph Contract Schema

The API endpoints (`/api/status`, `/api/telemetry/history`) adhere to the following schema for time series data:

```json
{
  "source": "LIVE",
  "metric": "voltage",
  "unit": "V",
  "points": [
    {
      "timestamp": 1728414000.12,
      "elapsed_s": 12.4,
      "sequence": 142,
      "value": 6.748,
      "label": "12s"
    }
  ],
  "total_points": 1,
  "status": "LIVE_SAMPLES"
}
```

For unperformed derived quantities:
```json
{
  "source": "UNAVAILABLE",
  "metric": "marginal_risk",
  "unit": "%",
  "reason": "NO CURRENT RISK TRACE — AWAITING QUALIFICATION RUN",
  "points": [],
  "total_points": 0,
  "status": "INSUFFICIENT_CURRENT_EVIDENCE",
  "historical_reference_available": true
}
```

---

## 5. Verification Gate Summary

- **Contract Tests**: Verified under `test_live_dashboard_integration.py` (`TEST-DASH-01` through `TEST-DASH-20`).
- **Telemetry Ingestion**: Verified live under `TelemetryIngestEngine`.
- **Status Adapter**: Verified in `status_adapter.build_live_telemetry_snapshot`.
