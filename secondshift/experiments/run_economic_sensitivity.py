"""
Phase 17 & 18: Economic Model and Sensitivity Analysis
Project: RMK-REVOLT / SECONDShift Platform

Audits the net economic value per specimen claim (e.g. ₹2350/specimen):
Evaluates 3 economic regimes:
1. PESSIMISTIC: Low energy tariffs (₹6/kWh), high failure penalty (₹15,000), low salvage (₹800/kWh), 800 second-life cycles.
2. NOMINAL: Baseline tariffs (₹10/kWh), standard penalty (₹6,000), standard salvage (₹1200/kWh), 1200 second-life cycles.
3. OPTIMISTIC: High energy tariffs (₹14/kWh), moderate penalty (₹3,000), high salvage (₹1600/kWh), 1500 second-life cycles.

Evaluates systems:
- BASELINE A: Fixed OEM Sequence (42.86% FAR, 800s dwell, ₹150 test cost)
- BASELINE B: Scalar SOH Threshold (114.29% FAR, 0s dwell, ₹0 test cost)
- BASELINE C: Uncertainty Threshold (114.29% FAR, 0s dwell, ₹0 test cost)
- SECONDSHIFT: Adaptive VOI + Hard Barrier (0.00% FAR, 12.5s dwell, ₹12.5 test cost)

Saves results to secondshift/data/processed/economic_sensitivity_results.json
"""

import os
import json
import numpy as np

OUTPUT_PATH = "secondshift/data/processed/economic_sensitivity_results.json"

SCENARIOS = {
    "PESSIMISTIC": {
        "energy_tariff_inr_kwh": 6.0,
        "hazard_penalty_inr": 15000.0,
        "salvage_tariff_inr_kwh": 800.0,
        "second_life_cycles": 800,
        "cell_nominal_kwh": 0.064, # 20Ah * 3.2V
        "description": "Depressed power tariffs, aggressive liability penalties, weak raw material markets"
    },
    "NOMINAL": {
        "energy_tariff_inr_kwh": 10.0,
        "hazard_penalty_inr": 6000.0,
        "salvage_tariff_inr_kwh": 1200.0,
        "second_life_cycles": 1200,
        "cell_nominal_kwh": 0.064,
        "description": "Current Indian commercial C&I energy storage arbitrage, standard recycling scrap prices"
    },
    "OPTIMISTIC": {
        "energy_tariff_inr_kwh": 14.0,
        "hazard_penalty_inr": 3000.0,
        "salvage_tariff_inr_kwh": 1600.0,
        "second_life_cycles": 1500,
        "cell_nominal_kwh": 0.064,
        "description": "High peak-demand tariff shaving, premium repurposing market, strong lithium commodity prices"
    }
}

# Empirical performance parameters from Blind Physical Validation (Phase 7)
PERFORMANCE_PARAMS = {
    "BASELINE_A": {
        "name": "Baseline A (Fixed OEM Sequence)",
        "qar": 0.60,      # 60% safe qualification rate
        "far": 0.4286,    # 42.86% false acceptances among unsafe
        "p_unsafe": 7/12, # 58.3% unsafe prevalence in intake stream
        "p_safe": 5/12,   # 41.7% safe prevalence
        "mean_test_time_s": 800.0,
        "fixed_test_cost_inr": 150.0,
        "energy_consumption_kwh": 0.0224
    },
    "BASELINE_B": {
        "name": "Baseline B (Scalar SOH Threshold)",
        "qar": 1.00,
        "far": 1.00,      # Accepts virtually all intakes indiscriminately
        "p_unsafe": 7/12,
        "p_safe": 5/12,
        "mean_test_time_s": 0.0,
        "fixed_test_cost_inr": 0.0,
        "energy_consumption_kwh": 0.0
    },
    "BASELINE_C": {
        "name": "Baseline C (Uncertainty Threshold)",
        "qar": 1.00,
        "far": 1.00,
        "p_unsafe": 7/12,
        "p_safe": 5/12,
        "mean_test_time_s": 0.0,
        "fixed_test_cost_inr": 0.0,
        "energy_consumption_kwh": 0.0
    },
    "SECONDSHIFT": {
        "name": "SECONDShift (Adaptive VOI + Barrier)",
        "qar": 0.80,      # 80% safe qualified
        "far": 0.00,      # 0.00% false acceptance
        "p_unsafe": 7/12,
        "p_safe": 5/12,
        "mean_test_time_s": 12.5,
        "fixed_test_cost_inr": 12.5, # Amortized bench cost + energy
        "energy_consumption_kwh": 0.00025
    }
}


def compute_economic_returns():
    results = {}

    for scen_name, scen in SCENARIOS.items():
        results[scen_name] = {
            "scenario_metadata": scen,
            "systems": {}
        }
        
        # Base asset revenue per fully qualified cell
        # Revenue = mean_soh (0.85) * nominal_kwh * cycles * tariff
        mean_qualified_soh = 0.82
        gross_second_life_value = (
            mean_qualified_soh *
            scen["cell_nominal_kwh"] *
            scen["second_life_cycles"] *
            scen["energy_tariff_inr_kwh"]
        )

        salvage_value_per_cell = scen["cell_nominal_kwh"] * scen["salvage_tariff_inr_kwh"]

        for sys_id, perf in PERFORMANCE_PARAMS.items():
            # Probability breakdown:
            # 1. True Safe Qualified: P(Safe) * QAR
            p_safe_qual = perf["p_safe"] * perf["qar"]

            # 2. False Acceptance: P(Unsafe) * FAR
            p_false_accept = perf["p_unsafe"] * perf["far"]

            # 3. Truly Rejected / Retired:
            # P(Safe Rejected) + P(Unsafe Rejected)
            p_safe_reject = perf["p_safe"] * (1.0 - perf["qar"])
            p_unsafe_reject = perf["p_unsafe"] * (1.0 - perf["far"])
            p_retired = p_safe_reject + p_unsafe_reject

            # Expected Revenue
            # Safe qualified cells yield gross second life value
            # False acceptances generate partial revenue before premature catastrophic failure
            # (assume 20% operational life before failure event)
            rev_safe = p_safe_qual * gross_second_life_value
            rev_false = p_false_accept * (0.20 * gross_second_life_value)
            rev_salvage = p_retired * salvage_value_per_cell

            expected_gross_revenue = rev_safe + rev_false + rev_salvage

            # Expected Penalties & Costs
            expected_hazard_penalty = p_false_accept * scen["hazard_penalty_inr"]
            testing_cost = perf["fixed_test_cost_inr"] + (perf["energy_consumption_kwh"] * scen["energy_tariff_inr_kwh"])

            # Net Economic Value per Specimen
            net_value = expected_gross_revenue - expected_hazard_penalty - testing_cost

            # Throughput & Operational Capacity (8-hour shift = 28,800s)
            cycle_time = max(1.0, perf["mean_test_time_s"] + 15.0) # 15s mechanical handling
            daily_throughput_modules = 28800.0 / cycle_time
            daily_economic_value = daily_throughput_modules * net_value

            results[scen_name]["systems"][sys_id] = {
                "name": perf["name"],
                "gross_second_life_revenue_inr": round(gross_second_life_value, 2),
                "salvage_value_inr": round(salvage_value_per_cell, 2),
                "expected_gross_revenue_inr": round(expected_gross_revenue, 2),
                "expected_hazard_penalty_inr": round(expected_hazard_penalty, 2),
                "testing_cost_inr": round(testing_cost, 2),
                "net_value_per_specimen_inr": round(net_value, 2),
                "daily_throughput_cells": round(daily_throughput_modules, 0),
                "daily_net_economic_value_inr": round(daily_economic_value, 2)
            }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*95)
    print("ECONOMIC RETURN & SENSITIVITY AUDIT ACROSS REGIMES (PHASE 17 & 18)")
    print("="*95)
    for scen_name in ["PESSIMISTIC", "NOMINAL", "OPTIMISTIC"]:
        print(f"\n--- SCENARIO: {scen_name} ---")
        print(f"{'SYSTEM':40s} | {'NET VALUE/CELL':16s} | {'THROUGHPUT/DAY':16s} | {'DAILY VALUE':14s}")
        print("-" * 92)
        for sys_id, metrics in results[scen_name]["systems"].items():
            print(f"{metrics['name']:40s} | ₹{metrics['net_value_per_specimen_inr']:14.2f} | {metrics['daily_throughput_cells']:14.0f} | ₹{metrics['daily_net_economic_value_inr']:12.2f}")

    return results

if __name__ == "__main__":
    compute_economic_returns()
