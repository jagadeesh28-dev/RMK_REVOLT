"""
Canonical Feature Engine Package (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform
"""

from .feature_metadata import (
    FeatureFamily,
    TemporalAvailability,
    FeatureDirectionality,
    FeatureCandidateStatus,
    PhysicalBounds,
    FeatureWindow,
    FeatureDefinition
)
from .feature_registry import (
    FeatureRegistry,
    create_canonical_registry
)
from .admission import (
    FeatureAdmissionEngine,
    GateEvaluation,
    AdmissionAuditResult
)
from .feature_engine import (
    CanonicalFeatureEngine
)

__all__ = [
    "FeatureFamily",
    "TemporalAvailability",
    "FeatureDirectionality",
    "FeatureCandidateStatus",
    "PhysicalBounds",
    "FeatureWindow",
    "FeatureDefinition",
    "FeatureRegistry",
    "create_canonical_registry",
    "FeatureAdmissionEngine",
    "GateEvaluation",
    "AdmissionAuditResult",
    "CanonicalFeatureEngine"
]
