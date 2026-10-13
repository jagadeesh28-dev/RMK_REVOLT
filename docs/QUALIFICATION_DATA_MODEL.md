# Canonical Qualification Data Model & Temporal Semantics

**Project**: RMK-REVOLT / SECONDShift Platform  
**Document**: `docs/QUALIFICATION_DATA_MODEL.md`  
**Phase**: Phase 3 — Qualification Data Model + Dashboard Integration  
**Status**: AUDITED & SCIENTIFICALLY FROZEN (Phase 3 Final Acceptance)  

---

## 1. Executive Summary

In battery diagnostic research and remanufacturing qualification, computing features or making operational decisions on unstructured, raw telemetry without temporal provenance leads to scientific invalidity, data leakage, and unexplainable inferences.

Phase 3 establishes the canonical qualification data model for the SECONDShift platform. It formally defines:
1. **The Experimental Entity Hierarchy**:
   $$\text{BatteryRecord} \longrightarrow \text{QualificationSession} \longrightarrow \{\text{TestProtocol}, \text{TestSegment}, \text{Telemetry}, \text{ValidationRecords}, \text{DerivedFeatures}, \text{Evidence}, \text{Decision}\}$$
2. **Strict Separation of Declared vs. Inferred Properties**: Specimen intake metadata (e.g. declared chemistry) is permanently isolated from posterior beliefs and inferred parameters.
3. **Temporal Provenance & Causality**: Every derived feature and estimate explicitly records its observation interval $[t_{\text{start}}, t_{\text{end}}]$ and validates against the decision timestamp $t_{\text{decision}}$ to prevent future-information leakage.
4. **Categorical Validity & Non-Zero Missing Semantics**: Missing or invalid measurements are encoded as `None` (`NOT_AVAILABLE`), never coerced to `0` or `0.0`. Valid measured zeros are preserved as `0.0`.

---

## 2. Experimental Data Hierarchy

```
BATTERY (BatteryRecord)
   │
   └── QualificationSession
         ├── TestProtocol (Versioned specification)
         │
         ├── TestSegment (CHARGE | REST | DISCHARGE | PULSE | HOLD)
         │     ├── Segment configuration
         │     ├── Validation status (VALID | INVALID | PARTIALLY_VALID)
         │     └── ValidationRecord (PulseValidationRecord | DataQualityRecord)
         │
         ├── Telemetry Streams (Canonical voltage, current, temp, power, sequence)
         │
         ├── ValidationRecords (DataQualityRecord, PulseValidationRecord)
         │
         ├── DerivedFeatures (Feature provenance, units, physical meaning, window)
         │
         ├── Evidence (InferredChemistryRecord, Bayesian posterior beliefs)
         │
         └── Decision (OperationalDecision, InformationAction, DecisionAuditRecord)
```

---

## 3. Canonical Entities & Data Contracts

### 3.1 `BatteryRecord`
Represents the physical battery or cell specimen under test.

| Field | Type | Description |
|---|---|---|
| `battery_id` | `str` | Unique serial/lot identifier of battery pack or module. |
| `cell_id` | `Optional[str]` | Optional constituent cell index if instrumented. |
| `declared_chemistry` | `str` | Intake label (e.g. `"LFP"`, `"NMC"`, `"UNKNOWN"`). Never overwritten. |
| `nominal_voltage` | `Optional[float]` | Declared nameplate voltage (V) or `None` if unspecified. Never defaulted to arbitrary chemistry values. |
| `nominal_capacity_ah` | `Optional[float]` | Declared nameplate capacity (Ah) or `None` if unspecified. Never defaulted. |
| `format` | `Optional[str]` | Form factor (e.g. `"PRISMATIC"`, `"CYLINDRICAL_21700"`, `"POUCH"`). |
| `manufacturer` | `Optional[str]` | Known cell/pack manufacturer. |
| `source` | `Optional[str]` | Provenance intake (e.g. `"FLEET_RETIREMENT"`, `"INCOMING_INSPECTION"`). |
| `metadata` | `Dict[str, Any]` | Extensible dictionary for intake operator notes and visual inspection. |
| `creation_timestamp` | `float` | Epoch timestamp of specimen ingestion. |

**Invariant**: Declared chemistry is NEVER conflated with inferred chemistry. Intake metadata is immutable across diagnostic cycles. Missing intake attributes remain explicitly `None` and never become implicit production defaults.

---

### 3.2 `TestProtocol`
Represents the formal, versioned recipe governing physical qualification on the bench.

| Field | Type | Description |
|---|---|---|
| `protocol_id` | `str` | Stable identifier (e.g. `"QUAL_BENCH_RAPID_V2"`). |
| `protocol_version` | `str` | Semantic version string (e.g. `"2.0.0"`). |
| `name` | `str` | Descriptive protocol title. |
| `purpose` | `str` | Scientific or operational objective of characterization. |
| `charge_conditions` | `Dict[str, Any]` | Voltage cutoff, maximum current, CC-CV termination. |
| `discharge_conditions` | `Dict[str, Any]` | Cutoff voltage, C-rate, duration. |
| `rest_duration_s` | `float` | Minimum open-circuit relaxation duration. |
| `pulse_current_a` | `float` | Target excitation current amplitude. |
| `pulse_duration_s` | `float` | Transient excitation window length. |
| `sampling_rate_hz` | `float` | Bench ADC telemetry sample acquisition frequency. |
| `voltage_limits` | `Dict[str, float]` | Safe operating voltage window (`min_v`, `max_v`). |
| `current_limits` | `Dict[str, float]` | Current envelope bounds (`min_a`, `max_a`). |
| `temperature_limits` | `Dict[str, float]` | Thermal boundaries (`min_c`, `max_c`). |
| `termination_criteria` | `List[str]` | Explicit stopping rules (e.g. `["MAX_ITERATIONS", "SAFETY_TRIP"]`). |
| `safety_constraints` | `Dict[str, Any]` | Hardware interlocks and supervisor trip parameters. |

**Invariant**: Protocol bounds and tolerances must never be buried in Python function bodies. All experimental assumptions are externalized and versioned.

---

### 3.3 `TestSegment`
Represents an individual physical step executed during qualification.

Supported segment types (`SegmentType`):
- `CHARGE`: Active coulometric charging phase.
- `REST`: Passive zero-current relaxation phase (monitoring OCV drift / self-discharge).
- `DISCHARGE`: Constant current or constant power capacity discharge.
- `PULSE`: Diagnostic excitation pulse for transient impedance extraction.
- `HOLD`: Static voltage or current hold phase.

| Field | Type | Description |
|---|---|---|
| `segment_id` | `str` | Unique segment identifier (e.g. `"SEG_PULSE_01"`). |
| `session_id` | `str` | Parent qualification session ID. |
| `segment_type` | `str` | Value from `SegmentType`. |
| `start_time` | `float` | Physical timestamp when segment started. |
| `end_time` | `Optional[float]` | Physical timestamp when segment concluded. |
| `configuration` | `Dict[str, Any]` | Step-specific setpoints (current, duration, thresholds). |
| `validation_status` | `str` | Categorical status (`VALID`, `INVALID`, `PARTIALLY_VALID`). |
| `telemetry_references`| `List[str]` | IDs or sample indices of recorded telemetry. |
| `reason_codes` | `List[ReasonCode]` | Explicit failure or admissibility reasons if invalid. |
| `validation_record` | `Optional[Union[...]]`| Attached `PulseValidationRecord` or `DataQualityRecord`. |

**Invariant**: A segment is NOT valid simply because it was executed. For example, a `PULSE` segment where contactors opened or $I < I_{\text{MIN}}$ transitions to `validation_status = "INVALID"` and logs `CURRENT_FLOW_BELOW_MINIMUM`.

---

### 3.4 `QualificationSession`
The aggregate root orchestrating the qualification lifecycle.

Deterministic lifecycle states (`SessionLifecycleStatus`):
```
CREATED  ──>  ARMED  ──>  RUNNING  ──>  VALIDATING  ──>  COMPLETED
                           │   │
                           │   └──>  SAFE_STOP (Safety barrier trip)
                           │
                           └──>  ABORTED (Operator or communications abort)
```

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | Unique session run identifier. |
| `battery_id` | `str` | Target specimen identifier. |
| `protocol_id` | `str` | Active test protocol. |
| `status` | `str` | Value from `SessionLifecycleStatus`. |
| `battery_record` | `Optional[BatteryRecord]` | Linked specimen entity. |
| `protocol` | `Optional[TestProtocol]` | Versioned experimental parameters. |
| `segments` | `List[TestSegment]` | Ordered list of executed physical test segments. |
| `overall_data_status`| `str` | Aggregate status (`VALID`, `PARTIALLY_VALID`, `INVALID`, `INCOMPLETE`). |
| `inferred_chemistry_record` | `InferredChemistryRecord` | Posterior chemistry estimation and confidence. |
| `soh_estimate` | `Optional[float]` | Posterior SOH ($0.0 \le \mu \le 1.0$), or `None` if unmeasured. |
| `soh_uncertainty` | `Optional[float]` | SOH standard deviation $\sigma$, or `None`. |
| `r0_mohm_estimate` | `Optional[float]` | Ohmic internal resistance in $\text{m}\Omega$, or `None`. |
| `rul_cycles_estimate` | `Optional[float]` | `None` in Phase 3 (RUL models not yet implemented). |
| `prognostic_status`| `str` | `"NOT_YET_IMPLEMENTED"` in Phase 3. |
| `derived_features` | `List[DerivedFeature]` | Features derived with full temporal provenance. |
| `audit_record` | `Optional[DecisionAuditRecord]` | Complete decision explanation and audit record. |

---

## 4. Temporal Provenance & Future-Leakage Prevention

### 4.1 Causality Contract
A feature, state estimate, or evidence item calculated at decision time $t_{\text{decision}}$ may only consume telemetry whose physical observation interval satisfies:

$$t_{\text{end}} \le t_{\text{decision}} + \epsilon \quad (\epsilon = 10^{-4}\,\text{s})$$

If $t_{\text{end}} > t_{\text{decision}}$, the feature accesses future information:
$$\text{leakage\_status} = \text{FUTURE\_INFORMATION}$$

### 4.2 Non-Truncation & Inadmissibility Principle
When future data is present, the system MUST NOT silently truncate timestamps to simulate causality. The qualification data model detects and explicitly marks future-information provenance violations, sets `quality_status = INVALID`, and prevents them from being silently treated as valid observations by downstream models or decision gates.

*(Scientific Scope Note: We claim that the data model detects and explicitly flags future-information violations and rejects them via the admissibility contract; we do NOT claim universal formal verification across all possible external consumer implementations).*

---

## 5. Feature Provenance Contract (`DerivedFeature`)

Derived features (e.g. $\Delta V$, differential capacity $dQ/dV$, thermal slope $dT/dt$) adhere to the `DerivedFeature` interface:

```python
@dataclass
class DerivedFeature:
    feature_name: str
    feature_version: str = "1.0.0"
    value: Optional[float] = None
    unit: str = ""
    source_session: str = ""
    source_segment: Optional[str] = None
    source_measurements: List[str] = field(default_factory=list)
    temporal_provenance: TemporalProvenance = field(default_factory=TemporalProvenance)
    physical_meaning: str = ""
    expected_direction: Optional[str] = None  # e.g., "INCREASING_WITH_DEGRADATION"
    quality_status: str = "VALID"
    configuration_version: str = "2.0.0"

    @property
    def is_admissible(self) -> bool:
        """Admissible iff value is not None, quality_status is VALID, and no future leakage."""
        return (
            self.value is not None
            and self.quality_status == DataQualityState.VALID.value
            and self.temporal_provenance.leakage_status == TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value
        )

    def validate_against_decision_time(self, decision_timestamp: float) -> bool:
        """Validates causality against decision_timestamp. Transitions to INVALID if future info."""
        causal = self.temporal_provenance.check_leakage(decision_timestamp)
        if not causal:
            self.quality_status = DataQualityState.INVALID.value
            return False
        return self.is_admissible
```

### 5.1 Session Admissibility Filtering
`QualificationSession.get_admissible_features(decision_timestamp)` evaluates all attached derived features against $t_{\text{decision}}$, actively rejecting any feature flagged as `FUTURE_INFORMATION` or possessing `quality_status != VALID`.

### 5.2 Value vs. Quality Invariant
- `value = 0.0`: A valid, physically measured zero quantity (e.g. net polarization under zero current is $0.0\,\text{V}$).
- `value = None`: The measurement was invalid, sub-threshold, or unavailable.
- **Rule**: `0.0` is NEVER used as a substitute for `None` / missing data.

