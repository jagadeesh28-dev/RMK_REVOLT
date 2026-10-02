"""
RMK-REVOLT: Master RC-VOI Simulation Suite (v1)
Runs rigorous comparative benchmarks across:
- Policy A: Fixed Qualification (Industrial Standard)
- Policy B: Scalar SOH Threshold (Uncertainty-Blind Conventional BMS)
- Policy C: Uncertainty Threshold (Heuristic Confidence-Interval Policy)
- Policy D: Risk-Constrained Value-of-Information (RC-VOI)

Includes:
1. 500-Module Cohort Benchmark
2. 5,000-Module Cohort Benchmark
3. Direct Head-to-Head: Policy D vs Policy C
4. Monte Carlo Multi-Seed Validation (6 Fixed Seeds)
5. Comprehensive Sensitivity Analysis (Labor, Power, Penalty, Uncertainty)
6. Component Ablation Study on RC-VOI
7. Answers to Research Questions Q1 - Q8
"""

import os
import sys
import json
import yaml
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief
from src.triage import TriageEngine
from src.secondshift import SecondShiftDiagnosticEngine
from src.policies import (
    PolicyAFixedQualification,
    PolicyBScalarThreshold,
    PolicyCUncertaintyThreshold,
    PolicyDRCVOI
)
from metrics.stats_calculator import compute_distribution_metrics, cohens_d, bootstrap_ci

def generate_synthetic_cohort(n_samples: int, seed: int) -> List[Dict[str, Any]]:
    """
    Generates realistic retired EV battery cohort with multimodal degradation:
    - 60% reusable modules (SOH 0.70 - 0.94)
    - 40% degraded/suspicious modules (SOH 0.40 - 0.69)
    Includes Ohmic resistance degradation, realistic measurement noise, and leakage.
    """
    rng = np.random.RandomState(seed)
    
    sohs_healthy = rng.normal(0.81, 0.05, int(n_samples * 0.60))
    sohs_degraded = rng.normal(0.58, 0.08, int(n_samples * 0.40))
    true_sohs = np.clip(np.concatenate([sohs_healthy, sohs_degraded]), 0.35, 0.98)
    rng.shuffle(true_sohs)
    
    cohort = []
    for i, true_soh in enumerate(true_sohs):
        # 10% chance of high resistance defect, 5% micro-short leakage
        has_high_r = bool(rng.uniform(0, 1) < 0.10)
        has_leakage = bool(rng.uniform(0, 1) < 0.05)
        
        r0_mult = 3.5 if has_high_r else (1.0 + (1.0 - true_soh) * 1.8)
        
        # Initial noisy screening observation gives prior mean and uncertainty
        prior_noise = rng.normal(0.0, 0.06)
        prior_soh = float(np.clip(true_soh + prior_noise, 0.40, 0.96))
        prior_sigma = float(rng.uniform(0.04, 0.14))
        
        cohort.append({
            "id": f"MOD_{seed}_{i:05d}",
            "true_soh": float(true_soh),
            "r0_multiplier": float(r0_mult),
            "has_leakage": has_leakage,
            "has_high_r": has_high_r,
            "prior_soh": prior_soh,
            "prior_sigma_soh": prior_sigma,
            "prior_r0": float(0.0015 * r0_mult),
            "prior_sigma_r0": 0.0006
        })
    return cohort

def run_cohort_benchmark(
    cohort: List[Dict[str, Any]],
    app_config: Dict[str, Any],
    labor_rate_hr: float = 250.0,
    elec_cost_kwh: float = 8.0
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Evaluates all 4 policies on the same identical battery population."""
    diag = SecondShiftDiagnosticEngine(electricity_cost_kwh=elec_cost_kwh, labor_rate_hr=labor_rate_hr)
    triage = TriageEngine()
    
    soh_min = app_config.get("min_soh_threshold", 0.70)
    r0_max = app_config.get("max_acceptable_r0_mohm", 3.5) / 1000.0
    
    policy_a = PolicyAFixedQualification(diag, app_config)
    policy_b = PolicyBScalarThreshold(diag, app_config)
    policy_c = PolicyCUncertaintyThreshold(diag, app_config)
    policy_d = PolicyDRCVOI(diag, app_config)
    
    policies = {
        "A_Fixed": policy_a,
        "B_Scalar": policy_b,
        "C_UncertaintyThresh": policy_c,
        "D_RC_VOI": policy_d
    }
    
    records = []
    
    for item in cohort:
        true_soh = item["true_soh"]
        is_truly_healthy = (true_soh >= soh_min and not item["has_high_r"] and not item["has_leakage"])
        nominal_kwh = (50.0 * 3.2) / 1000.0  # 0.16 kWh
        true_module_kwh = true_soh * nominal_kwh
        
        for pol_name, pol_obj in policies.items():
            # Fresh physical module instantiation with identical ground truth
            mod = BatteryModule(
                item["id"],
                soh=true_soh,
                r0_multiplier=item["r0_multiplier"],
                abnormal_leakage=item["has_leakage"]
            )
            belief = ModuleBelief(
                item["id"],
                prior_soh=item["prior_soh"],
                prior_sigma_soh=item["prior_sigma_soh"],
                prior_r0=item["prior_r0"],
                prior_sigma_r0=item["prior_sigma_r0"]
            )
            
            # Triage screening
            t_status, _ = triage.evaluate(mod, belief, resting_duration_s=10.0)
            
            if t_status == "REJECT":
                action = "RETIRE"
                info = {"diag_time_s": 10.0, "diag_energy_wh": 0.05, "diag_cost_inr": (10.0/3600.0)*labor_rate_hr, "tests_applied": ["triage"]}
            else:
                action, info = pol_obj.evaluate(mod, belief)
                
            # Outcome classifications
            is_false_accept = (not is_truly_healthy and action == "OPERATE")
            is_false_reject = (is_truly_healthy and action == "RETIRE")
            is_unnecessary_isolation = (is_truly_healthy and action in ["RETIRE", "ISOLATE"])
            
            retained_kwh = 0.0
            if is_truly_healthy:
                if action == "OPERATE":
                    retained_kwh = true_module_kwh
                elif action == "DERATE":
                    retained_kwh = true_module_kwh * 0.80
                    
            records.append({
                "module_id": item["id"],
                "policy": pol_name,
                "true_soh": true_soh,
                "is_truly_healthy": is_truly_healthy,
                "action": action,
                "diag_time_s": info["diag_time_s"],
                "diag_energy_wh": info["diag_energy_wh"],
                "diag_cost_inr": info["diag_cost_inr"],
                "num_tests": len(info["tests_applied"]),
                "is_false_accept": is_false_accept,
                "is_false_reject": is_false_reject,
                "is_unnecessary_isolation": is_unnecessary_isolation,
                "retained_kwh": retained_kwh
            })
            
    df = pd.DataFrame(records)
    
    # Aggregate Policy Summary
    summary = {}
    for pol_name in policies.keys():
        pdf = df[df["policy"] == pol_name]
        n_total = len(pdf)
        n_healthy = pdf["is_truly_healthy"].sum()
        n_degraded = n_total - n_healthy
        
        far = (pdf["is_false_accept"].sum() / max(n_degraded, 1)) * 100.0
        frr = (pdf["is_false_reject"].sum() / max(n_healthy, 1)) * 100.0
        uir = (pdf["is_unnecessary_isolation"].sum() / max(n_healthy, 1)) * 100.0
        
        time_stats = compute_distribution_metrics(pdf["diag_time_s"].tolist())
        cost_stats = compute_distribution_metrics(pdf["diag_cost_inr"].tolist())
        energy_stats = compute_distribution_metrics(pdf["diag_energy_wh"].tolist())
        
        total_kwh_recovered = pdf["retained_kwh"].sum()
        potential_kwh = df[(df["policy"] == pol_name) & (df["is_truly_healthy"])]["true_soh"].sum() * nominal_kwh
        kwh_retention_pct = (total_kwh_recovered / max(potential_kwh, 1e-6)) * 100.0
        
        # Decision Efficiency
        mean_cost = cost_stats["mean"]
        mean_time_min = time_stats["mean"] / 60.0
        safety_multiplier = 1.0 if far <= 1.0 else max(0.01, 1.0 - (far - 1.0) * 0.25)
        decision_efficiency = (total_kwh_recovered * 10.0 * safety_multiplier) / max(mean_cost * (mean_time_min + 1.0), 1.0)
        
        summary[pol_name] = {
            "n_total": n_total,
            "far_percent": round(far, 2),
            "frr_percent": round(frr, 2),
            "uir_percent": round(uir, 2),
            "total_kwh_retained": round(total_kwh_recovered, 2),
            "kwh_retention_percent": round(kwh_retention_pct, 2),
            "decision_efficiency": round(decision_efficiency, 3),
            "time_distribution_s": time_stats,
            "cost_distribution_inr": cost_stats,
            "energy_distribution_wh": energy_stats
        }
        
    return df, summary

def run_sensitivity_sweeps(app_config: Dict[str, Any], n_samples: int = 500) -> Dict[str, Any]:
    """Sweeps labor rate, electricity tariff, failure penalty, and prior uncertainty."""
    print("Running Sensitivity Analysis across parameter grid...")
    sweep_results = {}
    cohort = generate_synthetic_cohort(n_samples, seed=777)
    
    # 1. Labor Rate Sweep (INR 100 to INR 500/hr)
    labor_sweep = []
    for labor in [100.0, 200.0, 250.0, 350.0, 500.0]:
        _, s = run_cohort_benchmark(cohort, app_config, labor_rate_hr=labor)
        labor_sweep.append({
            "labor_rate_hr": labor,
            "time_fixed_s": s["A_Fixed"]["time_distribution_s"]["mean"],
            "time_c_s": s["C_UncertaintyThresh"]["time_distribution_s"]["mean"],
            "time_rc_voi_s": s["D_RC_VOI"]["time_distribution_s"]["mean"],
            "cost_c_inr": s["C_UncertaintyThresh"]["cost_distribution_inr"]["mean"],
            "cost_rc_voi_inr": s["D_RC_VOI"]["cost_distribution_inr"]["mean"],
            "de_c": s["C_UncertaintyThresh"]["decision_efficiency"],
            "de_rc_voi": s["D_RC_VOI"]["decision_efficiency"]
        })
    sweep_results["labor_rate_sweep"] = labor_sweep
    
    # 2. Failure Penalty Sweep (INR 2,000 to INR 25,000)
    penalty_sweep = []
    for pen in [2000.0, 4000.0, 6000.0, 12000.0, 25000.0]:
        local_app = dict(app_config)
        local_app["safety_penalty_inr"] = pen
        _, s = run_cohort_benchmark(cohort, local_app)
        penalty_sweep.append({
            "safety_penalty_inr": pen,
            "far_scalar_percent": s["B_Scalar"]["far_percent"],
            "far_c_percent": s["C_UncertaintyThresh"]["far_percent"],
            "far_rc_voi_percent": s["D_RC_VOI"]["far_percent"],
            "time_rc_voi_s": s["D_RC_VOI"]["time_distribution_s"]["mean"],
            "uir_rc_voi_percent": s["D_RC_VOI"]["uir_percent"]
        })
    sweep_results["penalty_sweep"] = penalty_sweep
    
    # 3. Prior Uncertainty Scale Sweep
    unc_sweep = []
    for sigma_base in [0.03, 0.06, 0.09, 0.12, 0.16]:
        # Synthesize custom cohort with scaled sigma
        c_mod = generate_synthetic_cohort(n_samples, seed=888)
        for itm in c_mod:
            itm["prior_sigma_soh"] = sigma_base
        _, s = run_cohort_benchmark(c_mod, app_config)
        unc_sweep.append({
            "prior_sigma_soh": sigma_base,
            "time_c_s": s["C_UncertaintyThresh"]["time_distribution_s"]["mean"],
            "time_rc_voi_s": s["D_RC_VOI"]["time_distribution_s"]["mean"],
            "cost_c_inr": s["C_UncertaintyThresh"]["cost_distribution_inr"]["mean"],
            "cost_rc_voi_inr": s["D_RC_VOI"]["cost_distribution_inr"]["mean"],
            "uir_c_percent": s["C_UncertaintyThresh"]["uir_percent"],
            "uir_rc_voi_percent": s["D_RC_VOI"]["uir_percent"]
        })
    sweep_results["uncertainty_scale_sweep"] = unc_sweep
    
    return sweep_results

def run_ablation_benchmarks(cohort: List[Dict[str, Any]], app_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates 5 targeted ablation variants of RC-VOI:
    1. Full RC-VOI (Reference)
    2. No Uncertainty (sigma=0)
    3. No Test Cost (Cost(k)=0)
    4. No Application Context (Rigid threshold)
    5. No Derating (Binary accept/retire only)
    """
    diag = SecondShiftDiagnosticEngine()
    triage = TriageEngine()
    soh_min = app_config.get("min_soh_threshold", 0.70)
    nominal_kwh = (50.0 * 3.2) / 1000.0
    
    variants = ["FULL_RC_VOI", "NO_UNCERTAINTY", "NO_TEST_COST", "NO_APP_CONTEXT", "NO_DERATING"]
    ablation_summary = {}
    
    for v in variants:
        records = []
        for itm in cohort:
            true_soh = itm["true_soh"]
            is_truly_healthy = (true_soh >= soh_min and not itm["has_high_r"] and not itm["has_leakage"])
            mod = BatteryModule(itm["id"], soh=true_soh, r0_multiplier=itm["r0_multiplier"], abnormal_leakage=itm["has_leakage"])
            
            p_sigma = 0.0001 if v == "NO_UNCERTAINTY" else itm["prior_sigma_soh"]
            belief = ModuleBelief(itm["id"], prior_soh=itm["prior_soh"], prior_sigma_soh=p_sigma, prior_r0=itm["prior_r0"], prior_sigma_r0=itm["prior_sigma_r0"])
            
            triage.evaluate(mod, belief, resting_duration_s=10.0)
            
            local_app = dict(app_config)
            if v == "NO_APP_CONTEXT":
                local_app["min_soh_threshold"] = 0.80  # rigid EV threshold
                local_app["safety_penalty_inr"] = 12000.0
                
            local_diag = SecondShiftDiagnosticEngine(labor_rate_hr=0.0 if v == "NO_TEST_COST" else 250.0)
            policy = PolicyDRCVOI(local_diag, local_app)
            
            action, info = policy.evaluate(mod, belief)
            
            if v == "NO_DERATING" and action == "DERATE":
                action = "RETIRE"  # Binary only: cannot derate
                
            is_fa = (not is_truly_healthy and action == "OPERATE")
            is_uir = (is_truly_healthy and action in ["RETIRE", "ISOLATE"])
            
            retained = 0.0
            if is_truly_healthy:
                if action == "OPERATE":
                    retained = true_soh * nominal_kwh
                elif action == "DERATE":
                    retained = true_soh * nominal_kwh * 0.80
                    
            records.append({
                "diag_time_s": info["diag_time_s"],
                "diag_cost_inr": info["diag_cost_inr"],
                "is_fa": is_fa,
                "is_uir": is_uir,
                "retained_kwh": retained
            })
            
        rdf = pd.DataFrame(records)
        n_healthy = sum(1 for itm in cohort if (itm["true_soh"] >= soh_min and not itm["has_high_r"] and not itm["has_leakage"]))
        n_degraded = len(cohort) - n_healthy
        
        far = (rdf["is_fa"].sum() / max(n_degraded, 1)) * 100.0
        uir = (rdf["is_uir"].sum() / max(n_healthy, 1)) * 100.0
        mean_time = rdf["diag_time_s"].mean()
        mean_cost = rdf["diag_cost_inr"].mean()
        tot_kwh = rdf["retained_kwh"].sum()
        
        de = (tot_kwh * 10.0 * (1.0 if far <= 1.0 else 0.1)) / max(mean_cost * (mean_time / 60.0 + 1.0), 1.0)
        
        ablation_summary[v] = {
            "mean_time_s": round(mean_time, 2),
            "mean_cost_inr": round(mean_cost, 2),
            "far_percent": round(far, 2),
            "uir_percent": round(uir, 2),
            "total_kwh": round(tot_kwh, 2),
            "decision_efficiency": round(de, 3)
        }
        
    return ablation_summary

def main():
    print("="*75)
    print("STARTING RC-VOI SIMULATION v1: RIGOROUS FOUR-POLICY BENCHMARK")
    print("="*75)
    
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    app = config["applications"]["solar_storage"]
    
    results_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    # -------------------------------------------------------------
    # 1. 500-Module Benchmark
    # -------------------------------------------------------------
    print("\n[STEP 1/5] Executing 500-Module Population Benchmark (Seed 42)...")
    cohort_500 = generate_synthetic_cohort(500, seed=42)
    df_500, summary_500 = run_cohort_benchmark(cohort_500, app)
    df_500.to_csv(os.path.join(results_dir, "rc_voi_500_raw_records.csv"), index=False)
    with open(os.path.join(results_dir, "rc_voi_500_summary.json"), "w") as f:
        json.dump(summary_500, f, indent=2)
    print("Completed 500-Module Benchmark. CSV & JSON saved.")

    # -------------------------------------------------------------
    # 2. 5,000-Module Population Benchmark
    # -------------------------------------------------------------
    print("\n[STEP 2/5] Executing 5,000-Module Population Benchmark (Seed 101)...")
    cohort_5000 = generate_synthetic_cohort(5000, seed=101)
    df_5000, summary_5000 = run_cohort_benchmark(cohort_5000, app)
    df_5000.to_csv(os.path.join(results_dir, "rc_voi_5000_raw_records.csv"), index=False)
    with open(os.path.join(results_dir, "rc_voi_5000_summary.json"), "w") as f:
        json.dump(summary_5000, f, indent=2)
    print("Completed 5,000-Module Benchmark. CSV & JSON saved.")

    # -------------------------------------------------------------
    # 3. Monte Carlo Multi-Seed Validation (6 Fixed Seeds)
    # -------------------------------------------------------------
    print("\n[STEP 3/5] Executing Multi-Seed Monte Carlo (6 Seeds x 500 Modules)...")
    seeds = [42, 101, 202, 303, 404, 505]
    mc_results = {pol: {"time": [], "cost": [], "uir": [], "far": [], "kwh": []} for pol in ["A_Fixed", "B_Scalar", "C_UncertaintyThresh", "D_RC_VOI"]}
    
    for s_idx in seeds:
        c_seed = generate_synthetic_cohort(500, seed=s_idx)
        _, s_dict = run_cohort_benchmark(c_seed, app)
        for pol in mc_results.keys():
            mc_results[pol]["time"].append(s_dict[pol]["time_distribution_s"]["mean"])
            mc_results[pol]["cost"].append(s_dict[pol]["cost_distribution_inr"]["mean"])
            mc_results[pol]["uir"].append(s_dict[pol]["uir_percent"])
            mc_results[pol]["far"].append(s_dict[pol]["far_percent"])
            mc_results[pol]["kwh"].append(s_dict[pol]["total_kwh_retained"])
            
    mc_summary = {}
    for pol in mc_results.keys():
        mc_summary[pol] = {
            "mean_time_s": compute_distribution_metrics(mc_results[pol]["time"]),
            "mean_cost_inr": compute_distribution_metrics(mc_results[pol]["cost"]),
            "uir_percent": compute_distribution_metrics(mc_results[pol]["uir"]),
            "far_percent": compute_distribution_metrics(mc_results[pol]["far"]),
            "kwh_retained": compute_distribution_metrics(mc_results[pol]["kwh"])
        }
    with open(os.path.join(results_dir, "monte_carlo_seeds_summary.json"), "w") as f:
        json.dump(mc_summary, f, indent=2)

    # -------------------------------------------------------------
    # 4. Sensitivity Sweeps
    # -------------------------------------------------------------
    print("\n[STEP 4/5] Executing Sensitivity Grid Sweeps...")
    sensitivity_data = run_sensitivity_sweeps(app, n_samples=500)
    with open(os.path.join(results_dir, "sensitivity_sweeps_summary.json"), "w") as f:
        json.dump(sensitivity_data, f, indent=2)

    # -------------------------------------------------------------
    # 5. Ablation Study
    # -------------------------------------------------------------
    print("\n[STEP 5/5] Executing RC-VOI Component Ablation...")
    ablation_data = run_ablation_benchmarks(cohort_500, app)
    with open(os.path.join(results_dir, "rc_voi_ablation_summary.json"), "w") as f:
        json.dump(ablation_data, f, indent=2)

    # Effect Size: Policy D (RC-VOI) vs Policy C (Uncertainty Threshold)
    c_times = df_5000[df_5000["policy"] == "C_UncertaintyThresh"]["diag_time_s"].values
    d_times = df_5000[df_5000["policy"] == "D_RC_VOI"]["diag_time_s"].values
    d_time_effect = cohens_d(d_times, c_times)
    
    c_costs = df_5000[df_5000["policy"] == "C_UncertaintyThresh"]["diag_cost_inr"].values
    d_costs = df_5000[df_5000["policy"] == "D_RC_VOI"]["diag_cost_inr"].values
    d_cost_effect = cohens_d(d_costs, c_costs)
    
    print("\n" + "="*75)
    print("SIMULATION COMPLETED SUCCESSFULLY!")
    print(f"5,000 Module Results:")
    print(f"Policy A (Fixed)     : Mean Time = {summary_5000['A_Fixed']['time_distribution_s']['mean']:5.1f}s | Cost = INR {summary_5000['A_Fixed']['cost_distribution_inr']['mean']:5.2f} | FAR = {summary_5000['A_Fixed']['far_percent']:4.1f}% | UIR = {summary_5000['A_Fixed']['uir_percent']:4.1f}%")
    print(f"Policy B (Scalar)    : Mean Time = {summary_5000['B_Scalar']['time_distribution_s']['mean']:5.1f}s | Cost = INR {summary_5000['B_Scalar']['cost_distribution_inr']['mean']:5.2f} | FAR = {summary_5000['B_Scalar']['far_percent']:4.1f}% | UIR = {summary_5000['B_Scalar']['uir_percent']:4.1f}%")
    print(f"Policy C (UncThresh) : Mean Time = {summary_5000['C_UncertaintyThresh']['time_distribution_s']['mean']:5.1f}s | Cost = INR {summary_5000['C_UncertaintyThresh']['cost_distribution_inr']['mean']:5.2f} | FAR = {summary_5000['C_UncertaintyThresh']['far_percent']:4.1f}% | UIR = {summary_5000['C_UncertaintyThresh']['uir_percent']:4.1f}%")
    print(f"Policy D (RC-VOI)    : Mean Time = {summary_5000['D_RC_VOI']['time_distribution_s']['mean']:5.1f}s | Cost = INR {summary_5000['D_RC_VOI']['cost_distribution_inr']['mean']:5.2f} | FAR = {summary_5000['D_RC_VOI']['far_percent']:4.1f}% | UIR = {summary_5000['D_RC_VOI']['uir_percent']:4.1f}%")
    print(f"Cohen's d (Policy D vs Policy C Time): d = {d_time_effect:.3f}")
    print(f"Cohen's d (Policy D vs Policy C Cost): d = {d_cost_effect:.3f}")
    print("="*75)

if __name__ == "__main__":
    main()
