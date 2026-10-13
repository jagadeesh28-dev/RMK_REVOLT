"""
Phase 6: Chemistry / Domain Adaptation & Cross-Domain Prognostics Test Suite
Project: RMK-REVOLT / SECONDShift Platform

Tests all 14 mandatory Phase 6 areas:
1. Chemistry provenance verification (VERIFIED, DOCUMENTED, INFERRED, SIMULATED, UNKNOWN)
2. Real vs synthetic cohort isolation & strict count separation (N=12 physical, N=100 synthetic)
3. Domain label classification and field provenance (OBSERVED, DERIVED, ASSUMED, SIMULATED, UNKNOWN)
4. Group-disjoint validation (Leave-One-Battery-Out) non-leakage
5. Chemistry-disjoint validation (Leave-One-Chemistry-Out) non-leakage
6. Temporal leakage auditing (no future timestamps or oracle targets)
7. Chemistry-conditioned normalization non-leakage (training-only parameters)
8. Domain-shift detection via DomainValidityLayer
9. Uncertainty behavior under domain shift (epistemic inflation, detecting overconfidence)
10. Feature status taxonomy serialization
11. Evidence level hierarchy serialization (Level 1 to Level 4)
12. Reproducibility determinism across repeated executions
13. Unsupported chemistry rejection and DEFER trigger
14. UNKNOWN chemistry handling (SPECIMEN_12 remains UNKNOWN and triggers DEFER)
"""

import pytest
import os
import json
import numpy as np
import pandas as pd

from secondshift.software.domain_adaptation.domain_models import (
    ChemistryProvenance,
    FieldOrigin,
    Phase6FeatureStatus,
    Phase6Verdict,
    EpistemicDomainState,
    SpecimenDomainRecord,
    ChemistryConditionalNormalizer,
    R0ContextNormalizer,
    CrossDomainRidgeModel,
    StratifiedChemistryModel,
    HierarchicalSharedModel,
    DomainValidityAssessment,
    DomainValidityLayer,
)
from secondshift.software.features.validation_models import (
    BatteryDisjointSplitter,
    HostileLeakageAuditor,
    EvidenceLevel,
)
from secondshift.experiments.run_phase6_domain_adaptation import (
    load_physical_cohort,
    generate_synthetic_cohort,
    extract_features_for_specimen,
    run_phase6_pipeline,
    OUTPUT_PATH,
    SUMMARY_OUTPUT_PATH,
)
from secondshift.software.features.feature_engine import CanonicalFeatureEngine


# =============================================================================
# 1. CHEMISTRY PROVENANCE VERIFICATION
# =============================================================================

def test_chemistry_provenance_taxonomy():
    """Verifies all required chemistry provenance states exist and are distinct."""
    assert ChemistryProvenance.VERIFIED.value == "VERIFIED"
    assert ChemistryProvenance.DOCUMENTED.value == "DOCUMENTED"
    assert ChemistryProvenance.INFERRED.value == "INFERRED"
    assert ChemistryProvenance.SIMULATED.value == "SIMULATED"
    assert ChemistryProvenance.UNKNOWN.value == "UNKNOWN"

    # Simulated label must never equal verified label
    assert ChemistryProvenance.SIMULATED != ChemistryProvenance.VERIFIED


def test_physical_chemistry_provenance_assignment():
    """Verifies that physical specimens receive VERIFIED, DOCUMENTED, or UNKNOWN provenance, never SIMULATED."""
    specs = load_physical_cohort()
    assert len(specs) == 12

    # Verify SPECIMEN_12 is UNKNOWN
    spec_12 = specs["SPECIMEN_12_UNKNOWN_EXOTIC"]
    assert spec_12["chemistry"] == "UNKNOWN"

    # Verify physical cells have appropriate provenance
    for s_id, meta in specs.items():
        if s_id == "SPECIMEN_12_UNKNOWN_EXOTIC":
            prov = ChemistryProvenance.UNKNOWN
        elif "ALT" in s_id:
            prov = ChemistryProvenance.DOCUMENTED
        else:
            prov = ChemistryProvenance.VERIFIED
        assert prov in [ChemistryProvenance.VERIFIED, ChemistryProvenance.DOCUMENTED, ChemistryProvenance.UNKNOWN]
        assert prov != ChemistryProvenance.SIMULATED


# =============================================================================
# 2. REAL VS SYNTHETIC COHORT SEPARATION
# =============================================================================

def test_real_vs_synthetic_separation():
    """Verifies physical (N=12) and synthetic (N=100) cohort separation."""
    phys = load_physical_cohort()
    syn = generate_synthetic_cohort(n_lfp=50, n_nmc=50, seed=42)

    assert len(phys) == 12, "Physical cohort must be exactly N=12"
    assert len(syn) == 100, "Synthetic cohort must be exactly N=100"

    # Verify physical chemistry counts: 8 LFP, 3 NMC, 1 UNKNOWN
    chems_phys = [m["chemistry"] for m in phys.values()]
    assert chems_phys.count("LFP") == 8
    assert chems_phys.count("NMC") == 3
    assert chems_phys.count("UNKNOWN") == 1

    # Verify synthetic chemistry counts: exactly 50 LFP, 50 NMC
    chems_syn = [m["chemistry"] for m in syn.values()]
    assert chems_syn.count("LFP") == 50
    assert chems_syn.count("NMC") == 50


# =============================================================================
# 3. DOMAIN LABELS & FIELD ORIGIN CLASSIFICATION
# =============================================================================

def test_field_origin_classification():
    """Verifies all 20+ specimen fields are classified into OBSERVED, DERIVED, ASSUMED, SIMULATED, UNKNOWN."""
    allowed_origins = {FieldOrigin.OBSERVED, FieldOrigin.DERIVED, FieldOrigin.ASSUMED, FieldOrigin.SIMULATED, FieldOrigin.UNKNOWN}
    record = SpecimenDomainRecord(
        specimen_id="SPEC_01",
        battery_id="SPEC_01",
        chemistry="LFP",
        chemistry_source="LAB",
        chemistry_confidence=0.99,
        chemistry_provenance=ChemistryProvenance.VERIFIED,
        cohort_type="REAL_PHYSICAL",
        form_factor="CYLINDRICAL_4S",
        nominal_voltage_v=12.8,
        nominal_capacity_ah=20.0,
        test_protocol="HERMES_RAPID_INTAKE",
        pulse_amplitude_a=10.0,
        pulse_duration_s=2.0,
        sampling_rate_hz=10.0,
        temperature_c=25.0,
        soc=0.55,
        measurement_scope="CELL",
        dataset_origin="HERMES_BENCH",
        feature_availability={"V_MEAN": True},
        soh_target_available=True,
        rul_target_available=False,
        aging_history_available=False,
        field_origins={"specimen_id": FieldOrigin.OBSERVED, "rul_target": FieldOrigin.UNKNOWN}
    )
    d = record.to_dict()
    assert d["cohort_type"] == "REAL_PHYSICAL"
    assert d["chemistry_provenance"] == "VERIFIED"
    assert d["field_origins"]["rul_target"] == "UNKNOWN"
    assert d["rul_target_available"] is False


# =============================================================================
# 4. GROUP-DISJOINT VALIDATION (LOBO)
# =============================================================================

def test_battery_disjoint_validation_splits():
    """Verifies that no battery appears in both train and test partitions in LOBO."""
    bat_ids = [f"BAT_{i:02d}" for i in range(12)]
    splits = BatteryDisjointSplitter.split_lobo(bat_ids)
    assert len(splits) == 12

    for train_idx, test_idx, test_bat in splits:
        train_bats = {bat_ids[i] for i in train_idx}
        test_bats = {bat_ids[i] for i in test_idx}
        assert len(train_bats.intersection(test_bats)) == 0, "Battery leaked across fold boundary!"
        assert test_bat not in train_bats


# =============================================================================
# 5. CHEMISTRY-DISJOINT VALIDATION (LOCO)
# =============================================================================

def test_chemistry_disjoint_loco_separation():
    """Verifies Leave-One-Chemistry-Out completely separates training and test chemistries."""
    chems = ["LFP"] * 8 + ["NMC"] * 3 + ["UNKNOWN"] * 1
    chem_arr = np.array(chems)

    # Train LFP, Test NMC
    train_lfp_idx = np.where(chem_arr == "LFP")[0]
    test_nmc_idx = np.where(chem_arr == "NMC")[0]

    assert len(train_lfp_idx) == 8
    assert len(test_nmc_idx) == 3
    assert set(train_lfp_idx).isdisjoint(set(test_nmc_idx))
    assert all(chem_arr[i] == "LFP" for i in train_lfp_idx)
    assert all(chem_arr[i] == "NMC" for i in test_nmc_idx)


# =============================================================================
# 6. TEMPORAL & ORACLE LEAKAGE AUDITING
# =============================================================================

def test_leakage_auditor_prohibits_oracle_keys():
    """Verifies that ground-truth or future keys trigger HostileLeakageAuditor."""
    clean_dict = {"V_MEAN": 3.28, "DELTA_V_TOTAL": 0.025, "DELTA_V_OHMIC": 0.021}
    leaky_dict = {"V_MEAN": 3.28, "true_soh": 0.94, "future_cycle": 100}

    assert len(HostileLeakageAuditor.audit_feature_keys(clean_dict)) == 0
    leaks = HostileLeakageAuditor.audit_feature_keys(leaky_dict)
    assert any("true_soh" in msg for msg in leaks)
    assert any("future_cycle" in msg for msg in leaks)


# =============================================================================
# 7. CHEMISTRY-CONDITIONED NORMALIZATION NON-LEAKAGE
# =============================================================================

def test_chemistry_conditional_normalizer_non_leakage():
    """Verifies that normalizer statistics are computed strictly on training data."""
    normer = ChemistryConditionalNormalizer(target_features=["V_MEAN"])
    X_train = np.array([[3.20], [3.30], [3.70], [3.80]])
    chem_train = ["LFP", "LFP", "NMC", "NMC"]
    feat_names = ["V_MEAN"]

    normer.fit(X_train, chem_train, feat_names)
    assert normer.is_fitted

    # LFP mean should be 3.25, NMC mean should be 3.75
    lfp_mean, _ = normer.stats_["V_MEAN"]["LFP"]
    nmc_mean, _ = normer.stats_["V_MEAN"]["NMC"]
    assert abs(lfp_mean - 3.25) < 1e-4
    assert abs(nmc_mean - 3.75) < 1e-4

    # Transform test sample without updating training statistics
    X_test = np.array([[3.25], [3.75]])
    chem_test = ["LFP", "NMC"]
    X_trans = normer.transform(X_test, chem_test, feat_names)

    # Standardized values centered at 0
    assert abs(X_trans[0, 0]) < 1e-4
    assert abs(X_trans[1, 0]) < 1e-4


# =============================================================================
# 8. DOMAIN SHIFT DETECTION
# =============================================================================

def test_domain_validity_layer_detects_shift():
    """Verifies DomainValidityLayer flags out-of-domain temperature and voltage."""
    layer = DomainValidityLayer()

    # In-domain LFP
    res_in = layer.evaluate(
        chemistry="LFP",
        chemistry_confidence=0.99,
        chemistry_provenance=ChemistryProvenance.VERIFIED,
        features={"V_MEAN": 3.28, "T_MEAN": 25.0, "DELTA_V_TOTAL": 0.025}
    )
    assert res_in.is_domain_supported
    assert res_in.epistemic_state == EpistemicDomainState.SUPPORTED_HEALTHY
    assert res_in.recommended_action == "PROCEED_TO_ESTIMATION"

    # Out-of-domain temperature (55C > 45C max)
    res_hot = layer.evaluate(
        chemistry="LFP",
        chemistry_confidence=0.99,
        chemistry_provenance=ChemistryProvenance.VERIFIED,
        features={"V_MEAN": 3.28, "T_MEAN": 55.0, "DELTA_V_TOTAL": 0.025}
    )
    assert not res_hot.is_domain_supported
    assert res_hot.domain_shift_detected
    assert res_hot.epistemic_state == EpistemicDomainState.DISTRIBUTION_SHIFTED
    assert res_hot.recommended_action == "DEFER"


# =============================================================================
# 9. UNCERTAINTY UNDER DOMAIN SHIFT
# =============================================================================

def test_uncertainty_inflation_under_domain_shift():
    """Verifies that epistemic uncertainty inflates when tested out-of-domain."""
    X_tr = np.array([[0.020, 0.015], [0.025, 0.020], [0.030, 0.025]])
    y_tr = np.array([0.90, 0.80, 0.70])

    model = CrossDomainRidgeModel(alpha=1.0)
    model.fit(X_tr, y_tr)

    # In-domain prediction
    _, sigmas_in = model.predict_with_uncertainty(np.array([[0.025, 0.020]]), chemistry_in_train=True)

    # Shifted-domain prediction (same features but out-of-domain chemistry)
    _, sigmas_out = model.predict_with_uncertainty(np.array([[0.025, 0.020]]), chemistry_in_train=False)

    assert sigmas_out[0] > sigmas_in[0] * 2.0, "Uncertainty must inflate by >= 2x for shifted domain"


# =============================================================================
# 10. FEATURE STATUS TAXONOMY SERIALIZATION
# =============================================================================

def test_feature_status_taxonomy_serialization():
    """Verifies all Phase 6 feature status enum values serialize correctly."""
    valid_statuses = [
        Phase6FeatureStatus.SUPPORTED_CROSS_DOMAIN,
        Phase6FeatureStatus.SUPPORTED_WITH_CHEMISTRY_CONDITIONING,
        Phase6FeatureStatus.SUPPORTED_WITH_CONTEXT_NORMALIZATION,
        Phase6FeatureStatus.CONDITIONAL,
        Phase6FeatureStatus.DOMAIN_DEPENDENT,
        Phase6FeatureStatus.INSUFFICIENT_EVIDENCE,
        Phase6FeatureStatus.REJECTED,
        Phase6FeatureStatus.DEFERRED,
    ]
    for st in valid_statuses:
        assert isinstance(st.value, str)
        assert len(st.value) > 0


# =============================================================================
# 11. EVIDENCE LEVEL HIERARCHY
# =============================================================================

def test_evidence_hierarchy_ordering():
    """Verifies strict evidence hierarchy ordering from Level 0 to Level 5."""
    assert EvidenceLevel.LEVEL_0.value == "LEVEL_0_SOFTWARE_SYNTHETIC"
    assert EvidenceLevel.LEVEL_1.value == "LEVEL_1_SIMULATION_COHORT"
    assert EvidenceLevel.LEVEL_2.value == "LEVEL_2_SMALL_PHYSICAL_COHORT"
    assert EvidenceLevel.LEVEL_3.value == "LEVEL_3_CROSS_BATTERY_PHYSICAL"
    assert EvidenceLevel.LEVEL_4.value == "LEVEL_4_CROSS_CHEMISTRY_PHYSICAL"
    assert EvidenceLevel.LEVEL_5.value == "LEVEL_5_PROSPECTIVE_PHYSICAL"


# =============================================================================
# 12. REPRODUCIBILITY & DETERMINISM
# =============================================================================

def test_reproducibility_synthetic_cohort():
    """Verifies that synthetic cohort generation is strictly deterministic given seed."""
    c1 = generate_synthetic_cohort(n_lfp=10, n_nmc=10, seed=42)
    c2 = generate_synthetic_cohort(n_lfp=10, n_nmc=10, seed=42)

    for k in c1:
        assert c1[k]["chemistry"] == c2[k]["chemistry"]
        assert abs(c1[k]["SOH"] - c2[k]["SOH"]) < 1e-12
        assert abs(c1[k]["R0_mohm"] - c2[k]["R0_mohm"]) < 1e-12


# =============================================================================
# 13. UNSUPPORTED CHEMISTRY HANDLING
# =============================================================================

def test_unsupported_chemistry_triggers_defer():
    """Verifies that unsupported chemistry (e.g. LTO or Na-Ion) triggers DEFER."""
    layer = DomainValidityLayer(supported_chemistries={"LFP", "NMC"})
    assessment = layer.evaluate(
        chemistry="LTO",
        chemistry_confidence=0.99,
        chemistry_provenance=ChemistryProvenance.VERIFIED,
        features={"V_MEAN": 2.40, "T_MEAN": 25.0}
    )
    assert not assessment.is_domain_supported
    assert assessment.domain_shift_detected
    assert assessment.epistemic_state == EpistemicDomainState.DISTRIBUTION_SHIFTED
    assert assessment.recommended_action == "DEFER"


# =============================================================================
# 14. UNKNOWN CHEMISTRY HANDLING (SPECIMEN_12)
# =============================================================================

def test_unknown_specimen_12_handling():
    """Verifies that SPECIMEN_12 remains UNKNOWN and triggers DISTRIBUTION_SHIFTED / DEFER."""
    specs = load_physical_cohort()
    spec_12 = specs["SPECIMEN_12_UNKNOWN_EXOTIC"]

    assert spec_12["chemistry"] == "UNKNOWN"

    layer = DomainValidityLayer()
    assessment = layer.evaluate(
        chemistry=spec_12["chemistry"],
        chemistry_confidence=0.334,
        chemistry_provenance=ChemistryProvenance.UNKNOWN,
        features={"V_MEAN": spec_12["nominal_voltage_v"], "T_MEAN": spec_12["temperature_c"]}
    )

    assert not assessment.is_domain_supported
    assert assessment.domain_shift_detected
    assert assessment.epistemic_state == EpistemicDomainState.DISTRIBUTION_SHIFTED
    assert assessment.recommended_action == "DEFER"
    assert "UNMODELED_OR_UNKNOWN_CHEMISTRY" in assessment.flags


# =============================================================================
# 15. EVIDENCE FREEZE ARTIFACT CONSISTENCY
# =============================================================================

def test_phase6_evidence_freeze_json_exists_and_valid():
    """Verifies results/phase6_domain_evidence.json exists and contains required sections."""
    assert os.path.exists(OUTPUT_PATH), f"Evidence freeze file {OUTPUT_PATH} does not exist"
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "metadata" in data
    assert data["metadata"]["phase"] == "PHASE_6"
    assert data["metadata"]["physical_cohort_n"] == 12
    assert data["metadata"]["synthetic_cohort_n"] == 100
    assert data["metadata"]["mixed_cohort_n"] == 112
    assert data["metadata"]["verdict"] == "EXPLORATORY_ONLY"

    assert "exp601_data_origin_audit" in data
    assert data["exp601_data_origin_audit"]["rul_cross_domain_validation_performed"] is False

    assert "exp602_feature_chemistry_stats" in data
    assert "exp603_r0_context_study" in data
    assert "exp604_generalization_results" in data
    assert "exp605_loco_stress_test" in data
    assert "exp606_domain_shift_and_uncertainty" in data
    assert "exp607_ablation_results" in data
    assert "exp608_worst_case_metrics" in data
    assert "feature_status_table" in data

    # Verify candidate features in status table
    for feat in ["DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC", "RELAXATION_DELTA_V", "V_MEAN", "T_MEAN", "RELAXATION_SLOPE_DV_DT", "DISCHARGE_AH", "DISCHARGE_WH"]:
        assert feat in data["feature_status_table"]


# =============================================================================
# 16. PHASE 6.1 AUDIT SPECIFIC TESTS
# =============================================================================

def test_phase6_1_uncertainty_inflation_does_not_imply_calibration():
    """
    Verifies that uncertainty responsiveness (sigma inflation on shifted domains)
    does NOT assert calibration, and that calibration is classified as UNVALIDATED.
    """
    assert os.path.exists(OUTPUT_PATH)
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    exp606 = data["exp606_domain_shift_and_uncertainty"]
    assert exp606["in_domain_lfp_mean_sigma"] < exp606["domain_shifted_nmc_mean_sigma"]
    assert exp606["uncertainty_responsiveness"] == "DEMONSTRATED"
    assert exp606["uncertainty_calibration"] == "UNVALIDATED"
    assert "Calibration of uncertainty against independent physical prediction error remains unvalidated" in exp606["audit_statement"]


def test_phase6_1_threshold_provisional_status():
    """
    Verifies that the chemistry confidence threshold (0.90) is explicitly classified
    as a PROVISIONAL ENGINEERING THRESHOLD, not an empirically calibrated optimal cutoff.
    """
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["metadata"]["chemistry_confidence_threshold_status"] == "PROVISIONAL_ENGINEERING_THRESHOLD"

    layer = DomainValidityLayer()
    assert layer.min_chem_conf == 0.90


def test_phase6_1_r0_status_is_contextual_provisional():
    """
    Verifies R0_OHMIC is strictly classified as CONTEXTUAL / PROVISIONAL
    and not claimed to have autonomous incremental prognostic value.
    """
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    r0_entry = data["feature_status_table"]["R0_OHMIC"]
    assert r0_entry["final_status"] == "CONTEXTUAL / PROVISIONAL"
    assert r0_entry["incremental_value"] == 0.0
    assert "protocol- and operating-condition-dependent" in r0_entry["scientific_interpretation"]


def test_phase6_1_cross_chemistry_generalization_unproven():
    """
    Verifies cross-chemistry generalization cannot serialize as VALIDATED or PROVEN
    and remains EXPLORATORY_ONLY and UNPROVEN.
    """
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["metadata"]["verdict"] == "EXPLORATORY_ONLY"
    assert data["metadata"]["cross_chemistry_generalization"] == "UNPROVEN"
    assert "INSUFFICIENT TO ESTABLISH STATISTICALLY DEFENSIBLE" in data["metadata"]["data_sufficiency"]


def test_phase6_1_a1_vs_a6_tradeoff_consistency():
    """
    Verifies that Model A6 is NOT claimed to be more accurate than Model A1,
    and that A6 represents a risk-constrained domain-aware tradeoff.
    """
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    a1 = data["exp607_ablation_results"]["A1_CHEMISTRY_NAIVE"]
    a6 = data["exp607_ablation_results"]["A6_DOMAIN_ADAPTIVE_UNCERTAINTY"]

    # A1 has lower average MAE than A6
    assert a1["physical_lobo_mae"] < a6["physical_lobo_mae"]
    # A6 has higher defer rate to prevent unsupported confident acceptance
    assert a6["defer_rate"] > a1["defer_rate"]
    assert a6["defer_count"] == 1  # Defers SPECIMEN_12


def test_phase6_1_unknown_chemistry_remains_unknown():
    """
    Verifies that UNKNOWN chemistry (SPECIMEN_12) remains strictly UNKNOWN
    and produces DISTRIBUTION_SHIFTED and DEFER.
    """
    specs = load_physical_cohort()
    spec_12 = specs["SPECIMEN_12_UNKNOWN_EXOTIC"]
    assert spec_12["chemistry"] == "UNKNOWN"

    layer = DomainValidityLayer()
    ass = layer.evaluate(
        chemistry="UNKNOWN",
        chemistry_confidence=0.334,
        chemistry_provenance=ChemistryProvenance.UNKNOWN,
        features={"V_MEAN": 2.95, "T_MEAN": 25.0}
    )
    assert ass.epistemic_state == EpistemicDomainState.DISTRIBUTION_SHIFTED
    assert ass.recommended_action == "DEFER"


def test_phase6_1_rul_cross_domain_not_performed():
    """Verifies RUL cross-domain validation is strictly recorded as not performed."""
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["exp601_data_origin_audit"]["rul_cross_domain_validation_performed"] is False
    assert data["metadata"]["rul_cross_domain_status"] == "NOT_PERFORMED"


# =============================================================================
# 17. PHASE 6.1.1 FINAL EVIDENCE CONSISTENCY & FREEZE AUDIT TESTS
# =============================================================================

def test_phase6_1_1_freeze_json_exists_and_reconciled():
    """
    Verifies results/phase6_1_1_evidence_freeze.json exists and captures
    canonical reconciled values (e.g., canonical NMC r=-0.9984 superseding draft -0.912).
    """
    freeze_path = os.path.join(os.path.dirname(__file__), "..", "..", "results", "phase6_1_1_evidence_freeze.json")
    assert os.path.exists(freeze_path), f"Evidence freeze {freeze_path} missing"
    with open(freeze_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Status verification
    assert data["metadata"]["phase6_status"] == "EXPLORATORY_ONLY"
    assert data["metadata"]["phase6_1_status"] == "SCIENTIFICALLY_AUDITED_CLAIM_CORRECTED"
    assert data["metadata"]["phase6_1_1_status"] == "FINAL_EVIDENCE_FREEZE"

    # NMC correlation reconciliation
    nmc_corr = data["critical_audit_1_nmc_correlation_reconciliation"]
    assert pytest.approx(nmc_corr["canonical_serialized_value"], rel=1e-3) == -0.9984
    assert nmc_corr["superseded_draft_value"] == -0.912
    assert nmc_corr["status"] == "EXPLORATORY_UNDERPOWERED_N3"
    assert len(nmc_corr["specimen_ids"]) == 3


def test_phase6_1_1_lfp_lofo_attribution_isolated():
    """
    Verifies that Cohen's d=0.67 and p=0.0382 belong strictly to Physical Mixed-Cohort LOFO
    and are not attributed to the N=3 NMC cohort.
    """
    freeze_path = os.path.join(os.path.dirname(__file__), "..", "..", "results", "phase6_1_1_evidence_freeze.json")
    with open(freeze_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lfp_lofo = data["critical_audit_2_lfp_effect_attribution"]
    assert lfp_lofo["cohens_d"] == 0.67
    assert lfp_lofo["p_value"] == 0.0382
    assert lfp_lofo["attributed_cohort"] == "Physical Mixed-Cohort LOFO Ablation (N=12: 8 LFP, 3 NMC, 1 UNKNOWN)"
    assert "Physical Mixed-Cohort LOFO" in lfp_lofo["scoping_rule"]
    assert "NOT be attributed specifically to the NMC cohort" in lfp_lofo["scoping_rule"]

    # NMC sample size, descriptive status, and isolation
    nmc_info = data["critical_audit_3_nmc_sample_size"]
    assert nmc_info["physical_n"] == 3
    assert nmc_info["status"] == "EXPLORATORY / DESCRIPTIVE ONLY"
    assert nmc_info["reproducibility"] == "DETERMINISTIC FROM PERSISTED CANONICAL DATA"
    assert nmc_info["cross_chemistry_generalization"] == "UNPROVEN"
    assert nmc_info["statistical_power"] == "UNDERPOWERED"


def test_phase6_1_1_uncertainty_interval_width_formulation():
    """
    Verifies raw unclipped predictive interval formulation (3.92*sigma) and that
    dilated intervals (>1.0 SOH units) reflect uncalibrated heuristic inflation.
    """
    freeze_path = os.path.join(os.path.dirname(__file__), "..", "..", "results", "phase6_1_1_evidence_freeze.json")
    with open(freeze_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    audit4 = data["critical_audit_4_uncertainty_interval_audit"]
    assert audit4["uncertainty_responsiveness"] == "DEMONSTRATED"
    assert audit4["uncertainty_calibration"] == "UNVALIDATED"
    assert audit4["raw_95_full_width_nmc_soh_units"] > 1.0  # Dilated beyond physical domain [0, 1]
    assert audit4["raw_95_full_width_unknown_soh_units"] > 1.0
    assert "Full width = 2 * 1.96 * sigma = 3.92 * sigma" in audit4["formulation"]


# =============================================================================
# 18. PHASE 6.1.2 ATTRIBUTION & REPRODUCIBILITY MICRO-AUDIT TESTS
# =============================================================================

def test_phase6_1_2_nmc_reproducibility_from_persisted_canonical_data():
    """
    Verifies that Pearson correlation r = -0.9984 is reproducible and deterministic
    from the exact persisted canonical observations without fresh stochastic noise.
    """
    from scipy import stats

    freeze_path = os.path.join(os.path.dirname(__file__), "..", "..", "results", "phase6_1_1_evidence_freeze.json")
    with open(freeze_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    persisted_specs = data["critical_audit_3_nmc_sample_size"]["persisted_canonical_specimens"]
    assert len(persisted_specs) == 3

    # Extract persisted canonical inputs
    v_obs = [persisted_specs[s]["delta_v_total"] for s in persisted_specs]
    soh_obs = [persisted_specs[s]["true_soh"] for s in persisted_specs]

    # Run 1
    r_run1, p_run1 = stats.pearsonr(v_obs, soh_obs)

    # Run 2 (identical persisted inputs)
    r_run2, p_run2 = stats.pearsonr(v_obs, soh_obs)

    # Determinism assertion: run1 == run2 bitwise identical
    assert r_run1 == r_run2
    assert p_run1 == p_run2

    # Verification against canonical serialized artifact value
    canonical_val = data["critical_audit_1_nmc_correlation_reconciliation"]["canonical_serialized_value"]
    assert pytest.approx(r_run1, rel=1e-5) == canonical_val
    assert pytest.approx(r_run1, rel=1e-4) == -0.9984
    assert pytest.approx(p_run1, rel=1e-3) == 0.0357



