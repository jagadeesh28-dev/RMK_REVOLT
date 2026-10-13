"""
Canonical Feature Engine (Phase 4)
Project: RMK-REVOLT / SECONDShift Platform

End-to-end orchestration pipeline:
Validated Measurements
        ↓
Temporal Window Selection
        ↓
Measurement Quality Gate
        ↓
Feature Calculation (Family-Specific Extractors)
        ↓
Physical Validity Gate
        ↓
Missingness / Quality Annotation
        ↓
Temporal Provenance
        ↓
DerivedFeature (Frozen Phase 3 Contract)
        ↓
Feature Registry (Authoritative Catalog)
        ↓
Candidate Feature Set

Strict Invariants:
- Uses frozen DerivedFeature contract from qualification_schema.py.
- Missing != Zero.
- Future information is flagged and rejected from downstream admission.
- Observational only: computation error NEVER affects HardSafetyBarrier.
"""

from typing import Dict, Any, List, Optional, Union
import time

from secondshift.interfaces.qualification_schema import (
    DerivedFeature,
    TemporalProvenance,
    TemporalLeakageStatus,
    QualificationSession,
    TestSegment,
    SegmentType
)
from secondshift.interfaces.data_quality_schema import DataQualityState
from secondshift.interfaces.telemetry_schema import TelemetryFrame

from secondshift.software.features.feature_metadata import (
    FeatureDefinition,
    FeatureFamily,
    TemporalAvailability,
    FeatureCandidateStatus
)
from secondshift.software.features.feature_registry import (
    FeatureRegistry,
    create_canonical_registry
)
from secondshift.software.features.admission import (
    FeatureAdmissionEngine,
    AdmissionAuditResult
)
from secondshift.software.features.extractors.base import BaseFeatureExtractor
from secondshift.software.features.extractors.electrical import ElectricalFeatureExtractor
from secondshift.software.features.extractors.pulse import PulseFeatureExtractor
from secondshift.software.features.extractors.relaxation import RelaxationFeatureExtractor
from secondshift.software.features.extractors.coulometric import CoulometricFeatureExtractor
from secondshift.software.features.extractors.energy import EnergyFeatureExtractor
from secondshift.software.features.extractors.thermal import ThermalFeatureExtractor
from secondshift.software.features.extractors.data_quality import DataQualityFeatureExtractor


class CanonicalFeatureEngine:
    """
    Authoritative battery qualification feature engine.
    Ensures every feature is physically grounded, provenance-tracked, and causally valid.
    """

    def __init__(
        self,
        registry: Optional[FeatureRegistry] = None,
        admission_engine: Optional[FeatureAdmissionEngine] = None
    ):
        self.registry = registry or create_canonical_registry()
        self.admission_engine = admission_engine or FeatureAdmissionEngine()

        # Map families to dedicated deterministic extractors
        self._extractors: Dict[FeatureFamily, BaseFeatureExtractor] = {
            FeatureFamily.ELECTRICAL: ElectricalFeatureExtractor(),
            FeatureFamily.PULSE: PulseFeatureExtractor(),
            FeatureFamily.RELAXATION: RelaxationFeatureExtractor(),
            FeatureFamily.COULOMETRIC: CoulometricFeatureExtractor(),
            FeatureFamily.ENERGY: EnergyFeatureExtractor(),
            FeatureFamily.THERMAL: ThermalFeatureExtractor(),
            FeatureFamily.DATA_QUALITY: DataQualityFeatureExtractor()
        }

    def extract_feature(
        self,
        feature_id: str,
        samples: List[Union[Dict[str, Any], TelemetryFrame]],
        session_id: str = "QUAL_SESSION_DEFAULT",
        segment_id: Optional[str] = None,
        decision_timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> DerivedFeature:
        """
        Extracts an individual feature by ID, enforcing registry verification
        and the 8-Gate admission framework.
        """
        definition = self.registry.get(feature_id)

        # Standardize samples to dictionary format
        raw_dicts = self._normalize_samples(samples)

        # Handle explicitly deferred or rejected features (e.g. dQ/dV)
        if definition.family == FeatureFamily.DEFERRED or definition.status == FeatureCandidateStatus.REJECTED:
            tp = BaseFeatureExtractor.build_provenance(raw_dicts, decision_timestamp)
            return BaseFeatureExtractor.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"Feature is explicitly DEFERRED / REJECTED: {definition.limitations}"
            )

        extractor = self._extractors.get(definition.family)
        if extractor is None:
            tp = BaseFeatureExtractor.build_provenance(raw_dicts, decision_timestamp)
            return BaseFeatureExtractor.build_invalid_feature(
                definition, session_id, segment_id, tp,
                f"No registered extractor for family: {definition.family}"
            )

        # 1. Compute preliminary feature
        feature = extractor.extract(
            definition=definition,
            samples=raw_dicts,
            session_id=session_id,
            segment_id=segment_id,
            decision_timestamp=decision_timestamp,
            context=context
        )

        # 2. Evaluate 8-Gate Admission Audit
        audit = self.admission_engine.evaluate(
            feature=feature,
            definition=definition,
            raw_samples=raw_dicts,
            decision_timestamp=decision_timestamp
        )

        # 3. Enforce admission verdict: if audit fails, mark invalid and preserve None
        if not audit.admissible:
            feature.quality_status = DataQualityState.INVALID.value
            feature.value = None
            orig_meaning = feature.physical_meaning
            if "TEMPORALLY_UNAVAILABLE" in orig_meaning or "UNAVAILABLE" in orig_meaning:
                feature.physical_meaning = f"ADMISSION REJECTED: {orig_meaning}; {'; '.join(audit.failure_reasons)}"
            else:
                feature.physical_meaning = f"ADMISSION REJECTED: {'; '.join(audit.failure_reasons)}"

        return feature

    def extract_family(
        self,
        family: FeatureFamily,
        samples: List[Union[Dict[str, Any], TelemetryFrame]],
        session_id: str = "QUAL_SESSION_DEFAULT",
        segment_id: Optional[str] = None,
        decision_timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[DerivedFeature]:
        """Extracts all registered candidate features for a specified family."""
        features: List[DerivedFeature] = []
        for defn in self.registry.list(family=family):
            feat = self.extract_feature(
                feature_id=defn.feature_id,
                samples=samples,
                session_id=session_id,
                segment_id=segment_id,
                decision_timestamp=decision_timestamp,
                context=context
            )
            features.append(feat)
        return features

    def extract_all(
        self,
        samples: List[Union[Dict[str, Any], TelemetryFrame]],
        session_id: str = "QUAL_SESSION_DEFAULT",
        segment_id: Optional[str] = None,
        decision_timestamp: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[DerivedFeature]:
        """Extracts all active candidate features in the registry."""
        features: List[DerivedFeature] = []
        for defn in self.registry.list():
            if defn.family != FeatureFamily.DEFERRED:
                feat = self.extract_feature(
                    feature_id=defn.feature_id,
                    samples=samples,
                    session_id=session_id,
                    segment_id=segment_id,
                    decision_timestamp=decision_timestamp,
                    context=context
                )
                features.append(feat)
        return features

    def extract_for_session(
        self,
        session: QualificationSession,
        segment_data_map: Dict[str, List[Dict[str, Any]]],
        decision_timestamp: Optional[float] = None
    ) -> List[DerivedFeature]:
        """
        Extracts features across executed segments of a QualificationSession
        and attaches them directly to session.derived_features.
        """
        all_extracted: List[DerivedFeature] = []

        for seg in session.segments:
            seg_samples = segment_data_map.get(seg.segment_id, [])
            seg_type = seg.segment_type

            ctx: Dict[str, Any] = {
                "validation_record": seg.validation_record,
                "pulse_valid": (seg.validation_status == "VALID" and seg_type == SegmentType.PULSE.value)
            }

            # Map segment type to targeted families
            target_families = [FeatureFamily.ELECTRICAL, FeatureFamily.DATA_QUALITY]
            if seg_type == SegmentType.PULSE.value:
                target_families.append(FeatureFamily.PULSE)
            elif seg_type == SegmentType.REST.value:
                target_families.append(FeatureFamily.RELAXATION)
            elif seg_type == SegmentType.CHARGE.value:
                target_families.extend([FeatureFamily.COULOMETRIC, FeatureFamily.ENERGY])
            elif seg_type == SegmentType.DISCHARGE.value:
                target_families.extend([FeatureFamily.COULOMETRIC, FeatureFamily.ENERGY])

            for fam in target_families:
                feats = self.extract_family(
                    family=fam,
                    samples=seg_samples,
                    session_id=session.session_id,
                    segment_id=seg.segment_id,
                    decision_timestamp=decision_timestamp,
                    context=ctx
                )
                all_extracted.extend(feats)

        # Attach to session aggregate root
        session.derived_features.extend(all_extracted)
        return all_extracted

    def audit_admission(
        self,
        feature: DerivedFeature,
        raw_samples: List[Union[Dict[str, Any], TelemetryFrame]],
        decision_timestamp: Optional[float] = None
    ) -> AdmissionAuditResult:
        """Runs the 8-Gate audit directly and returns the structured evaluation."""
        definition = self.registry.get(feature.feature_name)
        raw_dicts = self._normalize_samples(raw_samples)
        return self.admission_engine.evaluate(
            feature=feature,
            definition=definition,
            raw_samples=raw_dicts,
            decision_timestamp=decision_timestamp
        )

    @staticmethod
    def _normalize_samples(
        samples: List[Union[Dict[str, Any], TelemetryFrame]]
    ) -> List[Dict[str, Any]]:
        """Converts heterogeneous TelemetryFrame or dictionary samples into standard dicts."""
        res: List[Dict[str, Any]] = []
        for s in samples:
            if isinstance(s, TelemetryFrame):
                res.append(s.to_dict())
            elif isinstance(s, dict):
                res.append(s)
            elif hasattr(s, "to_dict"):
                res.append(s.to_dict())
        return res
