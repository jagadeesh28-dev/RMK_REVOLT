"""
Automated Results Pipeline (Phase 20)
Project: RMK-REVOLT / SECONDShift Platform

Executes the entire end-to-end qualification and validation sequence:
1. Baseline Characterization & Ground Truth Quarantine
2. Physical Benchmark Suite (E01 - E14)
3. 11-Attack Adversarial Stress Suite
4. Epistemic Chemistry Disambiguation Attack Suite (5 Cohorts, 250 Cycles)
5. Hardware vs Simulation Consistency Audit
6. Publication Visualization Generation
7. Statistical Metric & FAR Confidence Bound Aggregation

Emits consolidated data artifacts with ZERO manually edited figures or numbers.
"""

import os
import sys
import json
import time

from secondshift.experiments.run_physical_benchmark_suite import run_all_experiments
from secondshift.experiments.run_adversarial_overconfidence import run_all_adversarial_attacks
from secondshift.experiments.run_chemistry_attacks import run_chemistry_attacks
from secondshift.simulation.hardware_consistency_audit import run_consistency_audit
from secondshift.experiments.generate_visualizations import generate_all_figures

PROCESSED_DIR = "secondshift/data/processed"

def execute_complete_pipeline():
    start_time = time.time()
    print("\n" + "="*80)
    print("STARTING SECONDSHIFT FULL AUTOMATED RESULTS PIPELINE (PHASE 20)")
    print("="*80)

    # 1. Physical Benchmark Matrix (E01 - E14)
    print("\n[STEP 1/5] Executing 14-Experiment Physical Benchmark Matrix...")
    bench_results = run_all_experiments()

    # 2. 11-Attack Adversarial Overconfidence Suite
    print("\n[STEP 2/5] Executing 11-Attack Adversarial Stress Suite...")
    attack_results = run_all_adversarial_attacks()

    # 3. Chemistry Disambiguation Attacks (5 Cohorts, 250 Trials)
    print("\n[STEP 3/5] Executing Chemistry Ambiguity Stress Suite...")
    chem_results = run_chemistry_attacks()

    # 4. Simulation Consistency Audit
    print("\n[STEP 4/5] Executing Hardware-in-the-Loop Consistency Audit...")
    audit_results = run_consistency_audit()

    # 5. Visualization Generation
    print("\n[STEP 5/5] Rendering Full Set of Publication Visualizations...")
    generate_all_figures()

    elapsed = time.time() - start_time

    # Generate Automated Summary Report
    summary = {
        "pipeline_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_execution_time_s": elapsed,
        "physical_benchmarks": {
            "total_count": len(bench_results),
            "passed_count": sum(1 for v in bench_results.values() if v.get("passed", False)),
            "pass_rate_pct": (sum(1 for v in bench_results.values() if v.get("passed", False)) / len(bench_results)) * 100.0
        },
        "adversarial_attacks": {
            "total_count": len(attack_results),
            "passed_count": sum(1 for v in attack_results if v.get("passed", False)),
            "pass_rate_pct": (sum(1 for v in attack_results if v.get("passed", False)) / len(attack_results)) * 100.0
        },
        "chemistry_cohorts": {
            k: {
                "far_percent": v["far_percent"],
                "abstention_rate_percent": v["abstention_rate_percent"],
                "chemistry_accuracy_percent": v["chemistry_accuracy_percent"]
            } for k, v in chem_results.items()
        }
    }

    summary_file = os.path.join(PROCESSED_DIR, "pipeline_summary_report.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "="*80)
    print("SECONDSHIFT RESULTS PIPELINE COMPLETE")
    print(f"Total Dwell Time: {elapsed:.2f}s | Summary: {summary_file}")
    print(f"Benchmarks Passed: {summary['physical_benchmarks']['passed_count']}/{summary['physical_benchmarks']['total_count']}")
    print(f"Adversarial Attacks Passed: {summary['adversarial_attacks']['passed_count']}/{summary['adversarial_attacks']['total_count']}")
    print("="*80 + "\n")

    return summary

if __name__ == "__main__":
    execute_complete_pipeline()
