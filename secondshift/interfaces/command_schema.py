"""
Canonical Hardware Command Protocol Schema (Layer 4 / 5)
Project: RMK-REVOLT / SECONDShift Platform

Defines abstract command representations sent from the supervisory software
to the embedded controller. Prevents research engines from directly manipulating
low-level GPIO or hardware actuators.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional
import time
import uuid


class AbstractAction(str, Enum):
    OPERATE = "OPERATE"
    DERATE = "DERATE"
    RETIRE = "RETIRE"
    HOLD = "HOLD"
    EMERGENCY_ISOLATE = "EMERGENCY_ISOLATE"
    REQUEST_MEASUREMENT = "REQUEST_MEASUREMENT"


class ActuatorIntent(str, Enum):
    ENABLE_LOAD = "ENABLE_LOAD"
    LIMIT_LOAD = "LIMIT_LOAD"
    ISOLATE = "ISOLATE"
    KEEP_ISOLATED = "KEEP_ISOLATED"
    EXECUTE_PULSE = "EXECUTE_PULSE"


@dataclass
class CommandFrame:
    """
    Strongly-typed abstract command frame.
    Does NOT contain pin numbers, GPIO addresses, or PWM duty registers.
    """
    action: str
    requested_mode: str
    reason: str
    command_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "command"
    timestamp: float = field(default_factory=time.time)
    interlock_required: bool = True
    current_limit_a: Optional[float] = None
    pulse_duration_s: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    @property
    def contactors_closed(self) -> bool:
        """True if requested mode requires closing power contactors to allow current flow."""
        return self.requested_mode in [
            ActuatorIntent.ENABLE_LOAD.value,
            ActuatorIntent.LIMIT_LOAD.value,
            ActuatorIntent.EXECUTE_PULSE.value
        ]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommandFrame":
        return cls(
            action=str(data.get("action", AbstractAction.HOLD.value)),
            requested_mode=str(data.get("requested_mode", ActuatorIntent.KEEP_ISOLATED.value)),
            reason=str(data.get("reason", "Default command")),
            command_id=str(data.get("command_id", str(uuid.uuid4())[:8])),
            type=str(data.get("type", "command")),
            timestamp=float(data.get("timestamp", time.time())),
            interlock_required=bool(data.get("interlock_required", True)),
            current_limit_a=float(data["current_limit_a"]) if data.get("current_limit_a") is not None else None,
            pulse_duration_s=float(data["pulse_duration_s"]) if data.get("pulse_duration_s") is not None else None,
            parameters=dict(data.get("parameters", {}))
        )
