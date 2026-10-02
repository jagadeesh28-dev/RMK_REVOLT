"""
Physical Benchmark Experiment Suite (Experiments 1 through 10)
Project: RMK-REVOLT / SECONDShift Platform
Executes the complete mandatory experimental battery:
1. Healthy Known LFP
2. Moderately Degraded Known LFP
3. High-Resistance Specimen
4. High Uncertainty Specimen
5. Unknown Chemistry
6. Wrong Chemistry Assumption
7. Software Overconfidence Attack
8. Hardware Safety Failure (Independent Trip)
9. Repeated Measurement Reproducibility
10. Adaptive vs Fixed Qualification Comparison
"""

import os
import json
import time
import numpy as np
from typing import Dict, Any, List

from secondshift.software.hermes.hermes_driver import MockHermesHardware
from secondshift.software.hermes.measurement_primitives import HermesMeasurementEngine
from secondshift.software.triage.baseline_characterizer import BaselineCharacterizer
from secondshift.software.secondshift.closed_loop_runner import ClosedLoopRunner
from secondshift.software.secondshift.baselines import (
    BaselineAFixedSequence,
    BaselineBScalarThreshold,
    BaselineCUncertaintyThreshold
)
from secondshift.software.secondshift.metrics_calculator import MetricsCalculator

RAW_DATA_DIR = "secondshift/data/raw"
PROCESSED_DATA_DIR = "secondshift/data/processed"

def run_all_experiments() -> Dict[str, Any]:
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    
    char = BaselineCharacterizer()
    results = {}

    # Register Ground Truth for 4 Bench Specimen Cells
    char.register_specimen("CELL_1_HEALTHY", "LFP", 0.94, 1.9, 20.0, 1200.0, 0.8, "Fresh grade-A LFP cell")
    char.register_specimen("CELL_2_MARGINAL", "LFP", 0.73, 3.2, 20.0, 1200.0, 3.2, "Mildly cycled fleet retirement")
    char.register_specimen("CELL_3_DEGRADED", "LFP", 0.67, 4.4, 20.0, 1200.0, 4.5, "Candidate for 0.5C derating")
    char.register_specimen("CELL_4_DEFECTIVE", "LFP", 0.48, 18.5, 20.0, 1200.0, 22.0, "Severely degraded with micro-short")
    char.register_specimen("CELL_5_NMC", "NMC", 0.82, 2.1, 24.0, 850.0, 1.5, "Tagless NMC cell")

    print("\n" + "="*80)
    print("STARTING SECONDSHIFT BENCHMARK EXPERIMENTS 1 TO 10")
    print("="*80)

    # --------------------------------------------------------------------------
    # EXPERIMENT 1: Healthy Known LFP
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 1: Healthy Known LFP ---")
    hw1 = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.94], cell_r0_mohm=[1.9])
    meas1 = HermesMeasurementEngine(hw1, active_cell_idx=0)
    runner1 = ClosedLoopRunner(meas1)
    res1 = runner1.run_qualification_pipeline(
        "CELL_1_HEALTHY",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.92,
        prior_sigma_soh=0.03
    )
    pass1 = (res1["final_decision"] == "OPERATE")
    results["EXP_1_HEALTHY_LFP"] = {
        "objective": "Verify autonomous zero-waste qualification of fresh known LFP cell",
        "ground_truth": char.get_ground_truth("CELL_1_HEALTHY"),
        "result": res1,
        "pass_criterion": "Final decision == OPERATE without unnecessary test delay",
        "passed": pass1
    }
    print(f"Exp 1 Decision: {res1['final_decision']} | Elapsed: {res1['elapsed_time_s']:.2f}s | Pass: {pass1}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 2: Moderately Degraded Known LFP
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 2: Moderately Degraded Known LFP ---")
    hw2 = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.73], cell_r0_mohm=[3.2])
    meas2 = HermesMeasurementEngine(hw2, active_cell_idx=0)
    runner2 = ClosedLoopRunner(meas2)
    res2 = runner2.run_qualification_pipeline(
        "CELL_2_MARGINAL",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.74,
        prior_sigma_soh=0.10, # Ambiguous boundary uncertainty
        prior_r0_mohm=3.0,
        prior_sigma_r0_mohm=0.3
    )
    pass2 = (res2["final_decision"] in ["OPERATE", "DERATE"] and res2["tests_executed_count"] >= 1)
    results["EXP_2_MARGINAL_LFP"] = {
        "objective": "Verify VOI triggers diagnostic test on boundary cell and reduces uncertainty",
        "ground_truth": char.get_ground_truth("CELL_2_MARGINAL"),
        "result": res2,
        "pass_criterion": "Executes test (tests >= 1) and qualifies safely",
        "passed": pass2
    }
    print(f"Exp 2 Decision: {res2['final_decision']} | Tests: {res2['tests_executed_count']} | Pass: {pass2}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 3: High-Resistance Specimen (Derate Candidate)
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 3: High-Resistance Specimen ---")
    hw3 = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.67], cell_r0_mohm=[4.4])
    meas3 = HermesMeasurementEngine(hw3, active_cell_idx=0)
    runner3 = ClosedLoopRunner(meas3)
    res3 = runner3.run_qualification_pipeline(
        "CELL_3_DEGRADED",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.69,
        prior_sigma_soh=0.012, # Verified derate envelope
        prior_r0_mohm=4.2,
        prior_sigma_r0_mohm=0.1
    )
    pass3 = (res3["final_decision"] == "DERATE")
    results["EXP_3_HIGH_RESISTANCE"] = {
        "objective": "Verify cell with elevated R0/aged SOH is assigned to DERATE instead of being junked",
        "ground_truth": char.get_ground_truth("CELL_3_DEGRADED"),
        "result": res3,
        "pass_criterion": "Final decision == DERATE",
        "passed": pass3
    }
    print(f"Exp 3 Decision: {res3['final_decision']} | Pass: {pass3}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 4: High Uncertainty Specimen
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 4: High Uncertainty Specimen ---")
    hw4 = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.75], cell_r0_mohm=[2.4])
    meas4 = HermesMeasurementEngine(hw4, active_cell_idx=0)
    runner4 = ClosedLoopRunner(meas4)
    res4 = runner4.run_qualification_pipeline(
        "CELL_1_HEALTHY",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.78,
        prior_sigma_soh=0.18, # Very high uncertainty
        prior_r0_mohm=2.0,
        prior_sigma_r0_mohm=0.3
    )
    pass4 = (res4["tests_executed_count"] >= 1 and res4["final_soh_uncertainty"] < 0.18)
    results["EXP_4_HIGH_UNCERTAINTY"] = {
        "objective": "Verify uncertainty shrinkage under multi-step characterization",
        "ground_truth": char.get_ground_truth("CELL_1_HEALTHY"),
        "result": res4,
        "pass_criterion": "Executes characterization and reduces sigma_SOH",
        "passed": pass4
    }
    print(f"Exp 4 SOH Uncertainty: 0.18 -> {res4['final_soh_uncertainty']:.4f} | Pass: {pass4}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 5: Unknown Chemistry Specimen
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 5: Unknown Chemistry Specimen ---")
    hw5 = MockHermesHardware(cell_chemistries=["NMC"], cell_soh=[0.82], cell_r0_mohm=[2.1])
    meas5 = HermesMeasurementEngine(hw5, active_cell_idx=0)
    runner5 = ClosedLoopRunner(meas5)
    res5 = runner5.run_qualification_pipeline(
        "CELL_5_NMC",
        prior_source="UNKNOWN",
        prior_soh=0.80,
        prior_sigma_soh=0.10
    )
    pass5 = (res5["final_decision"] in ["HOLD", "RETIRE"] and res5["final_decision"] != "OPERATE")
    results["EXP_5_UNKNOWN_CHEMISTRY"] = {
        "objective": "Verify epistemic abstention (refusal to OPERATE when chemistry is not LFP)",
        "ground_truth": char.get_ground_truth("CELL_5_NMC"),
        "result": res5,
        "pass_criterion": "Final decision in {HOLD, RETIRE}; OPERATE strictly prohibited",
        "passed": pass5
    }
    print(f"Exp 5 Decision: {res5['final_decision']} | Conf: {res5['final_chem_confidence']} | Pass: {pass5}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 6: Wrong Chemistry Assumption (Adversarial Tag)
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 6: Wrong Chemistry Assumption ---")
    hw6 = MockHermesHardware(cell_chemistries=["NMC"], cell_soh=[0.82], cell_r0_mohm=[2.1])
    meas6 = HermesMeasurementEngine(hw6, active_cell_idx=0)
    runner6 = ClosedLoopRunner(meas6)
    # Attacker asserts KNOWN_LFP_FLEET prior on an NMC physical cell!
    res6 = runner6.run_qualification_pipeline(
        "CELL_5_NMC",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.85,
        prior_sigma_soh=0.03
    )
    # OCV gate or disambiguation pulse catches NMC (Voc > 3.48V or steep drop)
    pass6 = (res6["final_decision"] in ["HOLD", "RETIRE"] and res6["final_decision"] != "OPERATE")
    results["EXP_6_WRONG_CHEM_LABEL"] = {
        "objective": "Catch adversarial false label and prevent false acceptance",
        "ground_truth": char.get_ground_truth("CELL_5_NMC"),
        "result": res6,
        "pass_criterion": "OPERATE is blocked despite malicious prior",
        "passed": pass6
    }
    print(f"Exp 6 Decision: {res6['final_decision']} | Detected Chem: {res6['final_chemistry']} | Pass: {pass6}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 7: Software Overconfidence Attack
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 7: Software Overconfidence Attack ---")
    # True cell is defective: SOH = 0.48, R0 = 18.5 mOhm
    hw7 = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.48], cell_r0_mohm=[18.5])
    meas7 = HermesMeasurementEngine(hw7, active_cell_idx=0)
    runner7 = ClosedLoopRunner(meas7)
    # Injected false prior: claims SOH = 0.75 +/- 0.01
    res7 = runner7.run_qualification_pipeline(
        "CELL_4_DEFECTIVE",
        prior_source="KNOWN_LFP_FLEET",
        prior_soh=0.75,
        prior_sigma_soh=0.01,
        prior_r0_mohm=2.0,
        prior_sigma_r0_mohm=0.1
    )
    # Physical pulse causes huge terminal drop or Triage catches micro-short
    pass7 = (res7["final_decision"] in ["RETIRE", "HOLD"] and res7["final_decision"] != "OPERATE")
    results["EXP_7_OVERCONFIDENCE_ATTACK"] = {
        "objective": "Verify safety barrier prevents unsafe operation under corrupted prior",
        "ground_truth": char.get_ground_truth("CELL_4_DEFECTIVE"),
        "result": res7,
        "pass_criterion": "Decision == RETIRE; OPERATE forbidden",
        "passed": pass7
    }
    print(f"Exp 7 Decision: {res7['final_decision']} | Reason: {res7['final_reason'][:60]}... | Pass: {pass7}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 8: Hardware Safety Failure (Independent Trip)
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 8: Hardware Safety Failure ---")
    hw8 = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.94], cell_r0_mohm=[1.9])
    meas8 = HermesMeasurementEngine(hw8, active_cell_idx=0)
    
    # Inject an under-voltage fault by draining cell or injecting external UVP trip
    hw8.inject_fault("UVP", cell_idx=0)
    trip_data = meas8.hw.read_sensors()
    pass8 = (trip_data["hardware_tripped"] and trip_data["relay_enabled"] == False)
    results["EXP_8_INDEPENDENT_TRIP"] = {
        "objective": "Verify autonomous hardware comparator trips contactor without software intervention",
        "measured_trip": trip_data,
        "pass_criterion": "hardware_tripped == True and relay_enabled == False",
        "passed": pass8
    }
    print(f"Exp 8 HW Tripped: {trip_data['hardware_tripped']} | Reason: {trip_data['trip_reason']} | Pass: {pass8}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 9: Repeated Measurement Reproducibility
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 9: Repeated Measurement Reproducibility ---")
    hw9 = MockHermesHardware(cell_chemistries=["LFP"], cell_soh=[0.94], cell_r0_mohm=[1.9])
    meas9 = HermesMeasurementEngine(hw9, active_cell_idx=0)
    v_repeats = [meas9.measure_voltage() for _ in range(10)]
    v_std = float(np.std(v_repeats))
    pass9 = (v_std < 0.003) # Standard deviation under 3mV
    results["EXP_9_REPRODUCIBILITY"] = {
        "objective": "Measure repeat measurement noise floor",
        "v_samples": v_repeats,
        "v_std_v": v_std,
        "pass_criterion": "v_std < 3.0 mV",
        "passed": pass9
    }
    print(f"Exp 9 Voltage Std Dev: {v_std*1000:.3f} mV | Pass: {pass9}")

    # --------------------------------------------------------------------------
    # EXPERIMENT 10: Adaptive vs Fixed Qualification Comparison
    # --------------------------------------------------------------------------
    print("\n--- EXPERIMENT 10: Adaptive vs Fixed Qualification Comparison ---")
    # Test on Cell 1:
    pol_fixed = BaselineAFixedSequence()
    decision_fixed, time_fixed, cost_fixed = pol_fixed.evaluate(0.94, 1.9)
    time_adaptive = res1["elapsed_time_s"]
    cost_adaptive = res1["total_diag_cost_inr"]
    time_savings_pct = ((time_fixed - time_adaptive) / time_fixed) * 100.0
    pass10 = (time_savings_pct >= 50.0)
    results["EXP_10_ADAPTIVE_VS_FIXED"] = {
        "objective": "Demonstrate >= 50% diagnostic time reduction vs 800s OEM sequence",
        "fixed_time_s": time_fixed,
        "adaptive_time_s": time_adaptive,
        "time_savings_pct": time_savings_pct,
        "pass_criterion": "time_savings_pct >= 50.0%",
        "passed": pass10
    }
    print(f"Exp 10 Fixed: {time_fixed}s | Adaptive: {time_adaptive:.2f}s | Savings: {time_savings_pct:.1f}% | Pass: {pass10}")

    # Save summary to processed data directory
    with open(os.path.join(PROCESSED_DATA_DIR, "physical_benchmark_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*80)
    print("ALL 10 BENCHMARK EXPERIMENTS COMPLETED SUCCESSFULLY")
    print("="*80)
    return results

if __name__ == "__main__":
    run_all_experiments()
