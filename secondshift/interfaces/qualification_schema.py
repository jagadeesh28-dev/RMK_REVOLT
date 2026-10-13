"""
Canonical Qualification Data Model & Temporal Semantics (Layer 2 / 3)
Project: RMK-REVOLT / SECONDShift Platform

Defines the core experimental data hierarchy:
BATTERY
   └── QualificationSession
         ├── TestProtocol (Versioned specification)
         ├── TestSegment (CHARGE, REST, DISCHARGE, PULSE, HOLD)
         ├── Telemetry (Canonical stream references)
         ├── ValidationRecords (DataQualityRecord, PulseValidationRecord)
         ├── DerivedFeatures (With temporal provenance & leakage tracking)
         ├── Evidence (Inferred chemistry, Bayesian beliefs, state estimates)
         └── Decision (OperationalDecision, InformationAction, AuditRecord)

Invariants:
- Declared chemistry is NEVER conflated with inferred chemistry.
- Temporal provenance is mandatory: calculation window vs. decision timestamp.
- Future leakage is strictly detected and flagged (AVAILABLE_AT_DECISION_TIME vs FUTURE_INFORMATION).
- Feature quality != feature value: value = 0.0 is valid, value = None is unavailable.
  Zero is NEVER used as a generic missing-value encoding.
- Qualification data status is categorical: VALID, PARTIALLY_VALID, INVALID, INCOMPLETE.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Union
import time
import json
import math

from secondshift.interfaces.epistemic_schema import ReasonCode, DecisionAuditRecord
from secondshift.interfaces.data_quality_schema import (
    DataQualityRecord,
    PulseValidationRecord,
    DataQualityState
)


class SegmentType(str, Enum):
    """Canonical test segment types."""
    CHARGE = "CHARGE"
    REST = "REST"
    DISCHARGE = "DISCHARGE"
    PULSE = "PULSE"
    HOLD = "HOLD"


class SessionLifecycleStatus(str, Enum):
    """Deterministic lifecycle states for a qualification session."""
    CREATED = "CREATED"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    SAFE_STOP = "SAFE_STOP"
    ABORTED = "ABORTED"
    INVALID = "INVALID"


class QualificationDataStatus(str, Enum):
    """Categorical qualification dataset and segment validity."""
    VALID = "VALID"
    PARTIALLY_VALID = "PARTIALLY_VALID"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"


class TemporalLeakageStatus(str, Enum):
    """Flags whether a data object or feature respects decision-time causality."""
    AVAILABLE_AT_DECISION_TIME = "AVAILABLE_AT_DECISION_TIME"
    FUTURE_INFORMATION = "FUTURE_INFORMATION"
    UNCONSTRAINED = "UNCONSTRAINED"


class MeasurementScope(str, Enum):
    """
    Physical scope of measurement acquisition.
    Distinguishes single cell measurements from module- and pack-level aggregates.
    """
    CELL = "CELL"
    MODULE = "MODULE"
    PACK = "PACK"
    UNKNOWN = "UNKNOWN"



@dataclass
class BatteryRecord:
    """
    Canonical representation of a battery specimen under test.
    Preserves declared properties without conflating them with inference.
    """
    battery_id: str
    cell_id: Optional[str] = None
    declared_chemistry: str = "UNKNOWN"
    nominal_voltage: Optional[float] = None
    nominal_capacity_ah: Optional[float] = None
    format: Optional[str] = None          # e.g., "PRISMATIC", "CYLINDRICAL_21700", "POUCH"
    manufacturer: Optional[str] = None
    source: Optional[str] = None          # e.g., "INCOMING_INSPECTION", "FLEET_RETIREMENT"
    metadata: Dict[str, Any] = field(default_factory=dict)
    creation_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatteryRecord":
        nom_v = data.get("nominal_voltage")
        nom_cap = data.get("nominal_capacity_ah")
        return cls(
            battery_id=str(data["battery_id"]),
            cell_id=data.get("cell_id"),
            declared_chemistry=str(data.get("declared_chemistry", "UNKNOWN")),
            nominal_voltage=float(nom_v) if nom_v is not None else None,
            nominal_capacity_ah=float(nom_cap) if nom_cap is not None else None,
            format=data.get("format"),
            manufacturer=data.get("manufacturer"),
            source=data.get("source"),
            metadata=dict(data.get("metadata", {})),
            creation_timestamp=float(data.get("creation_timestamp", time.time()))
        )


@dataclass
class TestProtocol:
    """
    Formal, versioned experimental test protocol specification.
    Externalizes all experimental conditions, bounds, and termination criteria.
    """
    __test__ = False
    protocol_id: str = "QUAL_DEFAULT_V1"
    protocol_version: str = "1.0.0"
    name: str = "Standard SECONDShift Rapid Qualification"
    purpose: str = "Diagnostic qualification of retired second-life battery specimens"
    charge_conditions: Dict[str, Any] = field(default_factory=lambda: {"max_current_a": 5.0, "cutoff_v": 3.65})
    discharge_conditions: Dict[str, Any] = field(default_factory=lambda: {"current_a": 10.0, "cutoff_v": 2.50})
    rest_duration_s: float = 30.0
    pulse_current_a: float = 10.0
    pulse_duration_s: float = 10.0
    sampling_rate_hz: float = 10.0
    voltage_limits: Dict[str, float] = field(default_factory=lambda: {"min_v": 2.0, "max_v": 4.5})
    current_limits: Dict[str, float] = field(default_factory=lambda: {"min_a": -50.0, "max_a": 50.0})
    temperature_limits: Dict[str, float] = field(default_factory=lambda: {"min_c": -10.0, "max_c": 60.0})
    termination_criteria: List[str] = field(default_factory=lambda: ["MAX_ITERATIONS", "SAFETY_TRIP", "DECISION_FINALIZED"])
    safety_constraints: Dict[str, Any] = field(default_factory=lambda: {"lm393_hardware_protection": True, "thermal_snap": True})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestProtocol":
        return cls(
            protocol_id=str(data.get("protocol_id", "QUAL_DEFAULT_V1")),
            protocol_version=str(data.get("protocol_version", "1.0.0")),
            name=str(data.get("name", "Standard SECONDShift Rapid Qualification")),
            purpose=str(data.get("purpose", "")),
            charge_conditions=dict(data.get("charge_conditions", {})),
            discharge_conditions=dict(data.get("discharge_conditions", {})),
            rest_duration_s=float(data.get("rest_duration_s", 30.0)),
            pulse_current_a=float(data.get("pulse_current_a", 10.0)),
            pulse_duration_s=float(data.get("pulse_duration_s", 10.0)),
            sampling_rate_hz=float(data.get("sampling_rate_hz", 10.0)),
            voltage_limits=dict(data.get("voltage_limits", {})),
            current_limits=dict(data.get("current_limits", {})),
            temperature_limits=dict(data.get("temperature_limits", {})),
            termination_criteria=list(data.get("termination_criteria", [])),
            safety_constraints=dict(data.get("safety_constraints", {}))
        )


@dataclass
class TemporalProvenance:
    """
    Tracks the exact physical time interval used to compute a derived metric,
    and enforces future-leakage causality checks against decision timestamps.
    """
    calculation_timestamp: float = field(default_factory=time.time)
    observation_window_start: float = 0.0
    observation_window_end: float = 0.0
    decision_timestamp: Optional[float] = None
    leakage_status: str = TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value

    def check_leakage(self, decision_timestamp: float) -> bool:
        """
        Validates whether the observation window strictly precedes or equals the decision timestamp.
        Returns True if causality holds, False if future leakage is detected.
        Never silently truncates; flags as FUTURE_INFORMATION.
        """
        self.decision_timestamp = decision_timestamp
        if self.observation_window_end > (decision_timestamp + 1e-4):
            self.leakage_status = TemporalLeakageStatus.FUTURE_INFORMATION.value
            return False
        self.leakage_status = TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemporalProvenance":
        return cls(
            calculation_timestamp=float(data.get("calculation_timestamp", time.time())),
            observation_window_start=float(data.get("observation_window_start", 0.0)),
            observation_window_end=float(data.get("observation_window_end", 0.0)),
            decision_timestamp=float(data["decision_timestamp"]) if data.get("decision_timestamp") is not None else None,
            leakage_status=str(data.get("leakage_status", TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value))
        )


@dataclass
class DerivedFeature:
    """
    Canonical interface contract for derived electrochemical features.
    Provides complete lineage: source session, source segment, calculation window,
    causality verification, and configuration version.

    Rule: value = 0.0 is a valid measurement; value = None means unavailable or invalid.
    """
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
    quality_status: str = DataQualityState.VALID.value
    configuration_version: str = "2.0.0"
    measurement_scope: str = MeasurementScope.CELL.value
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_admissible(self) -> bool:
        """
        Validates whether the feature is admissible for downstream decision-making.
        Returns True if and only if:
        1. Feature value is physically valid (not None),
        2. Quality status is VALID, and
        3. Temporal provenance confirms availability at decision time (no future leakage).
        """
        return (
            self.value is not None
            and self.quality_status == DataQualityState.VALID.value
            and self.temporal_provenance.leakage_status == TemporalLeakageStatus.AVAILABLE_AT_DECISION_TIME.value
        )

    def validate_against_decision_time(self, decision_timestamp: float) -> bool:
        """
        Validates temporal causality against the decision timestamp.
        If future leakage is detected (observation_window_end > decision_timestamp),
        sets leakage_status to FUTURE_INFORMATION, transitions quality_status to INVALID,
        and returns False to block consumption by downstream models or decision gates.
        """
        causal = self.temporal_provenance.check_leakage(decision_timestamp)
        if not causal:
            self.quality_status = DataQualityState.INVALID.value
            return False
        return self.is_admissible

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_version": self.feature_version,
            "value": self.value,
            "unit": self.unit,
            "source_session": self.source_session,
            "source_segment": self.source_segment,
            "source_measurements": self.source_measurements,
            "temporal_provenance": self.temporal_provenance.to_dict(),
            "physical_meaning": self.physical_meaning,
            "expected_direction": self.expected_direction,
            "quality_status": self.quality_status,
            "configuration_version": self.configuration_version,
            "measurement_scope": self.measurement_scope,
            "context": dict(self.context)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DerivedFeature":
        tp_raw = data.get("temporal_provenance", {})
        tp = TemporalProvenance.from_dict(tp_raw) if isinstance(tp_raw, dict) else tp_raw
        val = data.get("value")
        return cls(
            feature_name=str(data["feature_name"]),
            feature_version=str(data.get("feature_version", "1.0.0")),
            value=float(val) if val is not None and not math.isnan(val) else None,
            unit=str(data.get("unit", "")),
            source_session=str(data.get("source_session", "")),
            source_segment=data.get("source_segment"),
            source_measurements=list(data.get("source_measurements", [])),
            temporal_provenance=tp,
            physical_meaning=str(data.get("physical_meaning", "")),
            expected_direction=data.get("expected_direction"),
            quality_status=str(data.get("quality_status", DataQualityState.VALID.value)),
            configuration_version=str(data.get("configuration_version", "2.0.0")),
            measurement_scope=str(data.get("measurement_scope", MeasurementScope.CELL.value)),
            context=dict(data.get("context", {}))
        )


@dataclass
class TestSegment:
    """
    Canonical representation of a single physical test step.
    A segment is NOT automatically valid because it exists; its validity depends on
    admissibility verification (e.g. current flow, contactor status).
    """
    __test__ = False
    segment_id: str
    session_id: str
    segment_type: str = SegmentType.REST.value
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    validation_status: str = QualificationDataStatus.VALID.value
    telemetry_references: List[str] = field(default_factory=list)
    reason_codes: List[ReasonCode] = field(default_factory=list)
    validation_record: Optional[Union[PulseValidationRecord, DataQualityRecord]] = None

    def mark_invalid(self, reason: ReasonCode):
        """Explicitly transitions segment to INVALID status with reason code."""
        self.validation_status = QualificationDataStatus.INVALID.value
        if reason not in self.reason_codes:
            self.reason_codes.append(reason)

    def to_dict(self) -> Dict[str, Any]:
        val_rec_dict = None
        if self.validation_record and hasattr(self.validation_record, "to_dict"):
            val_rec_dict = self.validation_record.to_dict()

        return {
            "segment_id": self.segment_id,
            "session_id": self.session_id,
            "segment_type": self.segment_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "configuration": self.configuration,
            "validation_status": self.validation_status,
            "telemetry_references": self.telemetry_references,
            "reason_codes": [rc.value if isinstance(rc, ReasonCode) else str(rc) for rc in self.reason_codes],
            "validation_record": val_rec_dict
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestSegment":
        def _parse_reasons(raw: Any) -> List[ReasonCode]:
            res = []
            if isinstance(raw, list):
                for c in raw:
                    if isinstance(c, ReasonCode):
                        res.append(c)
                    elif isinstance(c, str):
                        try:
                            res.append(ReasonCode(c))
                        except ValueError:
                            pass
            return res

        vr_raw = data.get("validation_record")
        vr = None
        if isinstance(vr_raw, dict):
            if "pulse_valid" in vr_raw:
                vr = PulseValidationRecord.from_dict(vr_raw)
            elif "sensor_valid" in vr_raw:
                vr = DataQualityRecord.from_dict(vr_raw)

        return cls(
            segment_id=str(data["segment_id"]),
            session_id=str(data["session_id"]),
            segment_type=str(data.get("segment_type", SegmentType.REST.value)),
            start_time=float(data.get("start_time", time.time())),
            end_time=float(data["end_time"]) if data.get("end_time") is not None else None,
            configuration=dict(data.get("configuration", {})),
            validation_status=str(data.get("validation_status", QualificationDataStatus.VALID.value)),
            telemetry_references=list(data.get("telemetry_references", [])),
            reason_codes=_parse_reasons(data.get("reason_codes", [])),
            validation_record=vr
        )


@dataclass
class InferredChemistryRecord:
    """
    Separates inferred chemistry, belief distribution, and confidence from declared chemistry.
    """
    inferred_chemistry: Optional[str] = None
    confidence_state: str = "NOT_YET_ESTIMATED"  # "NOT_YET_ESTIMATED", "KNOWN", "AMBIGUOUS", "UNKNOWN"
    posterior: Dict[str, float] = field(default_factory=lambda: {"LFP": 0.5, "NMC": 0.5, "UNKNOWN": 0.0})
    confidence_score: Optional[float] = None
    evidence_sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InferredChemistryRecord":
        return cls(
            inferred_chemistry=data.get("inferred_chemistry"),
            confidence_state=str(data.get("confidence_state", "NOT_YET_ESTIMATED")),
            posterior=dict(data.get("posterior", {"LFP": 0.5, "NMC": 0.5, "UNKNOWN": 0.0})),
            confidence_score=float(data["confidence_score"]) if data.get("confidence_score") is not None else None,
            evidence_sources=list(data.get("evidence_sources", []))
        )


@dataclass
class QualificationSession:
    """
    Top-level canonical qualification entity coordinating the battery,
    the active protocol, executed segments, and evidence collection.
    """
    session_id: str
    battery_id: str
    protocol_id: str = "QUAL_DEFAULT_V1"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    operator: str = "AUTOMATED_HERMES_RUNNER"
    dataset_version: str = "2.0.0"
    software_version: str = "SECONDShift-v2.0"
    configuration_version: str = "2.0.0"
    status: str = SessionLifecycleStatus.CREATED.value

    battery_record: Optional[BatteryRecord] = None
    protocol: Optional[TestProtocol] = None
    segments: List[TestSegment] = field(default_factory=list)
    overall_data_status: str = QualificationDataStatus.VALID.value

    # Evidence & Estimates (None if unavailable/unimplemented; never fake values)
    inferred_chemistry_record: InferredChemistryRecord = field(default_factory=InferredChemistryRecord)
    soh_estimate: Optional[float] = None
    soh_uncertainty: Optional[float] = None
    r0_mohm_estimate: Optional[float] = None
    r0_mohm_uncertainty: Optional[float] = None

    # Prognostic Placeholders (Explicitly None / Not Yet Implemented)
    rul_cycles_estimate: Optional[float] = None
    rul_uncertainty: Optional[float] = None
    prognostic_status: str = "NOT_YET_IMPLEMENTED"

    derived_features: List[DerivedFeature] = field(default_factory=list)
    audit_record: Optional[DecisionAuditRecord] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Lifecycle Methods
    def arm(self):
        """Arms session for physical actuation."""
        if self.status != SessionLifecycleStatus.CREATED.value:
            raise ValueError(f"Cannot arm session from status {self.status}")
        self.status = SessionLifecycleStatus.ARMED.value

    def start(self):
        """Starts active qualification testing."""
        self.start_time = time.time()
        self.status = SessionLifecycleStatus.RUNNING.value

    def add_segment(self, segment: TestSegment):
        """Appends an executed test segment and updates aggregate data status."""
        self.segments.append(segment)
        if segment.validation_status == QualificationDataStatus.INVALID.value:
            if self.overall_data_status == QualificationDataStatus.VALID.value:
                self.overall_data_status = QualificationDataStatus.PARTIALLY_VALID.value

    def complete(self):
        """Finalizes qualification session successfully."""
        self.end_time = time.time()
        self.status = SessionLifecycleStatus.COMPLETED.value

    def safe_stop(self, reason: str = "PROTECTION_TRIGGERED"):
        """Halts testing safely under hardware trip or safety threshold breach."""
        self.end_time = time.time()
        self.status = SessionLifecycleStatus.SAFE_STOP.value
        self.metadata["safe_stop_reason"] = reason

    def abort(self, reason: str = "OPERATOR_ABORT"):
        """Aborts testing prematurely."""
        self.end_time = time.time()
        self.status = SessionLifecycleStatus.ABORTED.value
        self.metadata["abort_reason"] = reason

    def get_admissible_features(self, decision_timestamp: float) -> List[DerivedFeature]:
        """
        Extracts derived features causally admissible at decision_timestamp.
        Strictly filters out and rejects any feature containing FUTURE_INFORMATION or invalid data.
        """
        return [f for f in self.derived_features if f.validate_against_decision_time(decision_timestamp)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "battery_id": self.battery_id,
            "protocol_id": self.protocol_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "operator": self.operator,
            "dataset_version": self.dataset_version,
            "software_version": self.software_version,
            "configuration_version": self.configuration_version,
            "status": self.status,
            "battery_record": self.battery_record.to_dict() if self.battery_record else None,
            "protocol": self.protocol.to_dict() if self.protocol else None,
            "segments": [s.to_dict() for s in self.segments],
            "overall_data_status": self.overall_data_status,
            "inferred_chemistry_record": self.inferred_chemistry_record.to_dict(),
            "soh_estimate": self.soh_estimate,
            "soh_uncertainty": self.soh_uncertainty,
            "r0_mohm_estimate": self.r0_mohm_estimate,
            "r0_mohm_uncertainty": self.r0_mohm_uncertainty,
            "rul_cycles_estimate": self.rul_cycles_estimate,
            "rul_uncertainty": self.rul_uncertainty,
            "prognostic_status": self.prognostic_status,
            "derived_features": [f.to_dict() for f in self.derived_features],
            "audit_record": self.audit_record.to_dict() if self.audit_record else None,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualificationSession":
        bat = BatteryRecord.from_dict(data["battery_record"]) if data.get("battery_record") else None
        proto = TestProtocol.from_dict(data["protocol"]) if data.get("protocol") else None
        segs = [TestSegment.from_dict(s) for s in data.get("segments", [])]
        feats = [DerivedFeature.from_dict(f) for f in data.get("derived_features", [])]
        chem = InferredChemistryRecord.from_dict(data.get("inferred_chemistry_record", {}))
        audit = DecisionAuditRecord.from_dict(data["audit_record"]) if data.get("audit_record") else None

        return cls(
            session_id=str(data["session_id"]),
            battery_id=str(data["battery_id"]),
            protocol_id=str(data.get("protocol_id", "QUAL_DEFAULT_V1")),
            start_time=float(data.get("start_time", time.time())),
            end_time=float(data["end_time"]) if data.get("end_time") is not None else None,
            operator=str(data.get("operator", "AUTOMATED_HERMES_RUNNER")),
            dataset_version=str(data.get("dataset_version", "2.0.0")),
            software_version=str(data.get("software_version", "SECONDShift-v2.0")),
            configuration_version=str(data.get("configuration_version", "2.0.0")),
            status=str(data.get("status", SessionLifecycleStatus.CREATED.value)),
            battery_record=bat,
            protocol=proto,
            segments=segs,
            overall_data_status=str(data.get("overall_data_status", QualificationDataStatus.VALID.value)),
            inferred_chemistry_record=chem,
            soh_estimate=float(data["soh_estimate"]) if data.get("soh_estimate") is not None else None,
            soh_uncertainty=float(data["soh_uncertainty"]) if data.get("soh_uncertainty") is not None else None,
            r0_mohm_estimate=float(data["r0_mohm_estimate"]) if data.get("r0_mohm_estimate") is not None else None,
            r0_mohm_uncertainty=float(data["r0_mohm_uncertainty"]) if data.get("r0_mohm_uncertainty") is not None else None,
            rul_cycles_estimate=float(data["rul_cycles_estimate"]) if data.get("rul_cycles_estimate") is not None else None,
            rul_uncertainty=float(data["rul_uncertainty"]) if data.get("rul_uncertainty") is not None else None,
            prognostic_status=str(data.get("prognostic_status", "NOT_YET_IMPLEMENTED")),
            derived_features=feats,
            audit_record=audit,
            metadata=dict(data.get("metadata", {}))
        )
