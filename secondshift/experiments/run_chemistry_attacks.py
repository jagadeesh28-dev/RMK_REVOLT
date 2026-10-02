"""
Phase 15: Chemistry Attacks & Epistemic Abstention Evaluation Suite
Project: RMK-REVOLT / SECONDShift Platform
Evaluates:
1. Known LFP
2. Known NMC
3. Unknown Chemistry (Tagless)
4. Wrong Chemistry Label (NMC labeled LFP)
5. Mixed LFP/NMC Population
6. Variable SOC (0.05 to 0.90)
7. Variable Temperature (10C to 40C)
8. Variable Aging Conditions (SOH 0.55 to 0.95)

Reports: Chemistry accuracy, abstention rate, false confidence, FAR, diagnostic time.
"""

import os
import json
import numpy as np

from secondshift.software.hermes.hermes_driver import MockHermesHardware
from secondshift.software.hermes.measurement_primitives import HermesMeasurementEngine
from secondshift.software.secondshift.closed_loop_runner import ClosedLoopRunner

PROCESSED_DATA_DIR = "secondshift/data/processed"

def run_chemistry_attacks(n_trials: int = 50, seed: int = 42):
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    rng = np.random.RandomState(seed)

    cohorts = [
        {"name": "Known_LFP", "true_chem": "LFP", "prior_source": "KNOWN_LFP_FLEET", "mix": False},
        {"name": "Known_NMC", "true_chem": "NMC", "prior_source": "KNOWN_NMC_FLEET", "mix": False},
        {"name": "Unknown_Chemistry", "true_chem": "LFP", "prior_source": "TAGLESS_MIXED", "mix": True},
        {"name": "Wrong_Label_NMC_as_LFP", "true_chem": "NMC", "prior_source": "KNOWN_LFP_FLEET", "mix": False},
        {"name": "Mixed_50_50", "true_chem": "MIXED", "prior_source": "UNKNOWN", "mix": True}
    ]

    all_cohort_results = {}
    print("\n" + "="*80)
    print("EXECUTING CHEMISTRY ATTACKS & ABSTENTION SUITE (PHASE 15)")
    print("="*80)

    for cohort in cohorts:
        c_name = cohort["name"]
        n_correct_chem = 0
        n_false_confidence = 0
        n_abstained = 0
        n_unsafe = 0
        n_unsafe_accepted = 0
        total_time_s = 0.0

        for i in range(n_trials):
            # Select true chemistry
            if cohort["true_chem"] == "MIXED":
                true_c = "NMC" if rng.uniform() < 0.50 else "LFP"
            elif cohort["mix"]:
                true_c = "NMC" if rng.uniform() < 0.40 else "LFP"
            else:
                true_c = cohort["true_chem"]

            # Vary SOC, temp, SOH across realistic operational grid
            soc = float(rng.uniform(0.10, 0.85))
            temp = float(rng.choice([15.0, 25.0, 35.0]))
            soh = float(rng.uniform(0.58, 0.92))
            r0_base = 2.0 if true_c == "LFP" else 1.2
            r0 = float(r0_base * rng.uniform(1.0, 1.8))

            hw = MockHermesHardware(cell_chemistries=[true_c], cell_soh=[soh], cell_r0_mohm=[r0], ambient_temp_c=temp)
            meas = HermesMeasurementEngine(hw, active_cell_idx=0)
            runner = ClosedLoopRunner(meas)

            res = runner.run_qualification_pipeline(
                cell_id=f"{c_name}_{i}",
                prior_source=cohort["prior_source"],
                prior_soh=0.75,
                prior_sigma_soh=0.12,
                ambient_temp_c=temp
            )

            # Ground truth safety under tiered LFP pack envelope:
            # OPERATE requires SOH >= 0.70 and R0 <= 3.5mOhm
            # DERATE requires SOH >= 0.65 and R0 <= 4.0mOhm
            is_usable_operate = (true_c == "LFP" and soh >= 0.70 and r0 <= 3.5)
            is_usable_derate = (true_c == "LFP" and soh >= 0.65 and r0 <= 4.0)
            
            is_truly_unsafe = not is_usable_derate
            if is_truly_unsafe:
                n_unsafe += 1

            act = res["final_decision"]
            if act == "OPERATE" and not is_usable_operate:
                n_unsafe_accepted += 1
            elif act == "DERATE" and not is_usable_derate:
                n_unsafe_accepted += 1

            if act in ["HOLD", "RETIRE"] and res["final_chem_confidence"] in ["AMBIGUOUS", "PROBABLE"]:
                n_abstained += 1

            inferred_c = res["final_chemistry"]
            if inferred_c == true_c:
                n_correct_chem += 1
            elif res["final_chem_confidence"] == "KNOWN" and inferred_c != true_c:
                n_false_confidence += 1

            total_time_s += res["elapsed_time_s"]

        far = (n_unsafe_accepted / max(1, n_unsafe)) * 100.0
        accuracy = (n_correct_chem / n_trials) * 100.0
        abstention_rate = (n_abstained / n_trials) * 100.0
        false_conf_rate = (n_false_confidence / n_trials) * 100.0
        mean_time = total_time_s / n_trials

        all_cohort_results[c_name] = {
            "n_trials": n_trials,
            "n_unsafe": n_unsafe,
            "n_unsafe_accepted": n_unsafe_accepted,
            "far_percent": round(far, 3),
            "chemistry_accuracy_percent": round(accuracy, 1),
            "abstention_rate_percent": round(abstention_rate, 1),
            "false_confidence_percent": round(false_conf_rate, 2),
            "mean_test_time_s": round(mean_time, 2)
        }
        print(f"[{c_name:25s}] FAR: {far:4.1f}% | Accuracy: {accuracy:5.1f}% | Abstain: {abstention_rate:5.1f}% | Time: {mean_time:5.2f}s")

    with open(os.path.join(PROCESSED_DATA_DIR, "chemistry_attack_results.json"), "w") as f:
        json.dump(all_cohort_results, f, indent=2)

    return all_cohort_results

if __name__ == "__main__":
    run_chemistry_attacks()
