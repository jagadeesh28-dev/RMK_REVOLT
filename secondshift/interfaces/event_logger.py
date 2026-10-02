"""
Structured Event Logger (Layer 2 / 4)
Project: RMK-REVOLT / SECONDShift Platform

Logs complete telemetry, validation, state estimation, risk, decision,
and actuation intent traces to machine-readable JSONL files.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional

from .telemetry_schema import TelemetryFrame
from .telemetry_validator import TelemetryValidationResult
from .command_schema import CommandFrame


class EventLogger:
    """
    Append-only structured JSONL logger for research and production traceability.
    """
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path
        self.in_memory_events: List[Dict[str, Any]] = []
        if self.log_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)

    def log_event(self, event_type: str, payload: Dict[str, Any]):
        """Records an arbitrary typed event."""
        record = {
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_type": event_type,
            "data": payload
        }
        self.in_memory_events.append(record)

        if self.log_path:
            with open(self.log_path, mode="a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

    def log_telemetry_evaluation(
        self,
        frame: TelemetryFrame,
        validation: TelemetryValidationResult,
        device_id: str
    ):
        self.log_event("TELEMETRY_EVALUATION", {
            "device_id": device_id,
            "sequence_number": frame.sequence_number,
            "frame_timestamp": frame.timestamp,
            "voltage_v": frame.voltage_v,
            "current_a": frame.current_a,
            "temperature_c": frame.temperature_c,
            "is_valid": validation.valid,
            "quality": validation.quality,
            "errors": validation.errors,
            "warnings": validation.warnings
        })

    def log_qualification_decision(
        self,
        cell_id: str,
        stage: str,
        decision: str,
        reason: str,
        state_estimate: Optional[Dict[str, Any]] = None,
        marginal_risk: Optional[float] = None
    ):
        self.log_event("QUALIFICATION_DECISION", {
            "cell_id": cell_id,
            "stage": stage,
            "decision": decision,
            "reason": reason,
            "state_estimate": state_estimate,
            "marginal_risk": marginal_risk
        })

    def log_actuation_command(
        self,
        command: CommandFrame,
        acknowledged: bool
    ):
        self.log_event("ACTUATION_COMMAND", {
            "command_id": command.command_id,
            "action": command.action,
            "requested_mode": command.requested_mode,
            "reason": command.reason,
            "interlock_required": command.interlock_required,
            "acknowledged": acknowledged,
            "parameters": command.parameters
        })

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self.in_memory_events)

    def clear(self):
        self.in_memory_events.clear()
