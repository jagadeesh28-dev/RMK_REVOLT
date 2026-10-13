"""
Phase 5 Feature Scientific Validation Models & Contracts
Project: RMK-REVOLT / SECONDShift Platform

Defines the core data contracts, status models, multidimensional evidence vectors,
interpretable baselines, and cross-validation splitters for Phase 5.

Core Principle:
    COMPUTABLE != PHYSICALLY VALID != PROGNOSTICALLY USEFUL
    Validation Unit: BATTERY / SPECIMEN (Never individual telemetry rows)
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Set
import numpy as np
import math


class FeatureValidationStatus(str, Enum):
    """
    Epistemic validation status of a candidate feature.
    Preserves uncertainty: never forces an unproven feature into SUPPORTED or REJECTED.
    """
    IMPLEMENTATION_VALID = "IMPLEMENTATION_VALID"       # Correctly computed per software contract
    PHYSICALLY_SUPPORTED = "PHYSICALLY_SUPPORTED"       # Measured quantity has electrochemical/physical validity
    PROGNOSTICALLY_SUPPORTED = "PROGNOSTICALLY_SUPPORTED" # Demonstrates reproducible battery-disjoint predictive value
    PROGNOSTICALLY_REJECTED = "PROGNOSTICALLY_REJECTED"   # Unstable, non-generalizable, redundant, or leaking
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"     # Data/evidence insufficient to make definitive claim


class FeatureAdmissionStatus(str, Enum):
    """
    Canonical Phase 5 and Phase 5.1 feature admission decision.
    Distinguishes suite-level vs individual-feature evidentiary strength.
    """
    ADMIT = "ADMIT"
    PROVISIONALLY_ADMITTED = "PROVISIONALLY_ADMITTED"                     # Suite-level / legacy alias
    PROVISIONALLY_SUPPORTED = "PROVISIONALLY_SUPPORTED"                   # Strongest physical LOFO evidence (DELTA_V_TOTAL)
    PROVISIONALLY_SUPPORTED_MODEST_EFFECT = "PROVISIONALLY_SUPPORTED / MODEST_EFFECT" # Modest physical LOFO effect (DELTA_V_OHMIC)
    CONTEXTUAL_PROVISIONAL = "CONTEXTUAL / PROVISIONAL"                   # Protocol-dependent electrical observation (R0_OHMIC)
    INSUFFICIENT_INCREMENTAL_EVIDENCE = "INSUFFICIENT_INCREMENTAL_EVIDENCE" # Zero incremental LOFO value in 10s screening (RELAXATION_DELTA_V)
    CONDITIONAL = "CONDITIONAL"                                           # Prognostically useful strictly under defined bounds (V_MEAN, T_MEAN)
    DEFER = "DEFER"
    DEFERRED = "DEFERRED"                                                 # Potentially valid concept, offline only (DQ_DV_PEAK)
    REJECT = "REJECT"
    REJECTED = "REJECTED"                                                 # Redundancy, bench stimulus, or zero incremental information
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"                       # Insufficient evidence to support claim


class EvidenceLevel(str, Enum):
    """
    Evidence hierarchy from software simulation to prospective physical validation.
    """
    LEVEL_0 = "LEVEL_0_SOFTWARE_SYNTHETIC"
    LEVEL_1 = "LEVEL_1_SIMULATION_COHORT"
    LEVEL_2 = "LEVEL_2_SMALL_PHYSICAL_COHORT"
    LEVEL_3 = "LEVEL_3_CROSS_BATTERY_PHYSICAL"
    LEVEL_4 = "LEVEL_4_CROSS_CHEMISTRY_PHYSICAL"
    LEVEL_5 = "LEVEL_5_PROSPECTIVE_PHYSICAL"


class ClaimStatus(str, Enum):
    """
    Strict scientific claim classification taxonomy.
    """
    PROVEN = "PROVEN"
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
    SUPPORTED = "SUPPORTED"
    CONDITIONAL = "CONDITIONAL"
    EXPLORATORY = "EXPLORATORY"
    SIMULATION_SUPPORTED = "SIMULATION_SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class FoldRobustnessStats:
    """
    Quantifies fold-by-fold statistical and engineering robustness for LOFO ablation.
    """
    feature_id: str
    mean_delta_mae: float
    median_delta_mae: float
    std_delta_mae: float
    se_delta_mae: float
    ci_95_lower: float
    ci_95_upper: float
    folds_improved: int
    folds_degraded: int
    folds_neutral: int
    cohens_d: float
    p_value: float
    is_statistically_significant: bool
    is_engineering_significant: bool
    engineering_threshold: float = 0.005

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "mean_delta_mae": round(self.mean_delta_mae, 6),
            "median_delta_mae": round(self.median_delta_mae, 6),
            "std_delta_mae": round(self.std_delta_mae, 6),
            "se_delta_mae": round(self.se_delta_mae, 6),
            "ci_95_lower": round(self.ci_95_lower, 6),
            "ci_95_upper": round(self.ci_95_upper, 6),
            "folds_improved": self.folds_improved,
            "folds_degraded": self.folds_degraded,
            "folds_neutral": self.folds_neutral,
            "cohens_d": round(self.cohens_d, 4),
            "p_value": round(self.p_value, 6),
            "is_statistically_significant": self.is_statistically_significant,
            "is_engineering_significant": self.is_engineering_significant,
            "engineering_threshold": self.engineering_threshold
        }


@dataclass
class MultidimensionalEvidenceVector:
    """
    Non-collapsed multidimensional evidence vector for an individual candidate feature.
    STRICT RULE: Never collapses into an arbitrary magic 0-100 score.
    """
    feature_id: str
    feature_family: str
    implementation_validity: bool = True
    physical_support: bool = False
    temporal_validity: bool = True
    measurement_robustness: float = 0.0          # Stability under sensor noise in [0.0, 1.0]
    cross_battery_generalization: float = 0.0    # Cross-battery performance retention in [0.0, 1.0]
    incremental_predictive_value: float = 0.0    # Delta MAE or improvement beyond baseline in [0.0, 1.0]
    redundancy_level: float = 0.0                # Collinearity / correlation with higher-priority feature in [0.0, 1.0]
    domain_dependence: str = "UNIVERSAL"         # UNIVERSAL, CHEMISTRY_SPECIFIC, RATE_DEPENDENT, TEMPERATURE_BOUND
    availability_scope: str = "ONLINE_INCREMENTAL" # ONLINE_INCREMENTAL, SEGMENT_COMPLETION, OFFLINE_ONLY
    measurement_cost_seconds: float = 0.0        # Practical bench time required to obtain valid sample (s)
    primary_failure_mode: Optional[str] = None
    admission_verdict: FeatureAdmissionStatus = FeatureAdmissionStatus.DEFER
    scientific_claim_level: ClaimStatus = ClaimStatus.INSUFFICIENT_EVIDENCE
    evidence_level: EvidenceLevel = EvidenceLevel.LEVEL_1
    real_evidence_present: bool = True
    synthetic_evidence_present: bool = True
    mechanism_confidence: str = "AGGREGATE_ELECTRICAL" # CORRELATIONAL_ONLY, AGGREGATE_ELECTRICAL, DIRECT_PHYSICAL
    effect_size_cohens_d: Optional[float] = None
    confidence_interval_95: Optional[Tuple[float, float]] = None
    p_value: Optional[float] = None
    superseded_claims: List[str] = field(default_factory=list)
    limitations: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        ci_str = None
        if self.confidence_interval_95 is not None:
            ci_str = f"[{self.confidence_interval_95[0]:.5f}, {self.confidence_interval_95[1]:.5f}]"
        return {
            "feature_id": self.feature_id,
            "feature_family": self.feature_family,
            "implementation_validity": self.implementation_validity,
            "physical_support": self.physical_support,
            "temporal_validity": self.temporal_validity,
            "measurement_robustness": round(self.measurement_robustness, 4),
            "cross_battery_generalization": round(self.cross_battery_generalization, 4),
            "incremental_predictive_value": round(self.incremental_predictive_value, 6),
            "redundancy_level": round(self.redundancy_level, 4),
            "domain_dependence": self.domain_dependence,
            "availability_scope": self.availability_scope,
            "measurement_cost_seconds": self.measurement_cost_seconds,
            "primary_failure_mode": self.primary_failure_mode,
            "admission_verdict": self.admission_verdict.value,
            "scientific_claim_level": self.scientific_claim_level.value,
            "evidence_level": self.evidence_level.value if isinstance(self.evidence_level, EvidenceLevel) else str(self.evidence_level),
            "real_evidence_present": self.real_evidence_present,
            "synthetic_evidence_present": self.synthetic_evidence_present,
            "mechanism_confidence": self.mechanism_confidence,
            "effect_size_cohens_d": round(self.effect_size_cohens_d, 4) if self.effect_size_cohens_d is not None else None,
            "confidence_interval_95": ci_str,
            "p_value": round(self.p_value, 6) if self.p_value is not None else None,
            "superseded_claims": self.superseded_claims,
            "limitations": self.limitations
        }


@dataclass
class DatasetManifest:
    """
    Dataset audit record documenting specimens, channels, resolutions, and targets.
    Distinguishes REAL_PHYSICAL_N, SYNTHETIC_N, and TOTAL_COMPUTATIONAL_N.
    """
    dataset_name: str
    total_batteries: int
    battery_identifiers: List[str]
    chemistry_counts: Dict[str, int]
    operating_conditions: Dict[str, Any]
    temperature_range_c: Tuple[float, float]
    voltage_range_v: Tuple[float, float]
    current_range_a: Tuple[float, float]
    voltage_resolution_mv: float
    current_resolution_ma: float
    timestamp_resolution_ms: float
    missing_fraction: float
    has_trustworthy_soh: bool
    soh_definition: str
    has_trustworthy_rul: bool
    rul_audit_notes: str
    unit_of_independence: str = "BATTERY / SPECIMEN"
    real_physical_n: int = 12
    synthetic_n: int = 100
    total_computational_n: int = 112
    evidence_origin: str = "MIXED" # REAL_PHYSICAL, SYNTHETIC, MIXED


# =============================================================================
# INTERPRETABLE BASELINE MODELS
# =============================================================================

class MeanPredictorBaseline:
    """
    Minimal A0 baseline: always predicts the training set mean.
    Serves as the empirical floor for incremental predictive value.
    """
    def __init__(self):
        self.mean_target: float = 0.0
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "MeanPredictorBaseline":
        if len(y) == 0:
            raise ValueError("Cannot fit on empty target array.")
        self.mean_target = float(np.mean(y))
        self.is_fitted = True
        return self

    def predict(self, X: Any) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict.")
        n_samples = len(X) if hasattr(X, "__len__") else 1
        return np.full(n_samples, self.mean_target)


class LinearBaseline:
    """
    Ordinary Least Squares (OLS) baseline with SVD pseudoinverse to avoid singular inversions.
    """
    def __init__(self, fit_intercept: bool = True):
        self.fit_intercept = fit_intercept
        self.weights: Optional[np.ndarray] = None
        self.intercept: float = 0.0
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LinearBaseline":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        if self.fit_intercept:
            X_design = np.column_stack([np.ones(X.shape[0]), X])
        else:
            X_design = X

        # Pinverse via SVD
        try:
            beta = np.linalg.pinv(X_design) @ y
        except np.linalg.LinAlgError:
            # Fallback to mean if singular
            beta = np.zeros(X_design.shape[1])
            beta[0] = np.mean(y)

        if self.fit_intercept:
            self.intercept = float(beta[0])
            self.weights = beta[1:]
        else:
            self.intercept = 0.0
            self.weights = beta
        self.is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict.")
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X @ self.weights + self.intercept


class RidgeBaseline:
    """
    $L_2$ Regularized Ridge Regression baseline.
    """
    def __init__(self, alpha: float = 1.0, fit_intercept: bool = True):
        self.alpha = alpha
        self.fit_intercept = fit_intercept
        self.weights: Optional[np.ndarray] = None
        self.intercept: float = 0.0
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RidgeBaseline":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        n_samples, n_features = X.shape
        if self.fit_intercept:
            X_mean = np.mean(X, axis=0)
            y_mean = np.mean(y)
            X_centered = X - X_mean
            y_centered = y - y_mean
        else:
            X_mean = np.zeros(n_features)
            y_mean = 0.0
            X_centered = X
            y_centered = y

        reg_matrix = self.alpha * np.eye(n_features)
        A = X_centered.T @ X_centered + reg_matrix
        try:
            self.weights = np.linalg.solve(A, X_centered.T @ y_centered)
        except np.linalg.LinAlgError:
            self.weights = np.linalg.pinv(A) @ (X_centered.T @ y_centered)

        if self.fit_intercept:
            self.intercept = float(y_mean - X_mean @ self.weights)
        else:
            self.intercept = 0.0
        self.is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict.")
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X @ self.weights + self.intercept


# =============================================================================
# VALIDATION SPLITTERS (BATTERY-DISJOINT & TEMPORAL)
# =============================================================================

class BatteryDisjointSplitter:
    """
    Strict Battery-Disjoint Splitter.
    Enforces the core scientific requirement:
        A battery appearing in training must NEVER appear in validation/test.
    Supports Leave-One-Battery-Out (LOBO) and Grouped K-Fold.
    """
    @staticmethod
    def split_lobo(
        battery_ids: List[str]
    ) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        """
        Yields (train_indices, test_indices, test_battery_id) for each distinct battery.
        """
        battery_array = np.asarray(battery_ids)
        unique_batteries = np.unique(battery_array)
        splits = []
        for test_battery in unique_batteries:
            test_mask = (battery_array == test_battery)
            train_mask = ~test_mask
            train_idx = np.where(train_mask)[0]
            test_idx = np.where(test_mask)[0]
            splits.append((train_idx, test_idx, str(test_battery)))
        return splits

    @staticmethod
    def split_grouped_kfold(
        battery_ids: List[str],
        n_splits: int = 4,
        seed: int = 42
    ) -> List[Tuple[np.ndarray, np.ndarray, List[str]]]:
        """
        Groups batteries into k disjoint subsets.
        All records belonging to a group of batteries are in either train or test, never both.
        """
        battery_array = np.asarray(battery_ids)
        unique_batteries = np.unique(battery_array)
        rng = np.random.RandomState(seed)
        shuffled = unique_batteries.copy()
        rng.shuffle(shuffled)

        k = min(n_splits, len(unique_batteries))
        folds = np.array_split(shuffled, k)
        splits = []
        for test_batteries_fold in folds:
            test_batteries_set = set(test_batteries_fold)
            test_mask = np.isin(battery_array, list(test_batteries_set))
            train_mask = ~test_mask
            train_idx = np.where(train_mask)[0]
            test_idx = np.where(test_mask)[0]
            splits.append((train_idx, test_idx, list(test_batteries_fold)))
        return splits


class TemporalSplitter:
    """
    Strict Temporal Splitter for longitudinal battery aging telemetry.
    Ensures causality:
        Earlier cycles/segments -> Training
        Later cycles/segments   -> Validation/Evaluation
    Never predicts the past from the future.
    """
    @staticmethod
    def split_by_cycle_cutoff(
        cycle_indices: List[int],
        split_fraction: float = 0.50
    ) -> Tuple[np.ndarray, np.ndarray]:
        cycles = np.asarray(cycle_indices)
        cutoff = float(np.quantile(cycles, split_fraction))
        train_idx = np.where(cycles <= cutoff)[0]
        test_idx = np.where(cycles > cutoff)[0]
        return train_idx, test_idx


class RandomRowSplitter:
    """
    Conventional Random Row Splitter.
    Used SOLELY as a hostile contrast to demonstrate why random splitting produces
    illusory, over-optimistic performance via temporal/battery leakage.
    """
    @staticmethod
    def split(n_samples: int, test_ratio: float = 0.25, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
        rng = np.random.RandomState(seed)
        indices = np.arange(n_samples)
        rng.shuffle(indices)
        split_point = int(n_samples * (1.0 - test_ratio))
        return indices[:split_point], indices[split_point:]


# =============================================================================
# HOSTILE LEAKAGE AUDITOR
# =============================================================================

class HostileLeakageAuditor:
    """
    Audits feature vectors and datasets for subtle data leakage:
    1. Direct specimen/battery identity shortcut injection.
    2. Future timestamp look-ahead (t_feature > t_decision).
    3. Ground-truth oracle contamination (SOH, R0_true, failure_class).
    4. Cross-fold battery contamination in battery-disjoint evaluation.
    """
    PROHIBITED_FEATURE_PATTERNS = {
        "soh", "r0_true", "true_soh", "capacity_actual", "measured_capacity_ah",
        "specimen_id", "battery_id", "module_id", "cell_id", "failure_class",
        "abuse_class", "future_cycle", "degradation_slope_future", "eol_marker",
        "rul", "eol"
    }

    @classmethod
    def audit_feature_keys(cls, feature_dict: Dict[str, Any]) -> List[str]:
        violations = []
        for key in feature_dict.keys():
            k_lower = key.lower()
            for pattern in cls.PROHIBITED_FEATURE_PATTERNS:
                if pattern in k_lower:
                    violations.append(f"LEAKAGE_KEY_DETECTED: '{key}' matches prohibited pattern '{pattern}'")
        return violations

    @classmethod
    def audit_temporal_admissibility(
        cls,
        feature_end_timestamp: float,
        decision_timestamp: float
    ) -> Tuple[bool, str]:
        if feature_end_timestamp > decision_timestamp + 1e-6:
            diff = feature_end_timestamp - decision_timestamp
            return False, f"TEMPORAL_LEAKAGE: feature t_end ({feature_end_timestamp:.3f}s) > t_decision ({decision_timestamp:.3f}s) by {diff:.3f}s"
        return True, "TEMPORALLY_VALID"

    @classmethod
    def audit_train_test_battery_disjointness(
        cls,
        train_battery_ids: List[str],
        test_battery_ids: List[str]
    ) -> Tuple[bool, Set[str]]:
        train_set = set(train_battery_ids)
        test_set = set(test_battery_ids)
        overlap = train_set.intersection(test_set)
        if len(overlap) > 0:
            return False, overlap
        return True, set()
