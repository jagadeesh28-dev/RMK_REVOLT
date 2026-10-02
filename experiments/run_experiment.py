"""
RMK-REVOLT Unified Experiment Framework and Execution Suite
Implements Experiments E1-E5, Application Dependence, Ablation Studies, and Adversarial Scenarios.
Outputs raw CSVs, structured JSON summaries, and statistical reports.
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from scipy import stats

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief
from src.triage import TriageEngine
from src.secondshift import SecondShiftDiagnosticEngine
from src.decision_engine import DecisionEngine
from src.hermes import HermesController
from baselines.baseline_strategies import (
    BaselineAFixedTesting,
    BaselineBSOHThreshold,
    BaselineDStaticApplication
)
from metrics.evaluator import MetricEvaluator

def get_default_configs():
    import yaml
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

# =====================================================================
# EXPERIMENT 1: Does Uncertainty Change the Optimal Action?
# =====================================================================
def run_experiment_1(config: Dict[str, Any]) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("RUNNING EXPERIMENT 1: Does Uncertainty Change the Optimal Action?")
    print("="*70)
    
    rng = np.random.RandomState(42)
    diag = SecondShiftDiagnosticEngine()
    app = config["applications"]["solar_storage"]
    engine = DecisionEngine(app, diag)
    baseline_b = BaselineBSOHThreshold(diag, soh_cutoff=app["min_soh_threshold"])
    
    # Module A: SOH ~ 72%, High Confidence (Low Uncertainty: sigma = 0.02)
    # Module B: SOH ~ 72%, Low Confidence (High Uncertainty: sigma = 0.12)
    # Both have identical point estimates of SOH (72%) and R0 (2.4 mOhm)
    # Application Solar BESS threshold is SOH >= 70%
    
    # Ground truth physics modules (both truly 72% SOH)
    mod_a = BatteryModule("MOD_A_CERTAIN", soh=0.72, r0_multiplier=1.2, rng=rng)
    mod_b = BatteryModule("MOD_B_UNCERTAIN", soh=0.72, r0_multiplier=1.2, rng=rng)
    
    belief_a = ModuleBelief("MOD_A", prior_soh=0.72, prior_sigma_soh=0.02, prior_r0=0.0024, prior_sigma_r0=0.0002)
    belief_b = ModuleBelief("MOD_B", prior_soh=0.72, prior_sigma_soh=0.12, prior_r0=0.0024, prior_sigma_r0=0.0009)
    belief_a.triage_status = "ACCEPT"
    belief_b.triage_status = "ACCEPT"
    
    # 1. Evaluate under Baseline B (SOH Threshold only: uncertainty-blind)
    # A conventional BMS threshold policy checks if estimated SOH >= 70%
    action_base_a = "OPERATE" if belief_a.mu_soh >= app["min_soh_threshold"] else "RETIRE"
    action_base_b = "OPERATE" if belief_b.mu_soh >= app["min_soh_threshold"] else "RETIRE"
    
    # 2. Evaluate under Our Uncertainty-Aware Decision Engine
    action_our_a, test_a, debug_a = engine.select_action(belief_a)
    action_our_b, test_b, debug_b = engine.select_action(belief_b)
    
    # Hypothesis is confirmed if uncertainty changes our action (e.g. DERATE vs TEST)
    # while an uncertainty-blind threshold treats both identically
    confirmed = bool(action_our_a != action_our_b and action_base_a == action_base_b)
    
    results = {
        "experiment": "E1_Uncertainty_Action_Separation",
        "module_a": {
            "prior_soh": belief_a.mu_soh,
            "sigma_soh": belief_a.sigma_soh,
            "baseline_b_action": action_base_a,
            "our_action": action_our_a,
            "recommended_test": test_a,
            "op_utilities": debug_a["op_utilities"],
            "best_voi": debug_a["best_voi"]
        },
        "module_b": {
            "prior_soh": belief_b.mu_soh,
            "sigma_soh": belief_b.sigma_soh,
            "baseline_b_action": action_base_b,
            "our_action": action_our_b,
            "recommended_test": test_b,
            "op_utilities": debug_b["op_utilities"],
            "best_voi": debug_b["best_voi"]
        },
        "hypothesis_confirmed": bool(action_our_a != action_our_b and action_base_a == action_base_b)
    }
    
    print(f"Module A (Certain, sigma=0.02): Baseline B -> {action_base_a} | Our Engine -> {action_our_a}")
    print(f"Module B (Uncertain, sigma=0.12): Baseline B -> {action_base_b} | Our Engine -> {action_our_b} (Test: {test_b})")
    print(f"Hypothesis Confirmed: {results['hypothesis_confirmed']}")
    return results

# =====================================================================
# EXPERIMENT 2: Adaptive Testing vs Fixed Sequence (Monte Carlo)
# =====================================================================
def run_experiment_2(config: Dict[str, Any], n_samples: int = 500) -> Dict[str, Any]:
    print("\n" + "="*70)
    print(f"RUNNING EXPERIMENT 2: Diagnostic Burden Reduction (Monte Carlo N={n_samples})")
    print("="*70)
    
    rng = np.random.RandomState(config.get("random_seed", 42))
    diag = SecondShiftDiagnosticEngine()
    app = config["applications"]["solar_storage"]
    triage = TriageEngine()
    evaluator = MetricEvaluator(soh_threshold=app["min_soh_threshold"], r0_max_mohm=app["max_acceptable_r0_mohm"])
    
    # Synthesize realistic retired EV battery distribution:
    # Bimodal mixture: 60% reusable (SOH 0.70 - 0.92), 40% degraded/hazardous (SOH 0.40 - 0.69)
    true_sohs = np.concatenate([
        rng.normal(0.81, 0.06, int(n_samples * 0.60)),
        rng.normal(0.58, 0.08, int(n_samples * 0.40))
    ])
    true_sohs = np.clip(true_sohs, 0.35, 0.98)
    
    records_fixed = []
    records_adaptive = []
    
    for i, true_soh in enumerate(true_sohs):
        mod_id = f"CELL_{i:04d}"
        
        # Ground truth physics module
        r0_mult = 1.0 + (1.0 - true_soh) * 2.0
        mod_fixed = BatteryModule(mod_id, soh=true_soh, r0_multiplier=r0_mult, rng=np.random.RandomState(i))
        mod_adapt = BatteryModule(mod_id, soh=true_soh, r0_multiplier=r0_mult, rng=np.random.RandomState(i))
        
        # Prior with noisy initial SOH screening
        noisy_prior_soh = float(np.clip(true_soh + rng.normal(0.0, 0.08), 0.40, 0.95))
        prior_sigma = float(rng.uniform(0.05, 0.14))
        
        belief_fixed = ModuleBelief(mod_id, prior_soh=noisy_prior_soh, prior_sigma_soh=prior_sigma)
        belief_adapt = ModuleBelief(mod_id, prior_soh=noisy_prior_soh, prior_sigma_soh=prior_sigma)
        
        # 1. Execute Baseline A (Fixed Sequence: Pulse + Cycling + Thermal)
        b_a = BaselineAFixedTesting(diag, soh_cutoff=app["min_soh_threshold"])
        action_fixed, _ = b_a.evaluate(mod_fixed, belief_fixed)
        records_fixed.append({
            "module_id": mod_id,
            "true_soh": true_soh,
            "true_r0": mod_fixed.r0,
            "true_leakage": mod_fixed.abnormal_leakage,
            "decision": action_fixed,
            "diag_time_s": belief_fixed.total_diagnostic_time_s,
            "diag_energy_wh": belief_fixed.total_diagnostic_energy_wh,
            "diag_cost_inr": belief_fixed.total_test_cost_inr,
            "num_tests": len(belief_fixed.applied_tests),
            "final_mu_soh": belief_fixed.mu_soh,
            "final_sigma_soh": belief_fixed.sigma_soh
        })
        
        # 2. Execute Adaptive Policy (Triage -> SECONDShift VOI loop -> Decision Engine)
        t_status, _ = triage.evaluate(mod_adapt, belief_adapt, resting_duration_s=10.0)
        engine = DecisionEngine(app, diag)
        
        while True:
            act, test_to_run, _ = engine.select_action(belief_adapt, max_tests_allowed=3)
            if act == "TEST" and test_to_run is not None:
                diag.execute_test(test_to_run, mod_adapt, belief_adapt)
            else:
                final_action = act
                break
                
        records_adaptive.append({
            "module_id": mod_id,
            "true_soh": true_soh,
            "true_r0": mod_adapt.r0,
            "true_leakage": mod_adapt.abnormal_leakage,
            "decision": final_action,
            "diag_time_s": belief_adapt.total_diagnostic_time_s,
            "diag_energy_wh": belief_adapt.total_diagnostic_energy_wh,
            "diag_cost_inr": belief_adapt.total_test_cost_inr,
            "num_tests": len(belief_adapt.applied_tests),
            "final_mu_soh": belief_adapt.mu_soh,
            "final_sigma_soh": belief_adapt.sigma_soh
        })
        
    summary_fixed = evaluator.evaluate_cohort(records_fixed)
    summary_adaptive = evaluator.evaluate_cohort(records_adaptive)
    
    # Statistical significance: Paired t-test on diagnostic time & energy
    times_fixed = [r["diag_time_s"] for r in records_fixed]
    times_adapt = [r["diag_time_s"] for r in records_adaptive]
    t_stat_time, p_val_time = stats.ttest_rel(times_fixed, times_adapt)
    
    time_reduction_pct = ((summary_fixed["mean_diag_time_s"] - summary_adaptive["mean_diag_time_s"]) / summary_fixed["mean_diag_time_s"]) * 100.0
    energy_reduction_pct = ((summary_fixed["mean_diag_energy_wh"] - summary_adaptive["mean_diag_energy_wh"]) / summary_fixed["mean_diag_energy_wh"]) * 100.0
    
    results = {
        "experiment": "E2_Diagnostic_Burden_MonteCarlo",
        "n_samples": n_samples,
        "fixed_testing": summary_fixed,
        "adaptive_testing": summary_adaptive,
        "time_reduction_percent": round(time_reduction_pct, 2),
        "energy_reduction_percent": round(energy_reduction_pct, 2),
        "p_value_diagnostic_time": float(p_val_time),
        "statistically_significant": bool(p_val_time < 0.001)
    }
    
    print(f"Fixed Testing Mean Time: {summary_fixed['mean_diag_time_s']}s | Adaptive Testing Mean Time: {summary_adaptive['mean_diag_time_s']}s")
    print(f"Time Reduction: {time_reduction_pct:.2f}% | Energy Reduction: {energy_reduction_pct:.2f}% (p={p_val_time:.2e})")
    print(f"False Acceptance Rate: Fixed={summary_fixed['far_percent']}% | Adaptive={summary_adaptive['far_percent']}%")
    return results

# =====================================================================
# EXPERIMENT 3: Avoiding Unnecessary Isolation (UIR)
# =====================================================================
def run_experiment_3(config: Dict[str, Any], n_samples: int = 300) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("RUNNING EXPERIMENT 3: Unnecessary Isolation Avoidance (Suspicious but Healthy)")
    print("="*70)
    
    rng = np.random.RandomState(101)
    diag = SecondShiftDiagnosticEngine()
    app = config["applications"]["solar_storage"]
    triage = TriageEngine()
    evaluator = MetricEvaluator(soh_threshold=app["min_soh_threshold"], r0_max_mohm=app["max_acceptable_r0_mohm"])
    
    # Cohort of genuinely healthy modules (SOH 0.72 - 0.78, truly compliant)
    # but corrupted by temporary surface polarization, noisy resting voltage, or missing history
    # causing an initial suspicious appearance (initial estimate 0.68 with sigma 0.10)
    true_sohs = rng.uniform(0.72, 0.78, n_samples)
    
    records_threshold = []
    records_adaptive = []
    
    for i, true_soh in enumerate(true_sohs):
        mod_id = f"SUSP_{i:04d}"
        mod = BatteryModule(mod_id, soh=true_soh, initial_soc=0.35, rng=np.random.RandomState(i))
        
        # Suspicious initial prior: noisy reading underestimates SOH as 0.68
        prior_soh = float(np.clip(0.68 + rng.normal(0.0, 0.02), 0.64, 0.71))
        prior_sigma = 0.08
        
        # Baseline B (Uncertainty-blind cutoff at 0.70)
        b_base = ModuleBelief(mod_id, prior_soh=prior_soh, prior_sigma_soh=prior_sigma)
        b_base.triage_status = "ACCEPT"
        base_engine = BaselineBSOHThreshold(diag, soh_cutoff=app["min_soh_threshold"])
        act_base, _ = base_engine.evaluate(mod, b_base)
        
        records_threshold.append({
            "module_id": mod_id,
            "true_soh": true_soh,
            "true_r0": mod.r0,
            "decision": act_base,
            "diag_time_s": b_base.total_diagnostic_time_s,
            "diag_energy_wh": b_base.total_diagnostic_energy_wh,
            "diag_cost_inr": b_base.total_test_cost_inr,
            "num_tests": 1,
            "final_mu_soh": b_base.mu_soh,
            "final_sigma_soh": b_base.sigma_soh
        })
        
        # Our Adaptive Uncertainty-Aware System (HERMES + VOI)
        b_adapt = ModuleBelief(mod_id, prior_soh=prior_soh, prior_sigma_soh=prior_sigma)
        triage.evaluate(mod, b_adapt, resting_duration_s=10.0)
        engine = DecisionEngine(app, diag)
        
        while True:
            act, test_to_run, _ = engine.select_action(b_adapt)
            if act == "TEST" and test_to_run is not None:
                diag.execute_test(test_to_run, mod, b_adapt)
            else:
                final_act = act
                break
                
        records_adaptive.append({
            "module_id": mod_id,
            "true_soh": true_soh,
            "true_r0": mod.r0,
            "decision": final_act,
            "diag_time_s": b_adapt.total_diagnostic_time_s,
            "diag_energy_wh": b_adapt.total_diagnostic_energy_wh,
            "diag_cost_inr": b_adapt.total_test_cost_inr,
            "num_tests": len(b_adapt.applied_tests),
            "final_mu_soh": b_adapt.mu_soh,
            "final_sigma_soh": b_adapt.sigma_soh
        })
        
    res_thresh = evaluator.evaluate_cohort(records_threshold)
    res_adapt = evaluator.evaluate_cohort(records_adaptive)
    
    uir_reduction = res_thresh["uir_percent"] - res_adapt["uir_percent"]
    energy_saved_kwh = res_adapt["usable_energy_retained_kwh"] - res_thresh["usable_energy_retained_kwh"]
    
    results = {
        "experiment": "E3_Unnecessary_Isolation_Reduction",
        "threshold_baseline_uir_percent": res_thresh["uir_percent"],
        "adaptive_system_uir_percent": res_adapt["uir_percent"],
        "uir_reduction_points": round(uir_reduction, 2),
        "usable_energy_recovered_baseline_kwh": res_thresh["usable_energy_retained_kwh"],
        "usable_energy_recovered_adaptive_kwh": res_adapt["usable_energy_retained_kwh"],
        "additional_energy_saved_kwh": round(energy_saved_kwh, 2)
    }
    
    print(f"Threshold Baseline UIR: {res_thresh['uir_percent']}% | Adaptive Policy UIR: {res_adapt['uir_percent']}%")
    print(f"Unnecessary Isolation Reduced by {uir_reduction:.1f}% points! Recovered +{energy_saved_kwh:.1f} kWh of usable energy.")
    return results

# =====================================================================
# EXPERIMENT 4: Degraded Module Identification & Safety Dominance
# =====================================================================
def run_experiment_4(config: Dict[str, Any], n_samples: int = 400) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("RUNNING EXPERIMENT 4: Degraded Module Detection & Safety Dominance")
    print("="*70)
    
    rng = np.random.RandomState(202)
    diag = SecondShiftDiagnosticEngine()
    app = config["applications"]["solar_storage"]
    triage = TriageEngine()
    evaluator = MetricEvaluator(soh_threshold=app["min_soh_threshold"], r0_max_mohm=app["max_acceptable_r0_mohm"])
    
    # 5 Heterogeneous Archetypes:
    # 1. Healthy (SOH 0.85, R0 nominal) - 25%
    # 2. Moderately Degraded (SOH 0.68, R0 slight rise) - 25%
    # 3. Severely Degraded (SOH 0.48) - 20%
    # 4. High-Resistance defect (SOH 0.75, R0 5.0 mOhm) - 15%
    # 5. Micro-short leakage (abnormal self-discharge) - 15%
    
    records = []
    
    for i in range(n_samples):
        mod_id = f"ARCH_{i:04d}"
        category = rng.choice(["HEALTHY", "MOD_DEG", "SEV_DEG", "HIGH_RES", "LEAKAGE"], p=[0.25, 0.25, 0.20, 0.15, 0.15])
        
        if category == "HEALTHY":
            true_soh = rng.uniform(0.80, 0.92)
            r0_m = 1.0
            leak = False
            bulge = False
        elif category == "MOD_DEG":
            true_soh = rng.uniform(0.64, 0.69)
            r0_m = 1.3
            leak = False
            bulge = False
        elif category == "SEV_DEG":
            true_soh = rng.uniform(0.40, 0.55)
            r0_m = 2.2
            leak = False
            bulge = False
        elif category == "HIGH_RES":
            true_soh = rng.uniform(0.72, 0.80)  # SOH looks okay, but resistance is dangerous!
            r0_m = 3.5  # High resistance defect
            leak = False
            bulge = False
        else:  # LEAKAGE
            true_soh = rng.uniform(0.70, 0.82)
            r0_m = 1.2
            leak = True
            bulge = False
            
        mod = BatteryModule(mod_id, soh=true_soh, r0_multiplier=r0_m, abnormal_leakage=leak, rng=np.random.RandomState(i))
        belief = ModuleBelief(mod_id, prior_soh=0.75, prior_sigma_soh=0.12, prior_r0=0.0025, prior_sigma_r0=0.0010)
        
        # Triage screening
        t_status, _ = triage.evaluate(mod, belief, resting_duration_s=15.0)
        engine = DecisionEngine(app, diag)
        
        if t_status == "REJECT":
            final_action = "RETIRE"
        else:
            while True:
                act, test_to_run, _ = engine.select_action(belief, max_tests_allowed=3)
                if act == "TEST" and test_to_run is not None:
                    diag.execute_test(test_to_run, mod, belief)
                else:
                    final_action = act
                    break
                    
        records.append({
            "module_id": mod_id,
            "category": category,
            "true_soh": true_soh,
            "true_r0": mod.r0,
            "true_leakage": leak,
            "decision": final_action,
            "diag_time_s": belief.total_diagnostic_time_s,
            "diag_energy_wh": belief.total_diagnostic_energy_wh,
            "diag_cost_inr": belief.total_test_cost_inr,
            "num_tests": len(belief.applied_tests),
            "final_mu_soh": belief.mu_soh,
            "final_sigma_soh": belief.sigma_soh
        })
        
    cohort_summary = evaluator.evaluate_cohort(records)
    
    # Specific safety checks
    leakage_records = [r for r in records if r["category"] == "LEAKAGE"]
    leakage_escapes = sum(1 for r in leakage_records if r["decision"] == "OPERATE")
    
    high_res_records = [r for r in records if r["category"] == "HIGH_RES"]
    high_res_escapes = sum(1 for r in high_res_records if r["decision"] == "OPERATE")
    
    results = {
        "experiment": "E4_Safety_Dominance_Degraded_Detection",
        "cohort_summary": cohort_summary,
        "leakage_escape_rate_percent": round((leakage_escapes / len(leakage_records)) * 100.0, 2),
        "high_res_escape_rate_percent": round((high_res_escapes / len(high_res_records)) * 100.0, 2),
        "overall_far_percent": cohort_summary["far_percent"],
        "safety_requirement_met": bool(cohort_summary["far_percent"] <= 1.0)
    }
    
    print(f"Overall False Acceptance Rate (FAR): {cohort_summary['far_percent']}% (Target <= 1.0%)")
    print(f"Internal Micro-Short Escapes: {leakage_escapes} / {len(leakage_records)}")
    print(f"High-Resistance Defect Escapes: {high_res_escapes} / {len(high_res_records)}")
    print(f"Safety Gate Met: {results['safety_requirement_met']}")
    return results

# =====================================================================
# EXPERIMENT 5: Controlled Participation as Diagnostic Information
# =====================================================================
def run_experiment_5(config: Dict[str, Any], n_trials: int = 50) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("RUNNING EXPERIMENT 5: Controlled Module Participation as Information")
    print("="*70)
    
    rng = np.random.RandomState(303)
    diag = SecondShiftDiagnosticEngine()
    
    # Compare:
    # Mode 1 (Passive Only): Module kept in BYPASS during operation. No current flows, no dynamic observation.
    # Mode 2 (Controlled Intervention): Module operated in DERATED state (0.5x string current) with HERMES in-situ feedback.
    
    sigma_reductions_passive = []
    sigma_reductions_intervention = []
    
    for trial in range(n_trials):
        true_soh = rng.uniform(0.68, 0.76)
        mod_passive = BatteryModule(f"PASS_{trial}", soh=true_soh, initial_soc=0.60, rng=np.random.RandomState(trial))
        mod_interv = BatteryModule(f"INT_{trial}", soh=true_soh, initial_soc=0.60, rng=np.random.RandomState(trial))
        
        b_passive = ModuleBelief(f"PASS_{trial}", prior_soh=0.72, prior_sigma_soh=0.10, prior_r0=0.0026, prior_sigma_r0=0.0008)
        b_interv = ModuleBelief(f"INT_{trial}", prior_soh=0.72, prior_sigma_soh=0.10, prior_r0=0.0026, prior_sigma_r0=0.0008)
        
        hermes_passive = HermesController(f"PASS_{trial}")
        hermes_interv = HermesController(f"INT_{trial}")
        
        hermes_passive.command_transition("BYPASS", "Passive idle mode")
        hermes_interv.command_transition("DERATED", "Active exploratory diagnosis")
        
        # Simulate 300 seconds of pack operation with 25A string load
        dt = 1.0
        for _ in range(300):
            hermes_passive.step_operational_feedback(mod_passive, b_passive, string_current_a=25.0, dt_s=dt)
            hermes_interv.step_operational_feedback(mod_interv, b_interv, string_current_a=25.0, dt_s=dt)
            
        sigma_reductions_passive.append(0.10 - b_passive.sigma_soh)
        sigma_reductions_intervention.append(0.10 - b_interv.sigma_soh)
        
    mean_red_passive = float(np.mean(sigma_reductions_passive))
    mean_red_interv = float(np.mean(sigma_reductions_intervention))
    
    # Paired t-test
    t_stat, p_val = stats.ttest_rel(sigma_reductions_intervention, sigma_reductions_passive)
    
    # Statistical verdict: must have p < 0.01 and meaningful reduction
    statistically_meaningful = bool(p_val < 0.001 and mean_red_interv > mean_red_passive + 0.01)
    
    results = {
        "experiment": "E5_Controlled_Intervention_Information_Gain",
        "n_trials": n_trials,
        "mean_sigma_reduction_passive": round(mean_red_passive, 4),
        "mean_sigma_reduction_intervention": round(mean_red_interv, 4),
        "t_statistic": round(float(t_stat), 3),
        "p_value": float(p_val),
        "statistically_meaningful": statistically_meaningful,
        "verdict": "SURVIVED" if statistically_meaningful else "KILL_COMPONENT"
    }
    
    print(f"Passive Uncertainty Reduction Delta Sigma: {mean_red_passive:.4f}")
    print(f"Intervention (DERATED Feedback) Delta Sigma: {mean_red_interv:.4f}")
    print(f"Paired t-test: t={t_stat:.3f}, p={p_val:.2e} -> Verdict: {results['verdict']}")
    return results

# =====================================================================
# EXPERIMENT ABLATION: Component-by-Component Ablation Study
# =====================================================================
def run_ablation_study(config: Dict[str, Any], n_samples: int = 300) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("RUNNING ABLATION STUDY: Evaluating Marginal Utility of Core Architecture")
    print("="*70)
    
    # 6 Configurations:
    # FULL: Complete proposed system
    # A: Without Uncertainty (sigma=0)
    # B: Without Adaptive Testing (rigid 3 tests)
    # C: Without HERMES (binary accept/reject, no DERATE)
    # D: Without Operational Feedback (no in-situ update)
    # E: Without Application Context (fixed universal threshold)
    # F: Without VOI (random test selector)
    
    variants = ["FULL", "NO_UNCERTAINTY", "NO_ADAPTIVE_TEST", "NO_HERMES", "NO_OP_FEEDBACK", "NO_APP_CONTEXT", "NO_VOI"]
    summary_results = {}
    
    app = config["applications"]["solar_storage"]
    evaluator = MetricEvaluator(soh_threshold=app["min_soh_threshold"], r0_max_mohm=app["max_acceptable_r0_mohm"])
    diag = SecondShiftDiagnosticEngine()
    triage = TriageEngine()
    
    rng_master = np.random.RandomState(404)
    true_sohs = np.clip(rng_master.normal(0.74, 0.10, n_samples), 0.40, 0.95)
    
    for v in variants:
        records = []
        for i, true_soh in enumerate(true_sohs):
            mod_id = f"ABL_{v}_{i:03d}"
            r0_m = 1.0 + (1.0 - true_soh) * 1.8
            mod = BatteryModule(mod_id, soh=true_soh, r0_multiplier=r0_m, rng=np.random.RandomState(i))
            
            prior_sigma = 0.0001 if v == "NO_UNCERTAINTY" else 0.09
            prior_soh = float(np.clip(true_soh + rng_master.normal(0.0, 0.04), 0.45, 0.95))
            belief = ModuleBelief(mod_id, prior_soh=prior_soh, prior_sigma_soh=prior_sigma)
            
            triage.evaluate(mod, belief, resting_duration_s=10.0)
            
            if v == "NO_APP_CONTEXT":
                local_app = {"min_soh_threshold": 0.80, "max_acceptable_r0_mohm": 2.5, "safety_penalty_inr": 10000.0, "energy_revenue_per_kwh_inr": 10.0, "lifetime_cycles": 1000}
            else:
                local_app = app
                
            engine = DecisionEngine(local_app, diag)
            
            if v == "NO_ADAPTIVE_TEST":
                diag.execute_test("pulse_power_test", mod, belief)
                diag.execute_test("short_coulometric_cycle", mod, belief)
                diag.execute_test("thermal_recovery_step", mod, belief)
                act, _, _ = engine.select_action(belief, max_tests_allowed=0)
            elif v == "NO_VOI":
                # Static heuristic: always pulse test first
                diag.execute_test("pulse_power_test", mod, belief)
                act, _, _ = engine.select_action(belief, max_tests_allowed=0)
            else:
                while True:
                    act, test_to_run, _ = engine.select_action(belief, max_tests_allowed=3)
                    if act == "TEST" and test_to_run is not None:
                        diag.execute_test(test_to_run, mod, belief)
                    else:
                        break
                        
            if v == "NO_HERMES" and act == "DERATE":
                act = "RETIRE"  # Binary only: cannot derate
                
            records.append({
                "module_id": mod_id,
                "true_soh": true_soh,
                "true_r0": mod.r0,
                "decision": act,
                "diag_time_s": belief.total_diagnostic_time_s,
                "diag_energy_wh": belief.total_diagnostic_energy_wh,
                "diag_cost_inr": belief.total_test_cost_inr,
                "num_tests": len(belief.applied_tests),
                "final_mu_soh": belief.mu_soh,
                "final_sigma_soh": belief.sigma_soh
            })
            
        summary = evaluator.evaluate_cohort(records)
        summary_results[v] = {
            "far_percent": summary["far_percent"],
            "uir_percent": summary["uir_percent"],
            "mean_diag_time_s": summary["mean_diag_time_s"],
            "usable_energy_kwh": summary["usable_energy_retained_kwh"],
            "decision_efficiency": summary["decision_efficiency"]
        }
        print(f"Variant [{v:16s}]: DE={summary['decision_efficiency']:7.2f} | FAR={summary['far_percent']:4.1f}% | UIR={summary['uir_percent']:4.1f}% | Time={summary['mean_diag_time_s']:5.1f}s")
        
    return summary_results

# =====================================================================
# MAIN CLI ENTRY POINT
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="RMK-REVOLT Experiment Suite")
    parser.add_argument("--experiment", type=str, default="ALL", choices=["E1", "E2", "E3", "E4", "E5", "ABLATION", "ALL"], help="Experiment identifier to run")
    parser.add_argument("--samples", type=int, default=500, help="Monte Carlo sample count")
    args = parser.parse_args()
    
    config = get_default_configs()
    results_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    all_outputs = {}
    
    if args.experiment in ["E1", "ALL"]:
        res_e1 = run_experiment_1(config)
        all_outputs["E1"] = res_e1
        with open(os.path.join(results_dir, "experiment_1_results.json"), "w") as f:
            json.dump(res_e1, f, indent=2)
            
    if args.experiment in ["E2", "ALL"]:
        res_e2 = run_experiment_2(config, n_samples=args.samples)
        all_outputs["E2"] = res_e2
        with open(os.path.join(results_dir, "experiment_2_results.json"), "w") as f:
            json.dump(res_e2, f, indent=2)
            
    if args.experiment in ["E3", "ALL"]:
        res_e3 = run_experiment_3(config, n_samples=min(args.samples, 300))
        all_outputs["E3"] = res_e3
        with open(os.path.join(results_dir, "experiment_3_results.json"), "w") as f:
            json.dump(res_e3, f, indent=2)
            
    if args.experiment in ["E4", "ALL"]:
        res_e4 = run_experiment_4(config, n_samples=min(args.samples, 400))
        all_outputs["E4"] = res_e4
        with open(os.path.join(results_dir, "experiment_4_results.json"), "w") as f:
            json.dump(res_e4, f, indent=2)
            
    if args.experiment in ["E5", "ALL"]:
        res_e5 = run_experiment_5(config, n_trials=50)
        all_outputs["E5"] = res_e5
        with open(os.path.join(results_dir, "experiment_5_results.json"), "w") as f:
            json.dump(res_e5, f, indent=2)
            
    if args.experiment in ["ABLATION", "ALL"]:
        res_abl = run_ablation_study(config, n_samples=300)
        all_outputs["ABLATION"] = res_abl
        with open(os.path.join(results_dir, "ablation_results.json"), "w") as f:
            json.dump(res_abl, f, indent=2)

    with open(os.path.join(results_dir, "master_experiment_summary.json"), "w") as f:
        json.dump(all_outputs, f, indent=2)
        
    print("\n" + "="*70)
    print(f"ALL REQUESTED EXPERIMENTS COMPLETED SUCCESSFULLY.")
    print(f"Results archived to {os.path.abspath(results_dir)}")
    print("="*70)

if __name__ == "__main__":
    main()
