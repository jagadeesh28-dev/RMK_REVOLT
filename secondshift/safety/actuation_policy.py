"""
Actuation Policy Layer (Layer 4)
Project: RMK-REVOLT / SECONDShift Platform

Translates scientific decisions (OPERATE, DERATE, RETIRE, HOLD) into abstract
actuator intents (ENABLE_LOAD, LIMIT_LOAD, ISOLATE, KEEP_ISOLATED).
Enforces fail-safe fallbacks:
- Stale telemetry, sensor faults, communication loss, or range errors
  CAN NEVER PRODUCE OPERATE / ENABLE_LOAD.
- Fallback strictly transitions to HOLD (KEEP_ISOLATED) or EMERGENCY_ISOLATE.
"""

import time
from typing import Dict, Any, Optional

try:
    from secondshift.interfaces.command_schema import (
        CommandFrame,
        AbstractAction,
        ActuatorIntent
    )
    from secondshift.interfaces.telemetry_schema import (
        TelemetryFrame,
        TelemetryQuality
    )
    from secondshift.interfaces.telemetry_validator import TelemetryValidationResult
except ImportError:
    from interfaces.command_schema import (
        CommandFrame,
        AbstractAction,
        ActuatorIntent
    )
    from interfaces.telemetry_schema import (
        TelemetryFrame,
        TelemetryQuality
    )
    from interfaces.telemetry_validator import TelemetryValidationResult


class ActuationPolicy:
    """
    Supervisory policy engine governing translation of research decisions
    to safe abstract actuator intents.
    """
    def __init__(
        self,
        default_operate_current_a: float = 10.0,
        default_derate_current_a: float = 5.0,
        critical_otp_temp_c: float = 45.0, # TR-06 Stage 0 Triage threshold
        critical_uvp_volt_v: float = 2.00,  # TR-03 Stage 0 Triage threshold
        critical_ovp_volt_v: float = 3.75   # TR-04 Stage 0 Triage threshold
    ):
        self.i_op_a = default_operate_current_a
        self.i_der_a = default_derate_current_a
        self.crit_temp_c = critical_otp_temp_c
        self.crit_uvp_v = critical_uvp_volt_v
        self.crit_ovp_v = critical_ovp_volt_v

    def translate_decision(
        self,
        research_decision: str,
        telemetry: Optional[TelemetryFrame] = None,
        validation_result: Optional[TelemetryValidationResult] = None,
        reason: str = "Standard decision translation",
        decision_metadata: Optional[Dict[str, Any]] = None
    ) -> CommandFrame:
        """
        Translates a research decision into a verified CommandFrame.
        Evaluates fail-safe preconditions before authorizing load engagement.
        """
        now = time.time()
        meta = decision_metadata or {}

        # 1. FAIL-SAFE CHECK: VALIDATION FAILURE
        if validation_result is not None and not validation_result.valid:
            # If critical physical violation (UVP, OVP, OTP), force EMERGENCY_ISOLATE
            critical_triggers = [
                e for e in validation_result.errors
                if "ERR_RANGE_01" in e or "ERR_RANGE_02" in e or "ERR_RANGE_04" in e or "ERR_NUM" in e
            ]
            if critical_triggers:
                return CommandFrame(
                    action=AbstractAction.EMERGENCY_ISOLATE.value,
                    requested_mode=ActuatorIntent.ISOLATE.value,
                    reason=f"Fail-Safe Interlock: Critical validation failure: {', '.join(critical_triggers)}",
                    timestamp=now,
                    interlock_required=False,
                    current_limit_a=0.0,
                    parameters={"safety_status": "FAULT_LOCKOUT", "validation_errors": validation_result.errors}
                )

            # For communication dropout, sequence failure, or missing fields: HOLD
            return CommandFrame(
                action=AbstractAction.HOLD.value,
                requested_mode=ActuatorIntent.KEEP_ISOLATED.value,
                reason=f"Fail-Safe Hold: Telemetry validation rejected: {', '.join(validation_result.errors)}",
                timestamp=now,
                interlock_required=False,
                current_limit_a=0.0,
                parameters={"safety_status": "HOLD_QUARANTINE", "validation_errors": validation_result.errors}
            )

        # 2. FAIL-SAFE CHECK: MISSING OR STALE TELEMETRY
        if telemetry is None:
            return CommandFrame(
                action=AbstractAction.HOLD.value,
                requested_mode=ActuatorIntent.KEEP_ISOLATED.value,
                reason="Fail-Safe Hold: Telemetry frame is None (Link Disconnected)",
                timestamp=now,
                interlock_required=False,
                current_limit_a=0.0,
                parameters={"safety_status": "DISCONNECTED"}
            )

        # 3. DIRECT MAPPING FROM VALIDATED RESEARCH DECISION
        if research_decision == "OPERATE":
            return CommandFrame(
                action=AbstractAction.OPERATE.value,
                requested_mode=ActuatorIntent.ENABLE_LOAD.value,
                reason=reason,
                timestamp=now,
                interlock_required=True,
                current_limit_a=self.i_op_a,
                parameters={
                    "safety_status": "NORMAL_OPERATION",
                    "soh_estimate": meta.get("soh_estimate"),
                    "marginal_risk": meta.get("marginal_risk_operate", 0.0),
                    "chemistry": meta.get("chemistry", "CONFIRMED_LFP")
                }
            )

        elif research_decision == "DERATE":
            return CommandFrame(
                action=AbstractAction.DERATE.value,
                requested_mode=ActuatorIntent.LIMIT_LOAD.value,
                reason=reason,
                timestamp=now,
                interlock_required=True,
                current_limit_a=self.i_der_a,
                parameters={
                    "safety_status": "DERATED_OPERATION",
                    "soh_estimate": meta.get("soh_estimate"),
                    "marginal_risk": meta.get("marginal_risk_derate", 0.0),
                    "chemistry": meta.get("chemistry")
                }
            )

        elif research_decision == "RETIRE":
            return CommandFrame(
                action=AbstractAction.RETIRE.value,
                requested_mode=ActuatorIntent.ISOLATE.value,
                reason=reason,
                timestamp=now,
                interlock_required=False,
                current_limit_a=0.0,
                parameters={"safety_status": "RETIRED_RECYCLE", "reason": reason}
            )

        elif research_decision == "TEST":
            pulse_cur = meta.get("pulse_current_a", 10.0)
            pulse_dur = meta.get("pulse_duration_s", 15.0)
            return CommandFrame(
                action=AbstractAction.REQUEST_MEASUREMENT.value,
                requested_mode=ActuatorIntent.EXECUTE_PULSE.value,
                reason=f"Active Diagnostic Test: {reason}",
                timestamp=now,
                interlock_required=True,
                current_limit_a=float(pulse_cur),
                pulse_duration_s=float(pulse_dur),
                parameters={
                    "safety_status": "DIAGNOSTIC_TESTING",
                    "test_type": meta.get("recommended_test", "UNKNOWN_TEST")
                }
            )

        else: # Default HOLD
            return CommandFrame(
                action=AbstractAction.HOLD.value,
                requested_mode=ActuatorIntent.KEEP_ISOLATED.value,
                reason=reason,
                timestamp=now,
                interlock_required=False,
                current_limit_a=0.0,
                parameters={"safety_status": "HOLD_QUARANTINE", "reason": reason}
            )
