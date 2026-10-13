"""
Phase 6.1.1: Final Evidence Consistency, Numerical Reconciliation & Freeze Script
Project: RMK-REVOLT / SECONDShift Platform
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FREEZE_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "results/phase6_1_1_evidence_freeze.json")

# Load existing Phase 6 and Phase 6.1 audit results
PHASE6_EVIDENCE_PATH = os.path.join(PROJECT_ROOT, "results/phase6_domain_evidence.json")
PHASE6_1_AUDIT_PATH = os.path.join(PROJECT_ROOT, "results/phase6_1_audit.json")

with open(PHASE6_EVIDENCE_PATH, "r", encoding="utf-8") as f:
    p6_data = json.load(f)

with open(PHASE6_1_AUDIT_PATH, "r", encoding="utf-8") as f:
    p6_1_data = json.load(f)

# Reconciled metrics
# 1. NMC Correlation:
# Serialized machine artifact value: -0.9984309956787651 (p=0.0357 descriptive on N=3)
# Superseded draft value: -0.9120
nmc_r_canonical = float(p6_data["exp602_feature_chemistry_stats"]["DELTA_V_TOTAL"]["NMC"]["physical_corr_soh"])
lfp_r_canonical = float(p6_data["exp602_feature_chemistry_stats"]["DELTA_V_TOTAL"]["LFP"]["physical_corr_soh"])

# 2. LFP LOFO effect size and p-value (from Phase 5/5.1 LOFO on physical cohort):
# Mean delta_mae = +0.01355, Cohen's d = 0.67, p_value = 0.0382, 9/12 folds improved
# Belongs strictly to physical cohort LOFO feature ablation, NOT NMC!

# 3. Uncertainty interval statistics
unc_audit = p6_1_data["part1_uncertainty_calibration_audit"]
pearson_r_err_sigma = float(unc_audit["overall_cohort"]["pearson_r_error_vs_sigma"])
pearson_p_err_sigma = float(unc_audit["overall_cohort"]["pearson_p_value"])
nmc_full_width_95 = float(unc_audit["domain_shifted_nmc"]["mean_interval_width_95"]) # 1.98787
unk_full_width_95 = float(unc_audit["unknown_exotic"]["interval_width_95"]) # 2.27826
nmc_half_width_95 = nmc_full_width_95 / 2.0
unk_half_width_95 = unk_full_width_95 / 2.0

# 4. A1 vs A6 tradeoff
a1_mae = float(p6_data["exp607_ablation_results"]["A1_CHEMISTRY_NAIVE"]["physical_lobo_mae"]) # 0.13701769
a6_mae = float(p6_data["exp607_ablation_results"]["A6_DOMAIN_ADAPTIVE_UNCERTAINTY"]["physical_lobo_mae"]) # 0.15069636
a1_worst = float(p6_data["exp607_ablation_results"]["A1_CHEMISTRY_NAIVE"]["physical_worst_error"]) # 0.382556
a6_worst = float(p6_data["exp607_ablation_results"]["A6_DOMAIN_ADAPTIVE_UNCERTAINTY"]["physical_worst_error"]) # 0.531618
relative_mae_increase = float((a6_mae - a1_mae) / a1_mae) * 100.0 # ~9.98%

freeze_payload = {
    "metadata": {
        "system": "NEXUS — Intelligent Second-Life Qualification for EV Batteries",
        "project": "RMK-REVOLT / SECONDShift Platform",
        "phase6_status": "EXPLORATORY_ONLY",
        "phase6_1_status": "SCIENTIFICALLY_AUDITED_CLAIM_CORRECTED",
        "phase6_1_1_status": "FINAL_EVIDENCE_FREEZE",
        "governing_invariant": "COMPUTABLE != IMPLEMENTATION_VALID != PHYSICALLY VALIDATED != PROGNOSTICALLY SUPPORTED != CROSS_CHEMISTRY VALIDATED != UNCERTAINTY CALIBRATED != UNIVERSALLY VALID != CAUSALLY INTERPRETED != SAFETY PROVEN"
    },
    "cohort_counts": {
        "physical_n": 12,
        "physical_lfp_n": 8,
        "physical_nmc_n": 3,
        "physical_unknown_n": 1,
        "synthetic_n": 100,
        "synthetic_lfp_n": 50,
        "synthetic_nmc_n": 50,
        "mixed_total_n": 112
    },
    "critical_audit_1_nmc_correlation_reconciliation": {
        "canonical_serialized_value": nmc_r_canonical, # -0.9984
        "superseded_draft_value": -0.9120,
        "specimen_ids": ["SPECIMEN_09_TAGLESS_NMC_FRESH", "SPECIMEN_10_TAGLESS_NMC_AGED", "SPECIMEN_11_WRONG_LABEL_NMC"],
        "status": "EXPLORATORY_UNDERPOWERED_N3",
        "reconciliation_reason": (
            "Under N=3 sample size, Pearson correlation is descriptive and highly sensitive to small sensor/simulation noise variations. "
            "The canonical serialized value in results/phase6_domain_evidence.json is r = -0.9984 (p=0.0357). "
            "The earlier draft value r = -0.9120 from preliminary exploratory reports is formally classified as SUPERSEDED_BY_PHASE6_1_CORRECTION."
        )
    },
    "critical_audit_2_lfp_effect_attribution": {
        "feature": "DELTA_V_TOTAL",
        "attributed_cohort": "Physical Mixed-Cohort LOFO Ablation (N=12: 8 LFP, 3 NMC, 1 UNKNOWN)",
        "delta_mae": 0.01355,
        "cohens_d": 0.67,
        "p_value": 0.0382,
        "folds_improved": "9 of 12 folds",
        "status": "PROVISIONALLY_SUPPORTED",
        "scoping_rule": "Cohen's d=0.67 and p=0.0382 belong strictly to the Physical Mixed-Cohort LOFO analysis (N=12: 8 LFP, 3 NMC, 1 UNKNOWN). They must NOT be attributed specifically to the NMC cohort, described as NMC-specific evidence, or claimed as cross-chemistry inferential significance."
    },
    "critical_audit_3_nmc_sample_size": {
        "physical_n": 3,
        "r": nmc_r_canonical,
        "status": "EXPLORATORY / DESCRIPTIVE ONLY",
        "reproducibility": "DETERMINISTIC FROM PERSISTED CANONICAL DATA",
        "stochastic_regeneration_note": "CANONICAL SERIALIZED RESULT UNDER SPECIFIED SEED (cross-process hash salt variation affects fresh generation)",
        "persisted_canonical_specimens": {
            "SPECIMEN_09_TAGLESS_NMC_FRESH": {"delta_v_total": 0.03757019, "true_soh": 0.88},
            "SPECIMEN_10_TAGLESS_NMC_AGED": {"delta_v_total": 0.04458873, "true_soh": 0.68},
            "SPECIMEN_11_WRONG_LABEL_NMC": {"delta_v_total": 0.04003023, "true_soh": 0.82}
        },
        "cross_chemistry_generalization": "UNPROVEN",
        "statistical_power": "UNDERPOWERED",
        "scientific_interpretation": "An exploratory monotonic association was observed in the available NMC observations (N=3, r=-0.9984). This sample is descriptive only and insufficient to establish cross-chemistry generalization."
    },
    "critical_audit_4_uncertainty_interval_audit": {
        "correlation_error_sigma": pearson_r_err_sigma, # -0.00356
        "p_value": pearson_p_err_sigma, # 0.9912
        "uncertainty_responsiveness": "DEMONSTRATED",
        "uncertainty_calibration": "UNVALIDATED",
        "raw_95_full_width_nmc_soh_units": nmc_full_width_95, # 1.98787
        "raw_95_half_width_nmc_soh_units": nmc_half_width_95, # 0.9939
        "raw_95_full_width_unknown_soh_units": unk_full_width_95, # 2.27826
        "raw_95_half_width_unknown_soh_units": unk_half_width_95, # 1.1391
        "formulation": "Full width = 2 * 1.96 * sigma = 3.92 * sigma; Half width = 1.96 * sigma",
        "clipping_status": "Raw unclipped Gaussian predictive intervals from linear ridge epistemic model",
        "scientific_interpretation": (
            "Raw nominal 95% predictive intervals under shifted scenarios were substantially wider than the physical SOH domain [0, 1], "
            "indicating strong uncertainty responsiveness but uncalibrated uncertainty."
        )
    },
    "critical_audit_5_chemistry_threshold": {
        "threshold_value": 0.90,
        "status": "PROVISIONAL_ENGINEERING_THRESHOLD",
        "optimization_status": "THRESHOLD_OPTIMIZATION_UNDERPOWERED",
        "scientific_interpretation": (
            "The current physical cohort is insufficient to identify a meaningful optimal chemistry-confidence threshold "
            "because observed confidence values are concentrated near the extremes."
        )
    },
    "critical_audit_6_r0_status": {
        "status": "CONTEXTUAL_PROVISIONAL",
        "collinearity_fixed_current": 1.0,
        "independent_incremental_lofo_value": 0.0,
        "contextual_variance_reduction": 0.76,
        "scientific_interpretation": "R0_OHMIC is a protocol- and operating-condition-dependent electrical observation whose interpretation requires contextual normalization."
    },
    "critical_audit_7_delta_v_total_status": {
        "status": "SUPPORTED_WITH_CHEMISTRY_CONDITIONING",
        "evidence_level": "LEVEL_2_SMALL_PHYSICAL_COHORT",
        "cross_chemistry_generalization": "UNPROVEN"
    },
    "critical_audit_8_delta_v_ohmic_status": {
        "status": "PROVISIONALLY_SUPPORTED / MODEST EFFECT",
        "evidence_level": "LEVEL_2_SMALL_PHYSICAL_COHORT",
        "contact_resistance_claim": "RETRACTED",
        "scientific_interpretation": "Sensitive to aggregate early-time electrical response under the tested pulse conditions."
    },
    "critical_audit_9_a1_vs_a6_tradeoff": {
        "directly_comparable": True,
        "evaluation_protocol": "Leave-One-Battery-Out (LOBO) across 12 physical folds",
        "a1_mae": a1_mae, # 0.1370
        "a6_mae": a6_mae, # 0.1507
        "a1_worst_error": a1_worst, # 0.3826
        "a6_worst_error": a6_worst, # 0.5316
        "a1_ood_acceptance": 0.0833,
        "a6_ood_acceptance": 0.0,
        "a1_defer_rate": 0.0,
        "a6_defer_rate": 0.0833,
        "relative_mae_increase_pct": relative_mae_increase, # 9.98%
        "characterization": {
            "A1": "Prediction-optimized / domain-risk vulnerable",
            "A6": "Risk-constrained / domain-aware / conservative"
        },
        "scientific_conclusion": (
            "Model A6 sacrificed approximately 9.98% relative average MAE in the tested comparison while reducing tested OOD acceptance "
            "from 8.33% to 0%. This is a tested tradeoff, not a universal safety guarantee."
        )
    },
    "critical_audit_10_confounding_limitation": {
        "lfp_form_factor": "CYLINDRICAL_4S",
        "nmc_form_factor": "POUCH",
        "confounding_status": "CHEMISTRY_AND_FORM_FACTOR_CONFOUNDED",
        "scientific_interpretation": "Chemistry and physical/electrical configuration are confounded in the available physical cohort, preventing clean attribution of observed domain differences to chemistry alone."
    },
    "final_verdicts": {
        "phase6": "EXPLORATORY_ONLY",
        "phase6_1": "SCIENTIFICALLY_AUDITED_CLAIM_CORRECTED",
        "phase6_1_1": "FINAL_EVIDENCE_FREEZE",
        "cross_chemistry_generalization": "UNPROVEN",
        "uncertainty_calibration": "UNVALIDATED",
        "rul_cross_domain": "NOT_PERFORMED",
        "prospective_validation": "NOT_PERFORMED",
        "production_readiness": "NOT_ESTABLISHED",
        "safety_certification": "NOT_ESTABLISHED",
        "phase7_status": "NOT_STARTED"
    }
}

with open(FREEZE_OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(freeze_payload, f, indent=2)

print(f"Successfully generated {FREEZE_OUTPUT_PATH}")
