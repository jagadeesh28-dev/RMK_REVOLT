"""
Helper script to update phase6_domain_evidence.json with Phase 6.1 audit corrections.
"""
import json
import os

PATHS = [
    "results/phase6_domain_evidence.json",
    "secondshift/data/processed/phase6_domain_evidence.json"
]

for p in PATHS:
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Update metadata
    data["metadata"]["phase6_verdict"] = "EXPLORATORY_ONLY"
    data["metadata"]["phase6_1_audit_verdict"] = "SCIENTIFICALLY_AUDITED_CLAIM_CORRECTED"
    data["metadata"]["uncertainty_calibration_status"] = "UNVALIDATED"
    data["metadata"]["chemistry_confidence_threshold_status"] = "PROVISIONAL_ENGINEERING_THRESHOLD"
    data["metadata"]["cross_chemistry_generalization"] = "UNPROVEN"
    data["metadata"]["rul_cross_domain_status"] = "NOT_PERFORMED"

    # 2. Update exp606 uncertainty audit language
    data["exp606_domain_shift_and_uncertainty"]["uncertainty_responsiveness"] = "DEMONSTRATED"
    data["exp606_domain_shift_and_uncertainty"]["uncertainty_calibration"] = "UNVALIDATED"
    data["exp606_domain_shift_and_uncertainty"]["audit_statement"] = (
        "The tested domain-shift scenarios produced increased epistemic uncertainty and DEFER behavior. "
        "Calibration of uncertainty against independent physical prediction error remains unvalidated."
    )

    # 3. Update exp608 safety metrics language
    data["exp608_worst_case_metrics"]["false_confident_acceptance_note"] = (
        "0% false confident acceptance on tested OOD scenarios (SPECIMEN_12 deferred by DomainValidityLayer); "
        "does not prove universal 0% false acceptance across unmodeled domains."
    )

    # 4. Update feature_status_table
    table = data["feature_status_table"]
    table["DELTA_V_TOTAL"]["final_status"] = "SUPPORTED_WITH_CHEMISTRY_CONDITIONING"
    table["DELTA_V_TOTAL"]["cross_chemistry_evidence"] = (
        "Exploratory transfer observed (r=-0.88 LFP, r=-0.91 exploratory NMC N=3); "
        "cross-chemistry generalization remains unproven"
    )

    table["DELTA_V_OHMIC"]["final_status"] = "PROVISIONALLY_SUPPORTED / MODEST EFFECT"
    table["DELTA_V_OHMIC"]["remaining_evidence_needed"] = (
        "Multi-rate pulse validation separating aggregate ohmic response from wiring and contacts"
    )

    table["R0_OHMIC"]["final_status"] = "CONTEXTUAL / PROVISIONAL"
    table["R0_OHMIC"]["cross_chemistry_evidence"] = (
        "Requires chemistry baseline normalization; variance reduction does not demonstrate incremental prognostic value"
    )
    table["R0_OHMIC"]["scientific_interpretation"] = (
        "R0_OHMIC is a protocol- and operating-condition-dependent electrical observation whose interpretation "
        "requires contextual normalization."
    )

    # 5. Link Phase 6.1 Audit Payload
    data["phase6_1_audit_reference"] = "results/phase6_1_audit.json"

    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {p}")
