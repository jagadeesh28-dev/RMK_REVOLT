"""
SECONDShift Interfaces Package
Hardware abstraction contracts, telemetry schemas, validation, logging, and state machines.
"""

from .telemetry_schema import (
    TelemetryFrame,
    TelemetryQuality,
    SensorHealthStatus,
    CommunicationStatus,
    CalibrationStatus,
    TelemetrySource
)
from .telemetry_validator import (
    TelemetryValidator,
    TelemetryValidationResult
)
from .hardware_interface import HardwareInterface
from .command_schema import (
    CommandFrame,
    AbstractAction,
    ActuatorIntent
)
from .event_logger import EventLogger
from .state_machine import SystemState, SystemStateMachine

__all__ = [
    "TelemetryFrame",
    "TelemetryQuality",
    "SensorHealthStatus",
    "CommunicationStatus",
    "CalibrationStatus",
    "TelemetrySource",
    "TelemetryValidator",
    "TelemetryValidationResult",
    "HardwareInterface",
    "CommandFrame",
    "AbstractAction",
    "ActuatorIntent",
    "EventLogger",
    "SystemState",
    "SystemStateMachine"
]
