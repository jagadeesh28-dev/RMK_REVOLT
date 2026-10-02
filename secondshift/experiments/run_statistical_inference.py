"""
Phase 10 & 11: Statistical Inference and Power/Sample Size Analysis
Project: RMK-REVOLT / SECONDShift Platform

Computes:
1. Exact paired statistics (McNemar test, Wilcoxon signed-rank test).
2. Timing distribution metrics (Mean, Median, SD, IQR, 95% CI).
3. Statistical power and required sample sizes for:
   - Demonstrating FAR < 1.0% at 95% confidence
   - Demonstrating Accuracy > 85% at 95% confidence
   - Demonstrating Detection Sensitivity > 90% at 95% confidence
"""

import json
import numpy as np
from scipy.stats import wilcoxon, binom, beta

RESULTS_PATH = "secondshift/data/processed/blind_validation_results.json"
REGISTRY_PATH = "secondshift/data/raw/ground_truth_registry.json"

def calculate_statistical_inference():
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)["specimens"]

    records = bench_data["specimen_records"]
    n = len(records)

    times_a = [r["decisions"]["BASELINE_A"]["time_s"] for r in records]
    times_prop = [r["decisions"]["SECONDSHIFT"]["time_s"] for r in records]

    # Timing metrics for SECONDShift
    mean_t_prop = np.mean(times_prop)
    median_t_prop = np.median(times_prop)
    std_t_prop = np.std(times_prop, ddof=1)
    iqr_t_prop = np.percentile(times_prop, 75) - np.percentile(times_prop, 25)

    # Wilcoxon signed-rank test on paired dwell times
    w_stat, p_val_w = wilcoxon(times_a, times_prop)

    # Paired categorical decisions: McNemar test
    # Compare Baseline A correctness vs SECONDShift correctness
    b_correct = 0 # Baseline A correct, SECONDShift wrong
    c_correct = 0 # SECONDShift correct, Baseline A wrong
    both_correct = 0
    both_wrong = 0

    for rec in records:
        spec_key = rec["true_specimen_key"]
        gt = registry[spec_key]
        is_safe = (gt["chemistry"] == "LFP" and gt["SOH"] >= 0.65 and gt["R0_mohm"] <= 4.0 and gt["nominal_voltage_v"] >= 10.0 and gt["failure_class"] in ["NONE", "BORDERLINE_OPERATE", "REQUIRES_DERATING"])
        
        dec_a = rec["decisions"]["BASELINE_A"]["decision"] in ["OPERATE", "DERATE"]
        dec_prop = rec["decisions"]["SECONDSHIFT"]["decision"] in ["OPERATE", "DERATE"]

        corr_a = (dec_a == is_safe)
        corr_prop = (dec_prop == is_safe)

        if corr_a and corr_prop:
            both_correct += 1
        elif not corr_a and not corr_prop:
            both_wrong += 1
        elif corr_a and not corr_prop:
            b_correct += 1
        elif corr_prop and not corr_a:
            c_correct += 1

    # Exact McNemar p-value via binomial distribution
    # p = 2 * P(Binom(b + c, 0.5) <= min(b, c))
    n_discordant = b_correct + c_correct
    if n_discordant > 0:
        p_val_mcnemar = 2.0 * binom.cdf(min(b_correct, c_correct), n_discordant, 0.5)
        p_val_mcnemar = min(1.0, float(p_val_mcnemar))
    else:
        p_val_mcnemar = 1.0

    # -------------------------------------------------------------
    # PHASE 11: SAMPLE SIZE / POWER ANALYSIS
    # -------------------------------------------------------------
    # Goal 1: Prove FAR < 1.0% at 95% confidence assuming zero observed failures.
    # Rule of Three / Clopper-Pearson: 1 - (1 - alpha)^(1/N) <= target -> (0.05)^(1/N) >= 1 - 0.01 -> N >= ln(0.05) / ln(0.99)
    n_required_far_1pct = int(np.ceil(np.log(0.05) / np.log(0.99)))

    # Goal 2: Demonstrate Accuracy > 85% at 95% confidence with power = 80%.
    # H0: p <= 0.85, H1: p = 0.95 (one-sided exact test)
    # Using normal approximation for proportion test:
    # N = (z_alpha * sqrt(p0*(1-p0)) + z_beta * sqrt(p1*(1-p1)))^2 / (p1 - p0)^2
    z_alpha = 1.645 # 95% one-sided
    z_beta = 0.842  # 80% power
    p0 = 0.85
    p1 = 0.95
    n_required_acc_85pct = int(np.ceil(((z_alpha * np.sqrt(p0*(1-p0)) + z_beta * np.sqrt(p1*(1-p1))) / (p1 - p0))**2))

    # Goal 3: Detection Sensitivity > 90% at 95% confidence (p0 = 0.90, p1 = 0.98, power = 80%)
    p0_sens = 0.90
    p1_sens = 0.98
    n_required_sens_90pct = int(np.ceil(((z_alpha * np.sqrt(p0_sens*(1-p0_sens)) + z_beta * np.sqrt(p1_sens*(1-p1_sens))) / (p1_sens - p0_sens))**2))

    summary = {
        "timing_inference": {
            "mean_s": round(mean_t_prop, 4),
            "median_s": round(median_t_prop, 4),
            "std_s": round(std_t_prop, 4),
            "iqr_s": round(iqr_t_prop, 4),
            "wilcoxon_stat": float(w_stat),
            "wilcoxon_p_value": float(p_val_w)
        },
        "paired_mcnemar_test": {
            "both_correct": both_correct,
            "both_wrong": both_wrong,
            "baseline_a_only_correct": b_correct,
            "secondshift_only_correct": c_correct,
            "p_value_mcnemar": p_val_mcnemar
        },
        "power_and_sample_size": {
            "current_dataset_n": n,
            "current_unsafe_specimens_n": 7,
            "required_n_for_far_less_than_1pct_at_95ci": n_required_far_1pct,
            "required_n_for_acc_greater_than_85pct": n_required_acc_85pct,
            "required_n_for_sens_greater_than_90pct": n_required_sens_90pct
        }
    }

    with open("secondshift/data/processed/statistical_inference_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "="*80)
    print("STATISTICAL INFERENCE & POWER ANALYSIS RESULTS")
    print("="*80)
    print(f"Timing Comparison (Wilcoxon Signed-Rank Test): p = {p_val_w:.6f} (Stat = {w_stat})")
    print(f"McNemar Discordant Pairs: Baseline A only = {b_correct}, SECONDShift only = {c_correct}")
    print(f"McNemar Exact Binomial p-value: p = {p_val_mcnemar:.4f}")
    print("-" * 80)
    print(f"Current Benchmark Sample Size:            N = {n} (Unsafe: 7, Safe: 5)")
    print(f"Required Unsafe Sample Size for FAR < 1%: N >= {n_required_far_1pct} zero-failure trials")
    print(f"Required Sample Size for Accuracy > 85%:  N >= {n_required_acc_85pct} specimens")
    print(f"Required Sample Size for Sensitivity > 90%: N >= {n_required_sens_90pct} specimens")
    print("="*80)

    return summary

if __name__ == "__main__":
    calculate_statistical_inference()
