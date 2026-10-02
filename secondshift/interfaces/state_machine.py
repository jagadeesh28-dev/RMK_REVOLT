"""
System State Machine (Layer 4)
Project: RMK-REVOLT / SECONDShift Platform

Governs legal transitions across operational and safety lifecycle states.
Rules:
- FAULT can NEVER transition directly to OPERATE or DERATE.
- RETIRE is a terminal qualification state requiring explicit requalification.
- EMERGENCY_ISOLATE is a hardware latch state.
"""

from enum import Enum
from typing import Set, Dict, List, Optional
import time


class IllegalStateTransitionError(RuntimeError):
    """Raised when an illegal state machine transition is attempted."""
    pass


class SystemState(str, Enum):
    INIT = "INIT"
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    MEASURING = "MEASURING"
    QUALIFYING = "QUALIFYING"
    OPERATE = "OPERATE"
    DERATE = "DERATE"
    HOLD = "HOLD"
    RETIRE = "RETIRE"
    FAULT = "FAULT"
    EMERGENCY_ISOLATE = "EMERGENCY_ISOLATE"


class SystemStateMachine:
    """
    State machine enforcing architectural safety transition rules.
    """
    # Explicit legal transition graph
    LEGAL_TRANSITIONS: Dict[SystemState, Set[SystemState]] = {
        SystemState.INIT: {
            SystemState.DISCONNECTED,
            SystemState.CONNECTED
        },
        SystemState.DISCONNECTED: {
            SystemState.CONNECTED,
            SystemState.INIT
        },
        SystemState.CONNECTED: {
            SystemState.MEASURING,
            SystemState.DISCONNECTED,
            SystemState.FAULT
        },
        SystemState.MEASURING: {
            SystemState.QUALIFYING,
            SystemState.FAULT,
            SystemState.EMERGENCY_ISOLATE,
            SystemState.DISCONNECTED
        },
        SystemState.QUALIFYING: {
            SystemState.OPERATE,
            SystemState.DERATE,
            SystemState.HOLD,
            SystemState.RETIRE,
            SystemState.MEASURING, # Loop for active diagnostic tests
            SystemState.FAULT,
            SystemState.EMERGENCY_ISOLATE
        },
        SystemState.OPERATE: {
            SystemState.DERATE,
            SystemState.HOLD,
            SystemState.RETIRE,
            SystemState.FAULT,
            SystemState.EMERGENCY_ISOLATE,
            SystemState.DISCONNECTED
        },
        SystemState.DERATE: {
            SystemState.HOLD,
            SystemState.RETIRE,
            SystemState.FAULT,
            SystemState.EMERGENCY_ISOLATE,
            SystemState.DISCONNECTED
        },
        SystemState.HOLD: {
            SystemState.MEASURING, # Manual re-measurement permitted
            SystemState.RETIRE,
            SystemState.DISCONNECTED,
            SystemState.FAULT
        },
        SystemState.RETIRE: {
            SystemState.DISCONNECTED,
            SystemState.INIT # Explicit manual reset
        },
        SystemState.FAULT: {
            SystemState.HOLD,
            SystemState.EMERGENCY_ISOLATE,
            SystemState.DISCONNECTED,
            SystemState.INIT
        },
        SystemState.EMERGENCY_ISOLATE: {
            SystemState.DISCONNECTED,
            SystemState.INIT # Latched; requires explicit administrative reset
        }
    }

    def __init__(self, initial_state: SystemState = SystemState.INIT):
        self.current_state = initial_state
        self.history: List[Dict[str, Any]] = [{
            "timestamp": time.time(),
            "from_state": None,
            "to_state": initial_state.value,
            "reason": "System initialization"
        }]

    def transition_to(self, target_state: SystemState, reason: str = "", strict: bool = False) -> bool:
        """
        Attempts a transition to target_state.
        Returns True if transition is legally permitted, False otherwise.
        If strict=True, raises IllegalStateTransitionError on illegal transitions.
        """
        allowed = self.LEGAL_TRANSITIONS.get(self.current_state, set())
        if target_state not in allowed:
            if strict:
                raise IllegalStateTransitionError(
                    f"Illegal state transition: cannot transition from {self.current_state.value} to {target_state.value}"
                )
            return False

        old_state = self.current_state
        self.current_state = target_state
        self.history.append({
            "timestamp": time.time(),
            "from_state": old_state.value,
            "to_state": target_state.value,
            "reason": reason
        })
        return True

    def can_transition_to(self, target_state: SystemState) -> bool:
        """Checks if a transition is legal without performing it."""
        return target_state in self.LEGAL_TRANSITIONS.get(self.current_state, set())

    def is_emergency_latched(self) -> bool:
        """Returns True if the system is locked in EMERGENCY_ISOLATE state."""
        return self.current_state == SystemState.EMERGENCY_ISOLATE

    def clear_emergency_latch(self, reason: str = "Manual operator reset"):
        """Clears emergency latch by transitioning to INIT."""
        if self.current_state == SystemState.EMERGENCY_ISOLATE:
            self.current_state = SystemState.INIT
            self.history.append({
                "timestamp": time.time(),
                "from_state": SystemState.EMERGENCY_ISOLATE.value,
                "to_state": SystemState.INIT.value,
                "reason": f"RESET: {reason}"
            })

    def force_emergency_isolate(self, reason: str):
        """Unconditional safety trip to EMERGENCY_ISOLATE."""
        old = self.current_state
        self.current_state = SystemState.EMERGENCY_ISOLATE
        self.history.append({
            "timestamp": time.time(),
            "from_state": old.value,
            "to_state": SystemState.EMERGENCY_ISOLATE.value,
            "reason": f"SAFETY TRIP: {reason}"
        })
