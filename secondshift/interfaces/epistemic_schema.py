"""
Canonical Epistemic & Operational Decision Contracts (Layer 5)
Project: RMK-REVOLT / SECONDShift Platform

Defines the absolute semantic separation between:
1. EPISTEMIC STATE: "What does the system know / believe about the battery?"
2. OPERATIONAL DECISION: "What is the system authorized to do with the battery?"
3. INFORMATION ACTION: "Should we acquire more diagnostic test information?"

NON-NEGOTIABLE PRINCIPLE:
    SAFETY CONSTRAINT >> ECONOMIC OPTIMIZATION
    KNOW WHAT YOU KNOW. KNOW WHAT YOU DON'T KNOW. NEVER OPTIMIZE SAFETY AWAY.

INVARIANT:
    KNWOWN_GOOD is strictly prohibited. Absence of evidence of degradation
    is NOT evidence of health.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional
import json
import time


class EpistemicState(str, Enum):
    """
    Epistemic belief state representing what the qualification platform
    currently knows / believes about the battery pack based on gathered evidence.

    IMPORTANT:
    - SUPPORTED_HEALTHY does NOT mean 'guaranteed healthy'. It means available evidence
      supports the healthy interpretation within the validated operating domain.
    - KNOWN_GOOD is explicitly PROHIBITED because absence of evidence of degradation
      is not equivalent to known good.
    """
    SUPPORTED_HEALTHY = "SUPPORTED_HEALTHY"
    UNCERTAIN = "UNCERTAIN"
    DISTRIBUTION_SHIFTED = "DISTRIBUTION_SHIFTED"
    KNOWN_DEGRADED = "KNOWN_DEGRADED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class OperationalDecision(str, Enum):
    """
    Operational decision representing what the system authorizes to be done with the battery.

    This is STRICTLY SEPARATE from epistemic belief state.
    Safety constraints always override economic optimization.
    """
    OPERATE = "OPERATE"
    DERATE = "DERATE"
    HOLD = "HOLD"
    RETIRE = "RETIRE"


class InformationAction(str, Enum):
    """
    Diagnostic information acquisition decision representing whether the system
    recommends executing an additional test.

    This is STRICTLY SEPARATE from the operational decision.
    Prevents 'TEST' from masquerading as an operational action.
    """
    NO_TEST = "NO_TEST"
    REQUEST_TEST = "REQUEST_TEST"


class ReasonCode(str, Enum):
    """
    Controlled machine-readable and human-explainable reason codes explaining
    why an epistemic state, operational decision, or information action was assigned.
    """
    # Deterministic Triage & Hardware Safety
    TRIAGE_REJECTED = "TRIAGE_REJECTED"
    TRIAGE_HOLD = "TRIAGE_HOLD"
    SAFETY_LIMIT_EXCEEDED = "SAFETY_LIMIT_EXCEEDED"
    HARD_SAFETY_BARRIER_TRIP = "HARD_SAFETY_BARRIER_TRIP"
    ANALOG_INTERLOCK_TRIP = "ANALOG_INTERLOCK_TRIP"

    # Data Quality & Telemetry
    MEASUREMENT_INVALID = "MEASUREMENT_INVALID"
    SENSOR_FAULT = "SENSOR_FAULT"
    TELEMETRY_STALE = "TELEMETRY_STALE"
    DATA_QUALITY_DEGRADED = "DATA_QUALITY_DEGRADED"

    # Chemistry & Domain Disambiguation
    CHEMISTRY_UNCERTAIN = "CHEMISTRY_UNCERTAIN"
    CHEMISTRY_CONFIRMED = "CHEMISTRY_CONFIRMED"
    CHEMISTRY_INCOMPATIBLE = "CHEMISTRY_INCOMPATIBLE"

    # State Estimation & Uncertainty
    HIGH_SOH_UNCERTAINTY = "HIGH_SOH_UNCERTAINTY"
    HIGH_R0_UNCERTAINTY = "HIGH_R0_UNCERTAINTY"
    STATE_UNCERTAINTY_ACCEPTABLE = "STATE_UNCERTAINTY_ACCEPTABLE"

    # Prognostics & Identifiability
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    PROGNOSTIC_IDENTIFIABILITY_LOW = "PROGNOSTIC_IDENTIFIABILITY_LOW"
    HIGH_RUL_UNCERTAINTY = "HIGH_RUL_UNCERTAINTY"
    MODEL_DISAGREEMENT = "MODEL_DISAGREEMENT"

    # Evidence & Regimes
    DISTRIBUTION_SHIFT_DETECTED = "DISTRIBUTION_SHIFT_DETECTED"
    KNOWN_DEGRADATION = "KNOWN_DEGRADATION"
    SUPPORTED_EVIDENCE = "SUPPORTED_EVIDENCE"

    # Value of Information & Diagnostic Testing
    ADDITIONAL_TEST_VALUE_HIGH = "ADDITIONAL_TEST_VALUE_HIGH"
    NO_ADDITIONAL_TEST_VALUE = "NO_ADDITIONAL_TEST_VALUE"
    TESTING_BUDGET_EXHAUSTED = "TESTING_BUDGET_EXHAUSTED"

    # Measurement Admissibility & Pulse Validation (Phase 2)
    CURRENT_FLOW_BELOW_MINIMUM = "CURRENT_FLOW_BELOW_MINIMUM"
    HARDWARE_TRIP_DURING_TEST = "HARDWARE_TRIP_DURING_TEST"
    CONTACTOR_OPEN_FAULT = "CONTACTOR_OPEN_FAULT"
    TRANSIENT_DURATION_INSUFFICIENT = "TRANSIENT_DURATION_INSUFFICIENT"
    TIMESTAMP_INVERSION = "TIMESTAMP_INVERSION"
    DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP"
    SEQUENCE_GAP_DETECTED = "SEQUENCE_GAP_DETECTED"
    PULSE_VALID = "PULSE_VALID"
    PULSE_INVALID = "PULSE_INVALID"


@dataclass
class DecisionAuditRecord:
    """
    Complete strongly-typed audit trail capturing the end-to-end rationale
    for an epistemic belief state, information action, and operational decision.

    Guarantees:
    - No fake data: Nullable fields for unmodeled upstream modules remain None.
    - Zero future leakage: Audits snapshot only information available at decision timestamp.
    """
    # IDENTITY
    battery_id: str
    test_id: str
    timestamp: float
    software_version: str
    configuration_version: str

    # DATA
    data_quality: str
    sensor_valid: bool
    telemetry_status: str

    # CHEMISTRY
    chemistry_belief: Dict[str, float]
    chemistry_confidence_state: Optional[str] = None

    # STATE
    soh_estimate: float = 0.0
    soh_uncertainty: float = 0.0
    r0_estimate: float = 0.0
    r0_uncertainty: float = 0.0

    # PROGNOSTICS (Nullable - RUL engine does not yet exist; never coerce to 0)
    rul_estimate: Optional[float] = None
    rul_uncertainty: Optional[float] = None

    # EVIDENCE (Nullable - modules do not yet exist; never invent dummy scores)
    anomaly_status: Optional[str] = None
    distribution_status: Optional[str] = None
    prognostic_identifiability: Optional[str] = None
    degradation_regime: Optional[str] = None

    # SAFETY
    safety_barrier_status: str = "PASS"
    safety_reason_codes: List[ReasonCode] = field(default_factory=list)

    # DECISION
    epistemic_state: EpistemicState = EpistemicState.INSUFFICIENT_DATA
    operational_decision: OperationalDecision = OperationalDecision.HOLD
    information_action: InformationAction = InformationAction.NO_TEST
    reason_codes: List[ReasonCode] = field(default_factory=list)

    # AUDIT
    decision_trace: Optional[List[Dict[str, Any]]] = None
    model_version: Optional[str] = None
    feature_version: Optional[str] = None

    def validate_invariants(self) -> List[str]:
        """
        Validates core decision invariants. Returns a list of error descriptions.
        An empty list indicates all invariants are satisfied.
        """
        errors: List[str] = []

        # INVARIANT 1: OperationalDecision cannot be TEST
        # (Enforced by enum, but checked against raw values if bypassed)
        if not isinstance(self.operational_decision, OperationalDecision):
            try:
                op_val = OperationalDecision(self.operational_decision)
            except ValueError:
                errors.append(f"INVARIANT 1 VIOLATION: OperationalDecision '{self.operational_decision}' is invalid (cannot be TEST).")

        # INVARIANT 2: InformationAction must be NO_TEST or REQUEST_TEST
        if not isinstance(self.information_action, InformationAction):
            try:
                info_val = InformationAction(self.information_action)
            except ValueError:
                errors.append(f"INVARIANT 2 VIOLATION: InformationAction '{self.information_action}' is invalid.")

        # INVARIANT 3: KNOWN_GOOD must not exist
        for state in EpistemicState:
            if "GOOD" in state.value.upper():
                errors.append("INVARIANT 3 VIOLATION: KNOWN_GOOD exists in EpistemicState enum!")

        # INVARIANT 4: If sensor/data validity is unsafe, system CANNOT OPERATE
        if not self.sensor_valid or self.telemetry_status in ["FAULT", "COMMUNICATION_FAULT", "SENSOR_FAULT"]:
            if self.operational_decision == OperationalDecision.OPERATE:
                errors.append(
                    f"INVARIANT 4 VIOLATION: OperationalDecision cannot be OPERATE when sensor_valid={self.sensor_valid} "
                    f"and telemetry_status='{self.telemetry_status}'."
                )

        # INVARIANT 5: Missing RUL cannot automatically mean RUL = 0
        if self.rul_estimate == 0.0 and self.rul_uncertainty is None:
            errors.append("INVARIANT 5 VIOLATION: Missing RUL must be None, not 0.0 placeholder.")

        # INVARIANT 6: Missing evidence cannot automatically mean SUPPORTED_HEALTHY
        if self.epistemic_state == EpistemicState.SUPPORTED_HEALTHY:
            if self.soh_estimate <= 0.0 and self.r0_estimate <= 0.0:
                errors.append("INVARIANT 6 VIOLATION: Missing state evidence cannot be SUPPORTED_HEALTHY.")
            if self.soh_uncertainty >= 0.10:
                errors.append("INVARIANT 6 VIOLATION: High state uncertainty cannot be SUPPORTED_HEALTHY.")

        # INVARIANT 7: Epistemic state and operational decision must be separate instances
        if str(self.epistemic_state.value) == str(self.operational_decision.value):
            errors.append("INVARIANT 7 VIOLATION: Epistemic state and operational decision collapsed into identical symbol.")

        # INVARIANT 8: Requesting additional testing precludes immediate OPERATE
        if self.information_action == InformationAction.REQUEST_TEST and self.operational_decision == OperationalDecision.OPERATE:
            errors.append(
                "INVARIANT 8 VIOLATION: System cannot authorize OPERATE while simultaneously requesting additional diagnostic testing."
            )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Serializes record to standard dictionary representation."""
        return {
            "battery_id": self.battery_id,
            "test_id": self.test_id,
            "timestamp": self.timestamp,
            "software_version": self.software_version,
            "configuration_version": self.configuration_version,
            "data_quality": self.data_quality,
            "sensor_valid": self.sensor_valid,
            "telemetry_status": self.telemetry_status,
            "chemistry_belief": dict(self.chemistry_belief),
            "chemistry_confidence_state": self.chemistry_confidence_state,
            "soh_estimate": self.soh_estimate,
            "soh_uncertainty": self.soh_uncertainty,
            "r0_estimate": self.r0_estimate,
            "r0_uncertainty": self.r0_uncertainty,
            "rul_estimate": self.rul_estimate,
            "rul_uncertainty": self.rul_uncertainty,
            "anomaly_status": self.anomaly_status,
            "distribution_status": self.distribution_status,
            "prognostic_identifiability": self.prognostic_identifiability,
            "degradation_regime": self.degradation_regime,
            "safety_barrier_status": self.safety_barrier_status,
            "safety_reason_codes": [rc.value if isinstance(rc, ReasonCode) else str(rc) for rc in self.safety_reason_codes],
            "epistemic_state": self.epistemic_state.value if isinstance(self.epistemic_state, EpistemicState) else str(self.epistemic_state),
            "operational_decision": self.operational_decision.value if isinstance(self.operational_decision, OperationalDecision) else str(self.operational_decision),
            "information_action": self.information_action.value if isinstance(self.information_action, InformationAction) else str(self.information_action),
            "reason_codes": [rc.value if isinstance(rc, ReasonCode) else str(rc) for rc in self.reason_codes],
            "decision_trace": self.decision_trace,
            "model_version": self.model_version,
            "feature_version": self.feature_version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionAuditRecord":
        """Reconstructs DecisionAuditRecord from dictionary with type safety."""
        # Convert enums safely
        ep_raw = data.get("epistemic_state", EpistemicState.INSUFFICIENT_DATA.value)
        ep_state = EpistemicState(ep_raw) if isinstance(ep_raw, str) else ep_raw

        op_raw = data.get("operational_decision", OperationalDecision.HOLD.value)
        op_decision = OperationalDecision(op_raw) if isinstance(op_raw, str) else op_raw

        info_raw = data.get("information_action", InformationAction.NO_TEST.value)
        info_action = InformationAction(info_raw) if isinstance(info_raw, str) else info_raw

        def _parse_reason_codes(codes_raw: Any) -> List[ReasonCode]:
            res = []
            if isinstance(codes_raw, list):
                for c in codes_raw:
                    if isinstance(c, ReasonCode):
                        res.append(c)
                    elif isinstance(c, str):
                        try:
                            res.append(ReasonCode(c))
                        except ValueError:
                            pass
            return res

        return cls(
            battery_id=str(data.get("battery_id", "UNKNOWN")),
            test_id=str(data.get("test_id", "UNKNOWN")),
            timestamp=float(data.get("timestamp", time.time())),
            software_version=str(data.get("software_version", "2.0.0")),
            configuration_version=str(data.get("configuration_version", "default")),
            data_quality=str(data.get("data_quality", "VALID")),
            sensor_valid=bool(data.get("sensor_valid", True)),
            telemetry_status=str(data.get("telemetry_status", "CONNECTED")),
            chemistry_belief=dict(data.get("chemistry_belief", {})),
            chemistry_confidence_state=data.get("chemistry_confidence_state"),
            soh_estimate=float(data.get("soh_estimate", 0.0)),
            soh_uncertainty=float(data.get("soh_uncertainty", 0.0)),
            r0_estimate=float(data.get("r0_estimate", 0.0)),
            r0_uncertainty=float(data.get("r0_uncertainty", 0.0)),
            rul_estimate=float(data["rul_estimate"]) if data.get("rul_estimate") is not None else None,
            rul_uncertainty=float(data["rul_uncertainty"]) if data.get("rul_uncertainty") is not None else None,
            anomaly_status=data.get("anomaly_status"),
            distribution_status=data.get("distribution_status"),
            prognostic_identifiability=data.get("prognostic_identifiability"),
            degradation_regime=data.get("degradation_regime"),
            safety_barrier_status=str(data.get("safety_barrier_status", "PASS")),
            safety_reason_codes=_parse_reason_codes(data.get("safety_reason_codes", [])),
            epistemic_state=ep_state,
            operational_decision=op_decision,
            information_action=info_action,
            reason_codes=_parse_reason_codes(data.get("reason_codes", [])),
            decision_trace=data.get("decision_trace"),
            model_version=data.get("model_version"),
            feature_version=data.get("feature_version")
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "DecisionAuditRecord":
        """Deserializes from JSON string."""
        return cls.from_dict(json.loads(json_str))
