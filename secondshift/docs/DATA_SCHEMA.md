# SECONDShift Data Schema Specification

## 1. Overview

This document specifies the exact schemas for raw telemetry, belief state representations, ground-truth registries, and qualification audit logs across the SECONDShift platform.

---

## 2. Ground Truth Registry Schema (`ground_truth_registry.json`)

*Location:* `secondshift/data/raw/ground_truth_registry.json`  
*Access Level:* Quarantined. Accessible **only** by `baseline_characterizer.py` and `MockHermesHardware`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GroundTruthRegistry",
  "type": "object",
  "patternProperties": {
    "^[A-Z0-9_-]+$": {
      "type": "object",
      "properties": {
        "specimen_id": { "type": "string" },
        "true_chemistry": { "type": "string", "enum": ["LFP", "NMC", "UNKNOWN"] },
        "true_soh": { "type": "number", "minimum": 0.0, "maximum": 1.2 },
        "true_r0_mohm": { "type": "number", "minimum": 0.0, "maximum": 500.0 },
        "true_capacity_ah": { "type": "number", "minimum": 0.0, "maximum": 100.0 },
        "true_thermal_coeff": { "type": "number" },
        "has_micro_short": { "type": "boolean" },
        "is_physically_damaged": { "type": "boolean" },
        "is_safe_for_second_life": { "type": "boolean" }
      },
      "required": ["specimen_id", "true_chemistry", "true_soh", "true_r0_mohm", "is_safe_for_second_life"]
    }
  }
}
```

---

## 3. High-Frequency Telemetry Record Schema (CSV / JSON)

*Stream Rate:* 100 Hz (Raw ADC), 10 Hz (Aggregated Host Telemetry).

| Column Name | Type | Unit | Description | Min Value | Max Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `timestamp_ms` | `uint32` | ms | Monotonic time since ESP32 boot | 0 | $2^{32}-1$ |
| `pack_voltage_v` | `float` | V | Total pack terminal voltage | 0.000 | 20.000 |
| `cell_1_voltage_v`| `float` | V | Cell 1 individual terminal voltage | 0.000 | 5.000 |
| `cell_2_voltage_v`| `float` | V | Cell 2 individual terminal voltage | 0.000 | 5.000 |
| `cell_3_voltage_v`| `float` | V | Cell 3 individual terminal voltage | 0.000 | 5.000 |
| `cell_4_voltage_v`| `float` | V | Cell 4 individual terminal voltage | 0.000 | 5.000 |
| `pack_current_a` | `float` | A | Shunt current (+ discharge, - charge) | -10.00 | +25.00 |
| `cell_temp_c` | `float` | °C | Pack surface temperature (DS18B20) | -10.0 | 85.0 |
| `ambient_temp_c` | `float` | °C | Ambient room temperature | -10.0 | 50.0 |
| `contactor_status`| `uint8` | binary | 1 = Energized/Closed, 0 = De-energized/Open | 0 | 1 |
| `hardware_trip_pin`|`uint8`| binary | 1 = Normal, 0 = Hardware Comparator Trip | 0 | 1 |

---

## 4. Bayesian Belief State Schema (`belief_state.json`)

Records the mathematical belief maintained by Layer 2B & Layer 2C:

```json
{
  "specimen_id": "CELL_001_NOMINAL_LFP",
  "diagnostic_step": 3,
  "chemistry_belief": {
    "P_LFP": 0.9982,
    "P_NMC": 0.0015,
    "P_UNKNOWN": 0.0003,
    "confidence_state": "KNOWN"
  },
  "state_estimates": {
    "soh": {
      "mean": 0.842,
      "variance": 0.00035,
      "std_dev": 0.0187,
      "precision": 2857.14
    },
    "r0_ohms": {
      "mean": 0.00241,
      "variance": 1.2e-8,
      "std_dev": 0.000109,
      "precision": 8.33e7
    }
  },
  "safety_risk": {
    "p_failure_conditional_lfp": 0.0018,
    "p_failure_conditional_nmc": 0.1240,
    "p_failure_marginal": 0.00198,
    "is_safety_barrier_admissible": true
  }
}
```

---

## 5. Qualification Audit Record Schema (`qualification_audit_record.json`)

Permanent immutable audit certificate emitted at qualification completion:

```json
{
  "audit_version": "1.0.0",
  "specimen_id": "CELL_001_NOMINAL_LFP",
  "qualification_timestamp_utc": "2026-10-02T16:53:00Z",
  "final_action": "OPERATE",
  "derating_factor": 1.0,
  "triage_summary": { "status": "PASS", "dwell_time_s": 2.0 },
  "chemistry_identified": "LFP",
  "final_soh_mean": 0.842,
  "final_r0_mohm": 2.41,
  "marginal_failure_risk": 0.00198,
  "tests_executed": ["REST_QUERY", "PULSE_5A", "CYCLE_TEST"],
  "total_testing_time_s": 127.0,
  "total_energy_consumed_wh": 14.8,
  "net_economic_value_inr": 2350.0,
  "hardware_trip_events": 0,
  "signed_hash": "a4f89b1c78e920d4e5f6..."
}
```
