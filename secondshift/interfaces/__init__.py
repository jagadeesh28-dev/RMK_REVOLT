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
from .epistemic_schema import (
    EpistemicState,
    OperationalDecision,
    InformationAction,
    ReasonCode,
    DecisionAuditRecord
)
from .data_quality_schema import (
    DataQualityRecord,
    PulseValidationRecord,
    DataQualityState,
    EventClassification
)
from .qualification_schema import (
    BatteryRecord,
    TestProtocol,
    TestSegment,
    SegmentType,
    SessionLifecycleStatus,
    QualificationDataStatus,
    TemporalProvenance,
    TemporalLeakageStatus,
    MeasurementScope,
    DerivedFeature,
    InferredChemistryRecord,
    QualificationSession
)

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
    "SystemStateMachine",
    "EpistemicState",
    "OperationalDecision",
    "InformationAction",
    "ReasonCode",
    "DecisionAuditRecord",
    "DataQualityRecord",
    "PulseValidationRecord",
    "DataQualityState",
    "EventClassification",
    "BatteryRecord",
    "TestProtocol",
    "TestSegment",
    "SegmentType",
    "SessionLifecycleStatus",
    "QualificationDataStatus",
    "TemporalProvenance",
    "TemporalLeakageStatus",
    "MeasurementScope",
    "DerivedFeature",
    "InferredChemistryRecord",
    "QualificationSession"
]
