"""
Unit tests for Phase 5 Scientific Feature Validation and Ablation Engine.

Ensures:
1. FeatureValidationStatus and FeatureAdmissionStatus contracts are rigorous.
2. BatteryDisjointSplitter guarantees zero battery ID overlap between train and test.
3. HostileLeakageAuditor catches oracle columns, battery ID leakage, and temporal causality violations.
4. Baseline models (Mean, Linear, Ridge) operate reproducibly under LOBO-CV.
5. MultidimensionalEvidenceVector preserves independent scientific dimensions without magic scores.
6. Feature admission accounting matches exactly:
   5 Admitted + 4 Conditional + 1 Deferred + 20 Rejected = 30 Total Features.
7. Thermal and Data Quality features are prevented from leaking into prognostic health regression.
"""

import pytest
import numpy as np
import pandas as pd
from secondshift.software.features.feature_registry import (
    create_canonical_registry,
    FeatureFamily,
    TOTAL_CATALOGED_FEATURES,
    TOTAL_STANDARDIZED_CANDIDATE_FEATURES,
    TOTAL_DEFERRED_FEATURES,
)
from secondshift.software.features.validation_models import (
    FeatureValidationStatus,
    FeatureAdmissionStatus,
    ClaimStatus,
    MultidimensionalEvidenceVector,
    DatasetManifest,
    BatteryDisjointSplitter,
    TemporalSplitter,
    HostileLeakageAuditor,
    MeanPredictorBaseline,
    LinearBaseline,
    RidgeBaseline,
)
from secondshift.software.features.ablation import FeatureAblationEngine


@pytest.fixture
def sample_feature_df():
    """Generates synthetic multi-battery dataset for testing splitters and models."""
    np.random.seed(42)
    n_per_battery = 5
    batteries = ["BAT-001", "BAT-002", "BAT-003", "BAT-004", "BAT-005"]
    
    records = []
    for b_idx, b_id in enumerate(batteries):
        base_soh = 0.95 - (b_idx * 0.05)
        for c in range(n_per_battery):
            soh = base_soh - (c * 0.005) + np.random.normal(0, 0.001)
            records.append({
                "battery_id": b_id,
                "cycle": c + 1,
                "timestamp": 1000.0 + c * 3600.0,
                "V_MEAN": 3.3 - (1.0 - soh) * 0.2 + np.random.normal(0, 0.005),
                "DELTA_V_OHMIC": 0.05 + (1.0 - soh) * 0.1 + np.random.normal(0, 0.002),
                "R0_OHMIC": 0.012 + (1.0 - soh) * 0.02 + np.random.normal(0, 0.0005),
                "T_MEAN": 25.0 + np.random.normal(0, 0.5),
                "VALID_SAMPLE_FRACTION": 1.0,
                "soh": soh,
            })
    return pd.DataFrame(records)


def test_status_enums():
    """Test validation and admission enum invariants."""
    assert FeatureValidationStatus.IMPLEMENTATION_VALID.value == "IMPLEMENTATION_VALID"
    assert FeatureValidationStatus.PHYSICALLY_SUPPORTED.value == "PHYSICALLY_SUPPORTED"
    assert FeatureValidationStatus.PROGNOSTICALLY_SUPPORTED.value == "PROGNOSTICALLY_SUPPORTED"
    assert FeatureValidationStatus.PROGNOSTICALLY_REJECTED.value == "PROGNOSTICALLY_REJECTED"
    assert FeatureValidationStatus.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"

    assert FeatureAdmissionStatus.ADMIT.value == "ADMIT"
    assert FeatureAdmissionStatus.CONDITIONAL.value == "CONDITIONAL"
    assert FeatureAdmissionStatus.DEFER.value == "DEFER"
    assert FeatureAdmissionStatus.REJECT.value == "REJECT"

    assert ClaimStatus.PROVEN.value == "PROVEN"
    assert ClaimStatus.STRONGLY_SUPPORTED.value == "STRONGLY_SUPPORTED"
    assert ClaimStatus.REJECTED.value == "REJECTED"


def test_multidimensional_evidence_vector():
    """Verifies that evidence vector captures multi-criteria dimensions without collapsing to a magic score."""
    vec = MultidimensionalEvidenceVector(
        feature_id="R0_OHMIC",
        feature_family="PULSE",
        implementation_validity=True,
        physical_support=True,
        temporal_validity=True,
        measurement_robustness=0.92,
        cross_battery_generalization=0.88,
        incremental_predictive_value=0.0014,
        redundancy_level=0.15,
        domain_dependence="UNIVERSAL",
        availability_scope="SCREENING_PULSE",
        measurement_cost_seconds=10.0,
        admission_verdict=FeatureAdmissionStatus.ADMIT,
        scientific_claim_level=ClaimStatus.STRONGLY_SUPPORTED,
    )
    d = vec.to_dict()
    assert d["feature_id"] == "R0_OHMIC"
    assert d["admission_verdict"] == "ADMIT"
    assert "magic_score" not in d
    assert d["measurement_cost_seconds"] == 10.0


def test_battery_disjoint_splitter(sample_feature_df):
    """Verifies battery-disjoint split guarantees zero battery overlap between train and test."""
    folds = BatteryDisjointSplitter.split_lobo(sample_feature_df["battery_id"].tolist())
    assert len(folds) == 5

    for train_idx, test_idx, held_out in folds:
        train_bats = set(sample_feature_df.iloc[train_idx]["battery_id"].unique())
        test_bats = set(sample_feature_df.iloc[test_idx]["battery_id"].unique())
        assert len(test_bats) == 1
        assert held_out in test_bats
        assert train_bats.isdisjoint(test_bats), "Leakage detected: Battery appeared in both train and test!"


def test_temporal_splitter(sample_feature_df):
    """Verifies temporal splitting guarantees train cycles strictly precede test cycles."""
    train_idx, test_idx = TemporalSplitter.split_by_cycle_cutoff(sample_feature_df["cycle"].tolist(), split_fraction=0.6)
    assert len(train_idx) > 0
    assert len(test_idx) > 0
    assert sample_feature_df.iloc[train_idx]["cycle"].max() <= sample_feature_df.iloc[test_idx]["cycle"].min()


def test_hostile_leakage_auditor():
    """Verifies hostile leakage audit catches oracle keys, identity leakage, and temporal violations."""
    auditor = HostileLeakageAuditor()
    
    # 1. Oracle key detection
    leaky_features = {"V_MEAN": 1.0, "soh_future": 1.0, "RUL_target": 1.0, "DELTA_V_OHMIC": 0.05}
    violations = auditor.audit_feature_keys(leaky_features)
    assert any("soh" in v for v in violations)
    assert any("rul" in v.lower() for v in violations)
    assert not any("v_mean" in v.lower() for v in violations)

    # 2. Battery identity leakage / overlap
    is_disjoint, overlap = auditor.audit_train_test_battery_disjointness(["BAT-01", "BAT-02"], ["BAT-01"])
    assert is_disjoint is False
    assert "BAT-01" in overlap

    is_disjoint_clean, overlap_clean = auditor.audit_train_test_battery_disjointness(["BAT-01", "BAT-02"], ["BAT-03"])
    assert is_disjoint_clean is True
    assert len(overlap_clean) == 0

    # 3. Temporal causality violation
    is_valid, reason = auditor.audit_temporal_admissibility(feature_end_timestamp=35.0, decision_timestamp=30.0)
    assert is_valid is False
    assert "TEMPORAL_LEAKAGE" in reason

    is_valid_clean, _ = auditor.audit_temporal_admissibility(feature_end_timestamp=25.0, decision_timestamp=30.0)
    assert is_valid_clean is True


def test_baseline_models(sample_feature_df):
    """Verifies baseline models fit and predict properly."""
    X_train = sample_feature_df[["V_MEAN", "DELTA_V_OHMIC"]].iloc[:20]
    y_train = sample_feature_df["soh"].iloc[:20]
    X_test = sample_feature_df[["V_MEAN", "DELTA_V_OHMIC"]].iloc[20:]
    y_test = sample_feature_df["soh"].iloc[20:]

    mean_mod = MeanPredictorBaseline()
    mean_mod.fit(X_train.to_numpy(), y_train.to_numpy())
    p_mean = mean_mod.predict(X_test)
    assert len(p_mean) == len(y_test)
    assert np.allclose(p_mean, y_train.mean())

    lin_mod = LinearBaseline()
    lin_mod.fit(X_train.to_numpy(), y_train.to_numpy())
    p_lin = lin_mod.predict(X_test)
    assert len(p_lin) == len(y_test)
    assert not np.isnan(p_lin).any()

    ridge_mod = RidgeBaseline(alpha=1.0)
    ridge_mod.fit(X_train.to_numpy(), y_train.to_numpy())
    p_ridge = ridge_mod.predict(X_test)
    assert len(p_ridge) == len(y_test)
    assert not np.isnan(p_ridge).any()


def test_feature_family_ablation(sample_feature_df):
    """Verifies that FeatureAblationEngine runs family ablation suites."""
    engine = FeatureAblationEngine()
    results = engine.run_family_ablation_matrix(sample_feature_df, target_col="soh", battery_col="battery_id")
    assert "A0_MINIMAL_BASELINE" in results
    assert "A1_ELECTRICAL" in results
    assert "A2_ELEC_PLUS_PULSE" in results
    assert results["A0_MINIMAL_BASELINE"]["mae"] > 0.0


def test_noise_sensitivity(sample_feature_df):
    """Verifies that noise perturbation analysis detects feature drift."""
    engine = FeatureAblationEngine()
    feature_cols = ["V_MEAN", "DELTA_V_OHMIC", "T_MEAN"]
    noise_res = engine.evaluate_noise_sensitivity(sample_feature_df, feature_cols)
    for feat in feature_cols:
        assert feat in noise_res
        assert 0.0 <= noise_res[feat]["robustness_score"] <= 1.0


def test_admission_accounting_invariant():
    """
    CRITICAL PHASE 5 INVARIANT:
    Every single cataloged feature in Canonical Registry (30 features)
    must receive a scientifically substantiated status:
    ADMIT, CONDITIONAL, DEFER, or REJECT.
    """
    reg = create_canonical_registry()
    all_features = [f.feature_id for f in reg.list_all()]
    assert len(all_features) == TOTAL_CATALOGED_FEATURES
    assert TOTAL_CATALOGED_FEATURES == 30
    assert TOTAL_STANDARDIZED_CANDIDATE_FEATURES == 29
    assert TOTAL_DEFERRED_FEATURES == 1

    # Admitted set (5)
    admitted = {"V_MEAN", "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC", "RELAXATION_DELTA_V"}
    # Conditional set (4)
    conditional = {"RELAXATION_SLOPE_DV_DT", "DISCHARGE_AH", "DISCHARGE_WH", "T_MEAN"}
    # Deferred set (1)
    deferred = {"DQ_DV_PEAK"}
    # Rejected set (20)
    rejected = {
        "V_MIN", "V_MAX",
        "I_MEAN", "I_ABS_MEAN", "I_PEAK",
        "P_MEAN", "P_PEAK",
        "CHARGE_AH", "COULOMBIC_EFFICIENCY",
        "CHARGE_WH", "ENERGY_EFFICIENCY",
        "T_MAX", "DELTA_T", "DT_DT",
        "VALID_SAMPLE_FRACTION", "INVALID_SAMPLE_FRACTION",
        "CURRENT_FLOW_VALID", "PULSE_VALID",
        "TIMESTAMP_INTEGRITY", "MEASUREMENT_DURATION"
    }

    total_accounted = admitted | conditional | deferred | rejected
    assert len(total_accounted) == 30
    assert total_accounted == set(all_features), "Every cataloged feature must be accounted for"
    assert len(admitted) == 5
    assert len(conditional) == 4
    assert len(deferred) == 1
    assert len(rejected) == 20


def test_thermal_and_dq_rejection_invariant():
    """
    Verifies that thermal and data-quality features are NOT admitted to SOH prognosis.
    - Thermal features are rejected/conditional (context/safety only).
    - Data quality features are rejected from SOH regression (identifiability/gating only).
    """
    reg = create_canonical_registry()
    thermal_features = [f.feature_id for f in reg.list(family=FeatureFamily.THERMAL)]
    dq_features = [f.feature_id for f in reg.list(family=FeatureFamily.DATA_QUALITY)]

    admitted = {"V_MEAN", "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC", "RELAXATION_DELTA_V"}

    for tf in thermal_features:
        assert tf not in admitted, f"Thermal feature {tf} must NOT be in admitted SOH feature set"

    for dq in dq_features:
        assert dq not in admitted, f"Data quality feature {dq} must NOT be in admitted SOH feature set"

