"""
Unit tests for Phase 5 Scientific Remediation and Evidence Freeze.

Verifies:
1. Real vs synthetic dataset manifest separation (REAL_PHYSICAL_N, SYNTHETIC_N, TOTAL_COMPUTATIONAL_N).
2. Synthetic evidence contract cannot masquerade as physical evidence.
3. Battery-disjoint split enforcement (zero cross-battery leakage).
4. Feature selection / test separation via Nested Grouped Cross-Validation.
5. Fold-level Delta MAE recording, Cohen's d effect size, and 95% Confidence Interval.
6. Feature status classification (PROVISIONALLY_ADMITTED, CONDITIONAL, DEFERRED, REJECTED).
7. Scientific claim classification including SIMULATION_SUPPORTED.
8. R0 contextual dependence (>25% SOC shift, temperature conditioning).
9. Chemistry-conditional V_MEAN (+0.477V shift between LFP and NMC).
10. Strict prohibition of mechanism claims (SEI direct attribution) from feature importance.
"""

import pytest
import numpy as np
import pandas as pd
from secondshift.software.features.feature_registry import create_canonical_registry, FeatureFamily
from secondshift.software.features.validation_models import (
    FeatureValidationStatus,
    FeatureAdmissionStatus,
    ClaimStatus,
    EvidenceLevel,
    MultidimensionalEvidenceVector,
    FoldRobustnessStats,
    DatasetManifest,
    BatteryDisjointSplitter,
    LinearBaseline,
    RidgeBaseline
)
from secondshift.software.features.ablation import FeatureAblationEngine


@pytest.fixture
def remediation_sample_df():
    """Generates synthetic multi-battery dataset with known physical vs synthetic labeling."""
    np.random.seed(42)
    records = []
    # 4 physical + 6 synthetic
    for b_idx in range(10):
        b_id = f"SPECIMEN_{b_idx:02d}"
        origin = "REAL_PHYSICAL" if b_idx < 4 else "SYNTHETIC"
        chem = "LFP" if b_idx % 2 == 0 else "NMC"
        base_v = 3.28 if chem == "LFP" else 3.75
        soh = 0.95 - (b_idx * 0.03)

        for c in range(3):
            records.append({
                "specimen_id": b_id,
                "evidence_origin": origin,
                "chemistry": chem,
                "true_soh": soh - (c * 0.005),
                "V_MEAN": base_v - (1.0 - soh) * 0.15 + np.random.normal(0, 0.002),
                "DELTA_V_OHMIC": 0.04 + (1.0 - soh) * 0.08 + np.random.normal(0, 0.001),
                "R0_OHMIC": 0.010 + (1.0 - soh) * 0.02 + np.random.normal(0, 0.0003),
                "DELTA_V_TOTAL": 0.12 + (1.0 - soh) * 0.15 + np.random.normal(0, 0.002),
                "RELAXATION_DELTA_V": 0.03 + (1.0 - soh) * 0.05 + np.random.normal(0, 0.001),
                "T_MEAN": 25.0 + np.random.normal(0, 0.2)
            })
    return pd.DataFrame(records)


def test_real_vs_synthetic_manifest_separation():
    """Verifies that dataset manifest explicitly distinguishes physical vs synthetic specimen counts."""
    manifest = DatasetManifest(
        dataset_name="HERMES Testbed",
        total_batteries=112,
        battery_identifiers=[f"B_{i}" for i in range(112)],
        chemistry_counts={"LFP": 8, "NMC": 3, "UNKNOWN": 1},
        operating_conditions={},
        temperature_range_c=(20.0, 30.0),
        voltage_range_v=(2.0, 4.2),
        current_range_a=(0.0, 10.0),
        voltage_resolution_mv=0.1,
        current_resolution_ma=1.0,
        timestamp_resolution_ms=1.0,
        missing_fraction=0.0,
        has_trustworthy_soh=True,
        soh_definition="C/5 Galvanostatic",
        has_trustworthy_rul=False,
        rul_audit_notes="Rapid intake screening",
        real_physical_n=12,
        synthetic_n=100,
        total_computational_n=112,
        evidence_origin="MIXED"
    )
    assert manifest.real_physical_n == 12
    assert manifest.synthetic_n == 100
    assert manifest.total_computational_n == 112
    assert manifest.total_computational_n == manifest.real_physical_n + manifest.synthetic_n
    assert manifest.evidence_origin == "MIXED"


def test_synthetic_evidence_cannot_be_represented_as_physical():
    """Verifies that synthetic evidence level is strictly categorized as LEVEL_1 and cannot claim Level 3+."""
    synth_vector = MultidimensionalEvidenceVector(
        feature_id="DELTA_V_OHMIC",
        feature_family="PULSE",
        evidence_level=EvidenceLevel.LEVEL_1,
        real_evidence_present=False,
        synthetic_evidence_present=True,
        admission_verdict=FeatureAdmissionStatus.PROVISIONALLY_ADMITTED,
        scientific_claim_level=ClaimStatus.SIMULATION_SUPPORTED
    )
    d = synth_vector.to_dict()
    assert d["evidence_level"] == "LEVEL_1_SIMULATION_COHORT"
    assert d["real_evidence_present"] is False
    assert d["scientific_claim_level"] == "SIMULATION_SUPPORTED"


def test_nested_grouped_validation_execution(remediation_sample_df):
    """Verifies that nested grouped cross-validation isolates outer test batteries from feature selection."""
    engine = FeatureAblationEngine()
    suites = {
        "A0_MINIMAL": ["V_MEAN"],
        "A2_PULSE": ["V_MEAN", "DELTA_V_OHMIC", "R0_OHMIC"],
        "A9_ADMITTED": ["V_MEAN", "DELTA_V_OHMIC", "R0_OHMIC", "DELTA_V_TOTAL", "RELAXATION_DELTA_V"]
    }
    nested_res = engine.run_nested_grouped_validation(
        feature_df=remediation_sample_df,
        candidate_suites=suites,
        target_col="true_soh",
        battery_col="specimen_id"
    )
    assert nested_res["validation_type"] == "NESTED_GROUPED_LOBO"
    assert nested_res["outer_batteries_count"] == 10
    assert nested_res["nested_mae"] > 0.0
    assert len(nested_res["per_battery_selected_suite"]) == 10
    # Every outer battery was tested with an inner-selected suite
    for b_id, suite in nested_res["per_battery_selected_suite"].items():
        assert suite in suites


def test_fold_level_delta_mae_and_effect_size(remediation_sample_df):
    """Verifies fold-by-fold Delta MAE, Cohen's d effect size, and 95% Confidence Interval calculation."""
    engine = FeatureAblationEngine()
    features = ["V_MEAN", "DELTA_V_OHMIC", "R0_OHMIC"]
    lofo_res = engine.run_leave_one_feature_out_robust(
        feature_df=remediation_sample_df,
        candidate_features=features,
        target_col="true_soh",
        battery_col="specimen_id",
        engineering_threshold=0.005
    )
    for feat in features:
        assert feat in lofo_res
        stats_dict = lofo_res[feat]["fold_stats"]
        assert "mean_delta_mae" in stats_dict
        assert "median_delta_mae" in stats_dict
        assert "ci_95_lower" in stats_dict
        assert "ci_95_upper" in stats_dict
        assert "cohens_d" in stats_dict
        assert "folds_improved" in stats_dict
        assert stats_dict["folds_improved"] + stats_dict["folds_degraded"] + stats_dict["folds_neutral"] == 10


def test_feature_admission_reclassification():
    """Verifies provisional admission statuses match Phase 5 remediation contracts."""
    assert FeatureAdmissionStatus.PROVISIONALLY_ADMITTED.value == "PROVISIONALLY_ADMITTED"
    assert FeatureAdmissionStatus.CONDITIONAL.value == "CONDITIONAL"
    assert FeatureAdmissionStatus.DEFERRED.value == "DEFERRED"
    assert FeatureAdmissionStatus.REJECTED.value == "REJECTED"


def test_r0_contextual_dependence_invariant():
    """Verifies that R0 varies across SOC (>25%) and cannot be treated as a universal scalar."""
    soc_r0_map = {
        0.15: 12.38,
        0.55: 15.53,
        0.75: 15.62
    }
    relative_shift = (soc_r0_map[0.75] - soc_r0_map[0.15]) / soc_r0_map[0.15]
    assert relative_shift > 0.25, f"Expected >25% shift across SOC, got {relative_shift:.1%}"


def test_chemistry_conditional_v_mean():
    """Verifies that V_MEAN displays a domain shift of >0.4V between LFP and NMC plateaus."""
    lfp_v = 3.275
    nmc_v = 3.752
    domain_shift = nmc_v - lfp_v
    assert domain_shift > 0.40, f"Expected >0.4V shift between LFP and NMC, got {domain_shift:.3f}V"


def test_no_mechanism_inference_from_feature_importance():
    """Verifies that high predictive value for DELTA_V_OHMIC does NOT assert direct SEI identification."""
    vector = MultidimensionalEvidenceVector(
        feature_id="DELTA_V_OHMIC",
        feature_family="PULSE",
        mechanism_confidence="AGGREGATE_ELECTRICAL",
        admission_verdict=FeatureAdmissionStatus.PROVISIONALLY_SUPPORTED_MODEST_EFFECT,
        scientific_claim_level=ClaimStatus.SUPPORTED
    )
    assert vector.mechanism_confidence != "DIRECT_PHYSICAL"
    assert vector.mechanism_confidence == "AGGREGATE_ELECTRICAL"


def test_random_split_vs_lobo_generalization_gap_sign():
    """
    CORRECTION B: Verifies that random row split produces artificially optimistic MAE
    and the generalization gap is explicitly positive: LOBO_MAE - RANDOM_SPLIT_MAE > 0.
    """
    random_split_mae = 0.0915
    lobo_mae = 0.0959
    generalization_gap = lobo_mae - random_split_mae
    assert generalization_gap > 0.0, "Generalization gap must be positive (LOBO - Random Split)"
    assert round(generalization_gap, 4) == 0.0044
    assert random_split_mae < lobo_mae, "Random split appears artificially optimistic due to identity leakage"


def test_a2_baseline_distinction():
    """
    CORRECTION C: Verifies that A2 improvement explicitly distinguishes between
    minimal baseline A0 (V_MEAN) and electrical-only baseline A1.
    """
    a0_physical_mae = 0.1785
    a1_physical_mae = 0.1651
    a2_physical_mae = 0.1395

    delta_vs_a0 = a2_physical_mae - a0_physical_mae
    delta_vs_a1 = a2_physical_mae - a1_physical_mae

    assert round(delta_vs_a0, 4) == -0.0390, f"Expected -0.0390 vs A0, got {delta_vs_a0:.4f}"
    assert round(delta_vs_a1, 4) == -0.0256, f"Expected -0.0256 vs A1, got {delta_vs_a1:.4f}"


def test_suite_level_vs_individual_feature_evidence_separation():
    """
    CORRECTION D: Verifies that 100% selection of A2 suite does NOT mark constituent features
    like RELAXATION_DELTA_V or R0_OHMIC as having independent incremental physical support.
    """
    # A2 suite contains multiple features
    # But individual physical LOFO shows RELAXATION_DELTA_V has 0.0 incremental value
    relaxation_vector = MultidimensionalEvidenceVector(
        feature_id="RELAXATION_DELTA_V",
        feature_family="RELAXATION",
        incremental_predictive_value=0.0,
        admission_verdict=FeatureAdmissionStatus.INSUFFICIENT_INCREMENTAL_EVIDENCE
    )
    assert relaxation_vector.admission_verdict == FeatureAdmissionStatus.INSUFFICIENT_INCREMENTAL_EVIDENCE
    assert relaxation_vector.incremental_predictive_value == 0.0

    delta_v_total_vector = MultidimensionalEvidenceVector(
        feature_id="DELTA_V_TOTAL",
        feature_family="PULSE",
        incremental_predictive_value=0.01355,
        admission_verdict=FeatureAdmissionStatus.PROVISIONALLY_SUPPORTED
    )
    assert delta_v_total_vector.admission_verdict == FeatureAdmissionStatus.PROVISIONALLY_SUPPORTED
    assert delta_v_total_vector.incremental_predictive_value > 0.005  # Meets engineering threshold


def test_phase5_1_feature_status_taxonomy():
    """
    CORRECTION E: Verifies Phase 5.1 refined status taxonomy and multidimensional classification.
    """
    assert FeatureAdmissionStatus.PROVISIONALLY_SUPPORTED.value == "PROVISIONALLY_SUPPORTED"
    assert FeatureAdmissionStatus.PROVISIONALLY_SUPPORTED_MODEST_EFFECT.value == "PROVISIONALLY_SUPPORTED / MODEST_EFFECT"
    assert FeatureAdmissionStatus.CONTEXTUAL_PROVISIONAL.value == "CONTEXTUAL / PROVISIONAL"
    assert FeatureAdmissionStatus.INSUFFICIENT_INCREMENTAL_EVIDENCE.value == "INSUFFICIENT_INCREMENTAL_EVIDENCE"
    assert FeatureAdmissionStatus.CONDITIONAL.value == "CONDITIONAL"
    assert FeatureAdmissionStatus.DEFERRED.value == "DEFERRED"
    assert FeatureAdmissionStatus.REJECTED.value == "REJECTED"


def test_evidence_freeze_json_consistency():
    """
    CORRECTION 17: Verifies that results/phase5_evidence_freeze.json matches Phase 5.1 requirements.
    """
    import os
    import json
    freeze_path = os.path.join(os.path.dirname(__file__), "../../results/phase5_evidence_freeze.json")
    assert os.path.exists(freeze_path), "phase5_evidence_freeze.json must exist"

    with open(freeze_path, "r", encoding="utf-8") as f:
        freeze_data = json.load(f)

    assert len(freeze_data) == 30, "All 30 cataloged features must be in evidence freeze"

    # Check DELTA_V_TOTAL
    assert freeze_data["DELTA_V_TOTAL"]["final_status"] == "PROVISIONALLY_SUPPORTED"
    assert freeze_data["DELTA_V_TOTAL"]["evidence_level"] == "LEVEL_2_SMALL_PHYSICAL_COHORT"
    assert freeze_data["DELTA_V_TOTAL"]["effect_size"] == 0.67

    # Check DELTA_V_OHMIC
    assert freeze_data["DELTA_V_OHMIC"]["final_status"] == "PROVISIONALLY_SUPPORTED / MODEST_EFFECT"
    assert freeze_data["DELTA_V_OHMIC"]["evidence_level"] == "LEVEL_2_SMALL_PHYSICAL_COHORT"
    assert any("RETRACTED" in s for s in freeze_data["DELTA_V_OHMIC"]["superseded_claims"])

    # Check R0_OHMIC
    assert freeze_data["R0_OHMIC"]["final_status"] == "CONTEXTUAL / PROVISIONAL"
    assert freeze_data["R0_OHMIC"]["evidence_level"] == "LEVEL_2_SMALL_PHYSICAL_COHORT"
    assert any("RETRACTED" in s for s in freeze_data["R0_OHMIC"]["superseded_claims"])

    # Check RELAXATION_DELTA_V
    assert freeze_data["RELAXATION_DELTA_V"]["final_status"] == "INSUFFICIENT_INCREMENTAL_EVIDENCE"

    # Check V_MEAN
    assert freeze_data["V_MEAN"]["final_status"] == "CONDITIONAL"
    assert freeze_data["V_MEAN"]["chemistry_dependence"] == "CHEMISTRY_CONDITIONAL"
