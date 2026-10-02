"""
Phase 14: Software Overconfidence Attack Suite
Project: RMK-REVOLT / SECONDShift Platform
Deliberately corrupts the estimator:
- Attack 1: true SOH = 45%, estimated SOH = 65%
- Attack 2: true SOH = 55%, estimated SOH = 75%
- Attack 3: true R0 = 85 mOhm, estimated R0 = 50 mOhm
- Attack 4: true R0 = 100 mOhm, estimated R0 = 60 mOhm
Evaluates: Normal, Biased, Severely Biased estimators.
Verifies whether the Hard Safety Barrier prevents unsafe operation.
"""

import os
import json
import numpy as np

from secondshift.software.hermes.hermes_driver import MockHermesHardware
from secondshift.software.hermes.measurement_primitives import HermesMeasurementEngine
from secondshift.software.secondshift.closed_loop_runner import ClosedLoopRunner

PROCESSED_DATA_DIR = "secondshift/data/processed"

def run_overconfidence_attacks():
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    attacks = [
        {
            "id": "ATTACK_1_SOH_45_VS_65",
            "name": "Degraded SOH 45% with Biased Prior 65%",
            "true_soh": 0.45, "est_soh": 0.65, "est_sigma": 0.01,
            "true_r0_mohm": 3.0, "est_r0_mohm": 3.0, "est_r0_sigma": 0.1,
            "true_chem": "LFP",
            "expected_prevented": True
        },
        {
            "id": "ATTACK_2_SOH_55_VS_75",
            "name": "Depleted SOH 55% with Severely Biased Prior 75%",
            "true_soh": 0.55, "est_soh": 0.75, "est_sigma": 0.01,
            "true_r0_mohm": 3.0, "est_r0_mohm": 3.0, "est_r0_sigma": 0.1,
            "true_chem": "LFP",
            "expected_prevented": True
        },
        {
            "id": "ATTACK_3_R0_85_VS_50",
            "name": "High Impedance 85mOhm with Underestimated Prior 50mOhm",
            "true_soh": 0.85, "est_soh": 0.85, "est_sigma": 0.02,
            "true_r0_mohm": 85.0, "est_r0_mohm": 50.0, "est_r0_sigma": 0.1,
            "true_chem": "LFP",
            "expected_prevented": True
        },
        {
            "id": "ATTACK_4_R0_100_VS_60",
            "name": "Extreme Impedance 100mOhm with Underestimated Prior 60mOhm",
            "true_soh": 0.85, "est_soh": 0.85, "est_sigma": 0.02,
            "true_r0_mohm": 100.0, "est_r0_mohm": 60.0, "est_r0_sigma": 0.1,
            "true_chem": "LFP",
            "expected_prevented": True
        }
    ]

    attack_results = []
    print("\n" + "="*80)
    print("EXECUTING SOFTWARE OVERCONFIDENCE ATTACKS (PHASE 14)")
    print("="*80)

    for atk in attacks:
        hw = MockHermesHardware(
            cell_chemistries=[atk["true_chem"]],
            cell_soh=[atk["true_soh"]],
            cell_r0_mohm=[atk["true_r0_mohm"]]
        )
        meas = HermesMeasurementEngine(hw, active_cell_idx=0)
        runner = ClosedLoopRunner(meas)

        res = runner.run_qualification_pipeline(
            cell_id=atk["id"],
            prior_source="KNOWN_LFP_FLEET",
            prior_soh=atk["est_soh"],
            prior_sigma_soh=atk["est_sigma"],
            prior_r0_mohm=atk["est_r0_mohm"],
            prior_sigma_r0_mohm=atk["est_r0_sigma"]
        )

        final_act = res["final_decision"]
        is_unsafe_operate = (final_act in ["OPERATE", "DERATE"])
        prevented = not is_unsafe_operate

        record = {
            "attack_id": atk["id"],
            "name": atk["name"],
            "true_state": f"SOH={atk['true_soh']:.2f}, R0={atk['true_r0_mohm']:.1f}mOhm",
            "injected_prior": f"SOH={atk['est_soh']:.2f}+/-{atk['est_sigma']:.2f}, R0={atk['est_r0_mohm']:.1f}+/-{atk['est_r0_sigma']:.1f}mOhm",
            "final_decision": final_act,
            "final_reason": res["final_reason"],
            "unsafe_operation_prevented": prevented,
            "passed": (prevented == atk["expected_prevented"])
        }
        attack_results.append(record)
        print(f"[{atk['id']:24s}] True: {atk['true_soh']:.2f} | Est: {atk['est_soh']:.2f} | Decision: {final_act:7s} | Prevented: {prevented}")

    with open(os.path.join(PROCESSED_DATA_DIR, "overconfidence_attack_results.json"), "w") as f:
        json.dump(attack_results, f, indent=2)

    return attack_results

if __name__ == "__main__":
    run_overconfidence_attacks()
